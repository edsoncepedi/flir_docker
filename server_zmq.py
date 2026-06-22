import PySpin
import cv2
import zmq
import signal
import sys
import numpy as np

def init_camera():
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    
    if cam_list.GetSize() == 0:
        cam_list.Clear()
        system.ReleaseInstance()
        raise RuntimeError("Nenhuma câmera FLIR detectada. Verifique as conexões USB/GigE.")

    cam = cam_list.GetByIndex(0)
    cam.Init()
    print(f"Câmera inicializada com sucesso.")

    # Garante o formato Mono16 (Dados brutos radiométricos)
    nodemap = cam.GetNodeMap()
    try:
        px_fmt = PySpin.CEnumerationPtr(nodemap.GetNode("PixelFormat"))
        if PySpin.IsAvailable(px_fmt) and PySpin.IsWritable(px_fmt):
            node_pixel_format_mono16 = px_fmt.GetEntryByName("Mono16")
            if PySpin.IsAvailable(node_pixel_format_mono16) and PySpin.IsReadable(node_pixel_format_mono16):
                px_fmt.SetIntValue(node_pixel_format_mono16.GetValue())
                print("PixelFormat configurado para Mono16 (16-bit raw).")
    except PySpin.SpinnakerException as e:
        print(f"Aviso ao configurar PixelFormat: {e}")

    # Configura o modo de aquisição para contínuo
    node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
    if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
        node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

    return cam, system, cam_list

def main():
    port = 5555
    
    # Configura o ZeroMQ (Padrão Publisher)
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(f"tcp://0.0.0.0:{port}")
    print(f"Servidor ZeroMQ aguardando conexões na porta {port}...")

    cam, system, cam_list = init_camera()

    running = True
    def signal_handler(sig, frame):
        nonlocal running
        print("\nSinal de parada recebido. Encerrando transmissão...")
        running = False

    signal.signal(signal.SIGINT, signal_handler)

    try:
        cam.BeginAcquisition()
        print("Transmissão iniciada. Pressione Ctrl+C para parar.")
        
        frame_count = 0
        while running:
            # Captura o frame com timeout de 2000ms
            image_result = cam.GetNextImage(2000)

            if image_result.IsIncomplete():
                print(f"Frame incompleto: {image_result.GetImageStatus()}")
                image_result.Release()
                continue

            # Extrai a matriz bruta de 16-bits (uint16)
            raw_array = image_result.GetNDArray()
            image_result.Release()

            # Codifica a matriz em formato PNG na memória (Lossless para 16-bits)
            success, buffer = cv2.imencode('.png', raw_array)
            
            if success:
                # Transmite os bytes codificados
                socket.send(buffer.tobytes())
                print(f"Frame {frame_count:04d} transmitido via ZMQ...", end="\r")
                frame_count += 1

    except PySpin.SpinnakerException as ex:
        print(f"\nErro de Spinnaker durante a captura: {ex}")
    except Exception as e:
        print(f"\nErro geral: {e}")
    finally:
        # Procedimento rigoroso de limpeza (baseado no seu código)
        if cam.IsStreaming():
            cam.EndAcquisition()
        cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        socket.close()
        context.term()
        print("\nCâmera e recursos de rede liberados com segurança.")

if __name__ == "__main__":
    main()