"""
Captura e salvamento — FLIR A-series via GigE (Spinnaker SDK)
=============================================================
Pré-requisitos:
  1. Spinnaker SDK instalado  → https://www.flir.com/products/spinnaker-sdk/
  2. pip install spinnaker-python  (versão deve bater com o SDK instalado)
  3. NIC com MTU 9000 (jumbo frames):
       Linux : sudo ip link set eth0 mtu 9000
       Windows: Device Manager → NIC → Advanced → Jumbo Packet = 9014
  4. Câmera com IP estático na mesma subnet da NIC
       Usar FLIR IP Config Utility (vem com o SDK) para atribuir o IP

Uso rápido:
  python flir_capture.py                      # captura 10 frames e salva
  python flir_capture.py --n 50 --fps 5       # 50 frames a 5 fps
  python flir_capture.py --continuous         # captura até Ctrl+C
"""

import PySpin
import numpy as np
import cv2
import json
import argparse
import signal
import sys
from pathlib import Path
from datetime import datetime


# ── Configurações padrão ────────────────────────────────────────────────────

OUTPUT_DIR   = Path("capturas_flir")
PIXEL_FORMAT = "Mono16"        # raw 16-bit radiométrico
DEFAULT_FPS  = 10
DEFAULT_N    = 10


# ── Inicialização ────────────────────────────────────────────────────────────

def init_camera() -> tuple[PySpin.CameraPtr, PySpin.System]:
    """
    Detecta e inicializa a primeira câmera GigE disponível.
    Retorna (cam, system) — lembre de chamar cleanup() ao final.
    """
    system   = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    n        = cam_list.GetSize()

    if n == 0:
        system.ReleaseInstance()
        raise RuntimeError(
            "Nenhuma câmera FLIR detectada.\n"
            "Verifique: IP na mesma subnet, cabo, MTU da NIC."
        )

    print(f"{n} câmera(s) encontrada(s). Usando a primeira.")
    cam = cam_list[0]
    cam.Init()

    nodemap = cam.GetNodeMap()

    # Formato de pixel: Mono16 = raw radiométrico 16-bit
    px_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("PixelFormat"))
    px_fmt.SetIntValue(
        PySpin.CEnumEntryPtr(px_fmt.GetEntryByName(PIXEL_FORMAT)).GetValue()
    )

    # Modo de aquisição contínua
    acq = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
    acq.SetIntValue(
        PySpin.CEnumEntryPtr(acq.GetEntryByName("Continuous")).GetValue()
    )

    cam_list.Clear()
    print(f"Câmera pronta: {_cam_info(cam)}")
    return cam, system


def set_framerate(cam: PySpin.CameraPtr, fps: float):
    """Configura taxa de frames (se a câmera suportar controle de FPS)."""
    nodemap = cam.GetNodeMap()
    try:
        # Habilita controle de FPS
        fps_en = PySpin.CBooleanPtr(nodemap.GetNode("AcquisitionFrameRateEnable"))
        if PySpin.IsWritable(fps_en):
            fps_en.SetValue(True)

        fps_node = PySpin.CFloatPtr(nodemap.GetNode("AcquisitionFrameRate"))
        if PySpin.IsWritable(fps_node):
            fps_node.SetValue(min(fps, fps_node.GetMax()))
            print(f"FPS configurado: {fps_node.GetValue():.1f}")
    except PySpin.SpinnakerException:
        print("FPS automático (câmera não suporta controle manual de taxa).")


def _cam_info(cam: PySpin.CameraPtr) -> str:
    nodemap_tldev = cam.GetTLDeviceNodeMap()
    def get(name):
        node = PySpin.CStringPtr(nodemap_tldev.GetNode(name))
        return node.GetValue() if PySpin.IsReadable(node) else "N/A"
    return f"{get('DeviceModelName')}  SN:{get('DeviceSerialNumber')}"


# ── Conversão raw → °C ──────────────────────────────────────────────────────

