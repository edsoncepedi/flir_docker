import PySpin
import cv2
import numpy as np
from time import sleep

def main():
    # 1. Inicializa o sistema e a câmera
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    
    if cam_list.GetSize() == 0:
        print("Nenhuma câmera detectada.")
        cam_list.Clear()
        system.ReleaseInstance()
        return

    cam = cam_list.GetByIndex(0)
    cam.Init()

    try:
        # 2. Configura o modo de captura para Contínuo
        nodemap = cam.GetNodeMap()
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
        if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
            node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        # 3. Começa a transmitir (Acquisition)
        cam.BeginAcquisition()
        print("Transmissão iniciada. Pressione 'q' na janela de vídeo para sair.")

        # Criar o conversor de imagem do Spinnaker (Crucial para cores!)
        processor = PySpin.ImageProcessor()
        processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)

        while True:
            # Captura o frame bruto da câmera
            image_result = cam.GetNextImage(1000)  # timeout de 1000ms

            if image_result.IsIncomplete():
                print(f"Frame incompleto: {image_result.GetImageStatus()}")
                image_result.Release()
                continue

            # --- O SEGREDO DAS CORES ESTÁ AQUI ---
            # Converte a imagem Bayer/crua para RGB padrão
            image_converted = processor.Convert(image_result, PySpin.PixelFormat_BGR8)

            # Transforma os dados binários da FLIR em um Array do NumPy para o OpenCV
            # GetNDArray() retorna a matriz pronta de 3 dimensões (Altura, Largura, Canais de Cor)
            frame = image_converted.GetNDArray()

            # Libera as imagens da memória do SDK
            image_result.Release()

            # 4. Exibe a imagem na janela do OpenCV
            cv2.imshow("FLIR Camera - Array de Cores", frame)

            # Se pressionar a tecla 'q', fecha a janela
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        # 5. Finalização e limpeza (Ordem estrita para não travar a câmera)
        cam.EndAcquisition()
        cv2.destroyAllWindows()

        # Pequena pausa para garantir que tudo seja liberado antes de finalizar o sistema
        
    except PySpin.SpinnakerException as ex:
        print(f"Erro no Spinnaker: {ex}")

    finally:
        # Garante que a câmera seja liberada mesmo se houver erro
        cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        print("Sistema finalizado com segurança.")

if __name__ == "__main__":
    main()