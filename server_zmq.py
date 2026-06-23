"""
FLIR A70 — Servidor ZMQ corrigido
===================================
Correção principal: ordem de configuração
  1. PixelFormat → Mono16   (primeiro)
  2. IRFormat → TemperatureLinear10mK  (depois)
  3. AcquisitionMode → Continuous

Cliente usa: celsius = raw / 10.0 - 273.15
"""

import PySpin
import cv2
import zmq
import signal
import numpy as np
import time


def init_camera(retry_interval=10):
    attempt = 0
    while True:
        system   = PySpin.System.GetInstance()
        cam_list = system.GetCameras()

        if cam_list.GetSize() > 0:
            break

        cam_list.Clear()
        system.ReleaseInstance()
        attempt += 1
        print(f"[{attempt}] Nenhuma câmera FLIR detectada. Aguardando {retry_interval}s...")
        time.sleep(retry_interval)

    cam = cam_list.GetByIndex(0)
    cam.Init()
    print(f"Câmera inicializada.")

    nodemap = cam.GetNodeMap()

    # ── PASSO 1: PixelFormat → Mono16 ────────────────────────────────────────
    try:
        px_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("PixelFormat"))
        if PySpin.IsAvailable(px_fmt) and PySpin.IsWritable(px_fmt):
            entry = px_fmt.GetEntryByName("Mono16")
            if PySpin.IsAvailable(entry) and PySpin.IsReadable(entry):
                px_fmt.SetIntValue(entry.GetValue())
                print("PixelFormat → Mono16")
    except Exception as e:
        print(f"Aviso PixelFormat: {e}")

    # ── PASSO 2: IRFormat → TemperatureLinear10mK ────────────────────────────
    # DEVE vir DEPOIS do PixelFormat — a A70 pode resetar o PixelFormat
    # ao mudar o IRFormat, por isso confirmamos o Mono16 novamente abaixo
    ir_ok = False
    try:
        ir_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("IRFormat"))
        if PySpin.IsAvailable(ir_fmt) and PySpin.IsWritable(ir_fmt):
            entry = ir_fmt.GetEntryByName("TemperatureLinear10mK")
            if PySpin.IsAvailable(entry) and PySpin.IsReadable(entry):
                ir_fmt.SetIntValue(entry.GetValue())
                print("IRFormat → TemperatureLinear10mK")
                ir_ok = True
    except Exception as e:
        print(f"Aviso IRFormat: {e}")

    if not ir_ok:
        print("AVISO: IRFormat não configurado — raw sem conversão de temperatura")

    # ── PASSO 3: Confirma Mono16 ainda ativo (A70 pode ter resetado) ─────────
    try:
        px_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("PixelFormat"))
        atual  = px_fmt.GetCurrentEntry().GetSymbolic()
        if atual != "Mono16":
            print(f"PixelFormat resetou para {atual} — reconfigurando para Mono16...")
            entry = px_fmt.GetEntryByName("Mono16")
            if PySpin.IsAvailable(entry) and PySpin.IsReadable(entry):
                px_fmt.SetIntValue(entry.GetValue())
                print("PixelFormat → Mono16 (reconfigurado)")
        else:
            print(f"PixelFormat confirmado: {atual}")
    except Exception as e:
        print(f"Aviso confirmação PixelFormat: {e}")

    # ── PASSO 4: AcquisitionMode → Continuous ────────────────────────────────
    try:
        acq = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
        if PySpin.IsAvailable(acq) and PySpin.IsWritable(acq):
            acq.SetIntValue(acq.GetEntryByName("Continuous").GetValue())
            print("AcquisitionMode → Continuous")
    except Exception as e:
        print(f"Aviso AcquisitionMode: {e}")

    return cam, system, cam_list


def main():
    port = 5555

    context = zmq.Context()
    socket  = context.socket(zmq.PUB)
    socket.bind(f"tcp://0.0.0.0:{port}")
    print(f"Servidor ZMQ na porta {port}...")

    cam, system, cam_list = init_camera()

    running = True
    def signal_handler(sig, frame):
        nonlocal running
        print("\nEncerrando...")
        running = False
    signal.signal(signal.SIGINT, signal_handler)

    try:
        cam.BeginAcquisition()
        print("\nTransmissão iniciada.")
        print("Conversão no cliente: celsius = raw / 10.0 - 273.15")
        print("Pressione Ctrl+C para parar.\n")

        frame_count = 0
        while running:
            image_result = cam.GetNextImage(2000)

            if image_result.IsIncomplete():
                print(f"Frame incompleto: {image_result.GetImageStatus()}")
                image_result.Release()
                continue

            raw_array = image_result.GetNDArray()
            image_result.Release()

            # Diagnóstico nos primeiros 3 frames
            if frame_count < 3:
                mean_val = raw_array.mean()
                t_est    = mean_val / 10.0 - 273.15
                print(f"  Frame {frame_count}: raw_mean={mean_val:.0f}  "
                      f"→ {t_est:.1f}°C (esperado ~20-35°C)")

            success, buffer = cv2.imencode('.png', raw_array)
            if success:
                socket.send(buffer.tobytes())
                print(f"Frame {frame_count:04d} transmitido...", end="\r")
                frame_count += 1

    except PySpin.SpinnakerException as ex:
        print(f"\nErro Spinnaker: {ex}")
    except Exception as e:
        print(f"\nErro: {e}")
    finally:
        if cam.IsStreaming():
            cam.EndAcquisition()
        cam.DeInit()
        del cam
        cam_list.Clear()
        del system
        socket.close()
        context.term()
        print("\nRecursos liberados.")


if __name__ == "__main__":
    main()