def get_planck_coeffs(cam: PySpin.CameraPtr) -> dict:
    """
    Lê os coeficientes de calibração Planck do NodeMap da câmera.
    A FLIR A70 usa nomes de nós diferentes de outras séries — tentamos
    as variantes conhecidas em ordem.
    """
    nodemap = cam.GetNodeMap()

    def try_float(names: list[str]) -> float | None:
        for name in names:
            try:
                node = PySpin.CFloatPtr(nodemap.GetNode(name))
                if PySpin.IsReadable(node):
                    return node.GetValue()
            except Exception:
                pass
        return None

    # Variantes de nomes conhecidas nas séries A/T/E
    R1 = try_float(["R", "PlanckR1", "CalibrationR1"])
    R2 = try_float(["R2", "PlanckR2", "CalibrationR2"])
    B  = try_float(["B", "PlanckB",  "CalibrationB"])
    F  = try_float(["F", "PlanckF",  "CalibrationF"])
    O  = try_float(["O", "PlanckO",  "CalibrationO"])

    if all(v is not None for v in [R1, R2, B, F, O]):
        coeffs = {"R1": R1, "R2": R2, "B": B, "F": F, "O": O}
        print(f"Coeficientes Planck encontrados: {coeffs}")
        return coeffs

    # Se não achou, lista nós com nome relacionado a calibração
    print("Coeficientes Planck não encontrados nos nomes padrão.")
    print("Nós disponíveis no NodeMap com 'planck'/'calib'/'radiom':")
    try:
        for node in nodemap.GetNodes():
            try:
                name = node.GetName()
                if any(k in name.lower() for k in ["planck", "calib", "radiom"]):
                    fnode = PySpin.CFloatPtr(node)
                    if PySpin.IsReadable(fnode):
                        print(f"  {name} = {fnode.GetValue()}")
                    else:
                        print(f"  {name} (não float legível)")
            except Exception:
                pass
    except Exception as e:
        print(f"  (erro ao listar nós: {e})")

    print("\nA FLIR A70 pode operar em modo TemperatureLinear.")
    print("Tentando configurar IRFormat para temperatura direta...")
    return {}


def configure_temperature_linear(cam: PySpin.CameraPtr) -> bool:
    """
    Configura a A70 para entregar temperatura diretamente no pixel
    (modo TemperatureLinear100mK ou TemperatureLinear10mK).
    Nesse modo raw_to_celsius não é necessário — cada pixel já é T * 100 (em mK).
    """
    nodemap = cam.GetNodeMap()
    try:
        ir_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("IRFormat"))
        if not PySpin.IsWritable(ir_fmt):
            return False

        # Tenta 100mK primeiro (resolução 0.01°C), depois 10mK
        for entry_name in ["TemperatureLinear100mK", "TemperatureLinear10mK"]:
            entry = ir_fmt.GetEntryByName(entry_name)
            if PySpin.IsReadable(PySpin.CEnumEntryPtr(entry)):
                ir_fmt.SetIntValue(PySpin.CEnumEntryPtr(entry).GetValue())
                print(f"Modo IR configurado: {entry_name}")
                print("Conversão: temperatura (°C) = pixel_value / 100.0 - 273.15")
                return True
    except PySpin.SpinnakerException as e:
        print(f"IRFormat não disponível: {e}")
    return False


def detect_linear_scale(cam: PySpin.CameraPtr) -> float:
    """
    Captura um frame de diagnóstico para determinar a escala correta
    do modo TemperatureLinear na A70.
    Imprime o valor raw min/max/mean para inspeção.
    Retorna o divisor correto (100.0 para 100mK, 10.0 para 10mK).
    """
    cam.BeginAcquisition()
    try:
        img = cam.GetNextImage(5000)
        raw = img.GetNDArray()
        img.Release()
    finally:
        cam.EndAcquisition()

    raw_min  = int(raw.min())
    raw_max  = int(raw.max())
    raw_mean = float(raw.mean())

    print(f"\nDiagnóstico raw pixels:")
    print(f"  dtype  : {raw.dtype}")
    print(f"  min    : {raw_min}")
    print(f"  max    : {raw_max}")
    print(f"  mean   : {raw_mean:.1f}")

    # TemperatureLinear100mK: pixel = Kelvin * 100
    # Temperatura ambiente esperada ~25°C = 298K → pixel ≈ 29800
    # TemperatureLinear10mK:  pixel = Kelvin * 10  → pixel ≈ 2980
    # Se raw_mean > 20000 → escala 100 (100mK)
    # Se raw_mean > 2000  → escala 10  (10mK)
    # Se raw_mean < 1000  → provavelmente uint16 raw radiométrico sem escala linear

    if raw_mean > 20000:
        scale = 100.0
        t_est = raw_mean / scale - 273.15
        print(f"  Escala detectada: 100mK  →  T_mean ≈ {t_est:.1f}°C")
    elif raw_mean > 2000:
        scale = 10.0
        t_est = raw_mean / scale - 273.15
        print(f"  Escala detectada: 10mK   →  T_mean ≈ {t_est:.1f}°C")
    else:
        scale = 100.0
        print(f"  AVISO: raw_mean={raw_mean:.1f} inesperadamente baixo.")
        print(f"  Verifique PixelFormat e IRFormat no FLIR Spinnaker Explorer.")

    return scale



def raw_to_celsius_linear(raw: np.ndarray, scale: float = 100.0) -> np.ndarray:
    """
    Converte frame no modo TemperatureLinear.
    Pixel = Kelvin * scale  (100 para 100mK, 10 para 10mK).
    """
    return (raw.astype(np.float32) / scale) - 273.15

def raw_to_celsius(raw: np.ndarray, coeffs: dict) -> np.ndarray:
    """
    Converte frame raw uint16 → temperatura em °C via fórmula Planck.
    T(K) = B / ln(R1 / (R2 * (raw + O)) + F)
    """
    if not coeffs:
        # Sem coeficientes: retorna raw normalizado como fallback
        return raw.astype(np.float32)

    R1, R2 = coeffs["R1"], coeffs["R2"]
    B, F, O = coeffs["B"], coeffs["F"], coeffs["O"]

    raw_f    = raw.astype(np.float64)
    T_kelvin = B / np.log(R1 / (R2 * (raw_f + O)) + F)
    return (T_kelvin - 273.15).astype(np.float32)


# ── Salvamento ───────────────────────────────────────────────────────────────

def save_frame(thermal: np.ndarray,
               raw: np.ndarray,
               frame_id: int,
               output_dir: Path,
               coeffs: dict,
               save_raw: bool = True,
               save_thermal_jpg: bool = True,
               save_numpy: bool = True):
    """
    Salva um frame em múltiplos formatos conforme necessidade:

      .npy       — array float32 de temperatura em °C (melhor para análise Python)
      _raw.png   — raw uint16 em PNG 16-bit (sem perda, compacto)
      _thermal.jpg — visualização colorida para inspeção rápida
      _meta.json — metadados: timestamp, coeficientes, stats
    """
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    stem = output_dir / f"frame_{frame_id:04d}_{ts}"

    # 1. NumPy float32 em °C — formato principal para pipeline
    if save_numpy:
        np.save(str(stem) + ".npy", thermal)

    # 2. PNG 16-bit do raw — preserva dado original sem perda
    if save_raw:
        cv2.imwrite(str(stem) + "_raw.png", raw)

    # 3. JPEG colorido para inspeção visual rápida
    if save_thermal_jpg:
        t_min, t_max = thermal.min(), thermal.max()
        norm = ((thermal - t_min) / max(t_max - t_min, 0.1) * 255).astype(np.uint8)
        colored = cv2.applyColorMap(norm, cv2.COLORMAP_INFERNO)
        # Sobreposição de escala de temperatura
        cv2.putText(colored, f"{t_min:.1f}C",
                    (4, colored.shape[0] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.putText(colored, f"{t_max:.1f}C",
                    (colored.shape[1] - 60, colored.shape[0] - 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        cv2.imwrite(str(stem) + "_thermal.jpg", colored)

    # 4. Metadados JSON
    meta = {
        "frame_id":  frame_id,
        "timestamp": ts,
        "shape":     list(thermal.shape),
        "t_min":     float(thermal.min()),
        "t_max":     float(thermal.max()),
        "t_mean":    float(thermal.mean()),
        "coeffs":    coeffs,
    }
    with open(str(stem) + "_meta.json", "w") as f:
        json.dump(meta, f, indent=2)

    return stem


# ── Loop de captura ──────────────────────────────────────────────────────────

def capture_n_frames(cam: PySpin.CameraPtr,
                     coeffs: dict,
                     n: int,
                     output_dir: Path,
                     linear_mode: bool = False,
                     linear_scale: float = 100.0):
    """Captura N frames e salva cada um."""
    cam.BeginAcquisition()
    saved = 0

    print(f"\nCapturando {n} frames → {output_dir}")
    print("-" * 40)

    for i in range(n):
        try:
            img = cam.GetNextImage(5000)

            if img.IsIncomplete():
                status = img.GetImageStatus()
                print(f"  Frame {i}: incompleto (status {status}), pulando...")
                img.Release()
                continue

            raw = img.GetNDArray()
            if linear_mode:
                thermal = raw_to_celsius_linear(raw, linear_scale)
            else:
                thermal = raw_to_celsius(raw, coeffs)
            img.Release()

            stem = save_frame(thermal, raw, i, output_dir, coeffs)
            saved += 1
            print(f"  [{i+1:3d}/{n}] T_max={thermal.max():.1f}°C  → {stem.name}.*")

        except PySpin.SpinnakerException as e:
            print(f"  Frame {i}: erro → {e}")

    cam.EndAcquisition()
    print(f"\nSalvos: {saved}/{n} frames em {output_dir}")


def capture_continuous(cam: PySpin.CameraPtr,
                       coeffs: dict,
                       output_dir: Path,
                       linear_mode: bool = False,
                       linear_scale: float = 100.0):
    """
    Captura contínua até Ctrl+C.
    """
    running = True

    def _stop(sig, frame):
        nonlocal running
        print("\nCtrl+C recebido — encerrando...")
        running = False

    signal.signal(signal.SIGINT, _stop)

    cam.BeginAcquisition()
    frame_id = 0
    print(f"\nCaptura contínua iniciada → {output_dir}")
    print("Pressione Ctrl+C para parar.\n")

    while running:
        try:
            img = cam.GetNextImage(2000)
            if img.IsIncomplete():
                img.Release()
                continue

            raw = img.GetNDArray()
            if linear_mode:
                thermal = raw_to_celsius_linear(raw, linear_scale)
            else:
                thermal = raw_to_celsius(raw, coeffs)
            img.Release()

            save_frame(thermal, raw, frame_id, output_dir, coeffs)
            print(f"  frame {frame_id:04d}  T_max={thermal.max():.1f}°C", end="\r")
            frame_id += 1

        except PySpin.SpinnakerException as e:
            if running:
                print(f"\nErro: {e}")

    cam.EndAcquisition()
    print(f"\nTotal capturado: {frame_id} frames.")


# ── Cleanup ──────────────────────────────────────────────────────────────────

def cleanup(cam: PySpin.CameraPtr, system: PySpin.System):
    try:
        if cam.IsStreaming():
            cam.EndAcquisition()
    except Exception:
        pass
    try:
        cam.DeInit()
    except Exception:
        pass
    del cam
    del system
    print("Câmera liberada.")


# ── Carregar frames salvos ───────────────────────────────────────────────────

def load_frame(npy_path: str) -> tuple[np.ndarray, dict]:
    """
    Carrega um frame salvo (.npy) e seus metadados (.json).
    Retorna (thermal_array, meta_dict).
    """
    p    = Path(npy_path)
    meta_path = Path(str(p).replace(".npy", "_meta.json"))

    thermal = np.load(str(p))
    meta    = {}
    if meta_path.exists():
        with open(meta_path) as f:
            meta = json.load(f)

    return thermal, meta


def load_dataset(capture_dir: str) -> list[np.ndarray]:
    """
    Carrega todos os frames .npy de uma pasta, ordenados por frame_id.
    Útil para alimentar o TemporalFeatureExtractor.
    """
    files = sorted(Path(capture_dir).glob("frame_*.npy"))
    frames = [np.load(str(f)) for f in files]
    print(f"Carregados {len(frames)} frames de {capture_dir}")
    return frames


# ── Entry point ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Captura FLIR A-series via GigE")
    parser.add_argument("--n",          type=int,   default=DEFAULT_N,
                        help="Número de frames (padrão: 10)")
    parser.add_argument("--fps",        type=float, default=DEFAULT_FPS,
                        help="Taxa de frames desejada (padrão: 10)")
    parser.add_argument("--continuous", action="store_true",
                        help="Captura contínua até Ctrl+C")
    parser.add_argument("--out",        type=str,   default=str(OUTPUT_DIR),
                        help="Pasta de saída")
    args = parser.parse_args()

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    cam, system = init_camera()

    try:
        set_framerate(cam, args.fps)
        coeffs = get_planck_coeffs(cam)

        # Se não achou coeficientes Planck, tenta modo TemperatureLinear
        linear_mode = False
        linear_scale = 100.0
        if not coeffs:
            linear_mode = configure_temperature_linear(cam)
            if linear_mode:
                linear_scale = detect_linear_scale(cam)
            else:
                print("\nAVISO: sem coeficientes nem modo linear.")
                print("Os frames serão salvos como raw uint16 sem conversão para °C.")

        if args.continuous:
            capture_continuous(cam, coeffs, output_dir, linear_mode, linear_scale)
        else:
            capture_n_frames(cam, coeffs, args.n, output_dir, linear_mode, linear_scale)

    finally:
        cleanup(cam, system)

    print(f"\nPara carregar os frames depois:")
    print(f"  from flir_capture import load_dataset")
    print(f"  frames = load_dataset('{output_dir}')")


if __name__ == "__main__":
    main()
