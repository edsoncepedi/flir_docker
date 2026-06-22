import PySpin
import cv2
import numpy as np

def main():
    # 1. Inicializa o sistema e a câmera
    system = PySpin.System.GetInstance()
    cam_list = system.GetCameras()
    
    if cam_list.GetSize() == 0:
        print("Nenhuma câmera FLIR detectada.")
        cam_list.Clear()
        system.ReleaseInstance()
        return

    cam = cam_list.GetByIndex(0)
    cam.Init()

    try:
        # 2. Garante que o modo de captura está em Contínuo para o Preview
        nodemap = cam.GetNodeMap()
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
        if PySpin.IsAvailable(node_acquisition_mode) and PySpin.IsWritable(node_acquisition_mode):
            node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
            node_acquisition_mode.SetIntValue(node_acquisition_mode_continuous.GetValue())

        # 3. Inicia a transmissão
        cam.BeginAcquisition()
        print("\n=== FLIR A70 Conectada com Sucesso ===")
        print("-> Pressione 's' para tirar uma FOTO e salvar o ARRAY RADIOMÉTRICO em CSV.")
        print("-> Pressione 'q' para fechar o programa.\n")

        # Processador apenas para converter o sinal térmico bruto em algo visível no monitor
        processor = PySpin.ImageProcessor()
        processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)

        while True:
            # Captura o frame atual do buffer
            image_result = cam.GetNextImage(1000)

            if image_result.IsIncomplete():
                image_result.Release()
                continue

            # --- MONITORAMENTO DAS TECLAS ---
            key = cv2.waitKey(1) & 0xFF

            # Se o usuário pressionar 's', capturamos a foto salvando o array bruto
            if key == ord('s'):
                print("Capturando foto e extraindo matriz térmica...")
                
                # Dados brutos nativos da A70 (Geralmente Mono16 -> Valores de até 65535)
                raw_array = image_result.GetNDArray()
                
                largura = image_result.GetWidth()
                altura = image_result.GetHeight()
                formato = image_result.GetPixelFormatName()
                
                # Salva o arquivo CSV com os valores puros de 16-bits
                nome_csv = "snapshot_termico_A70.csv"
                np.savetxt(nome_csv, raw_array, delimiter=",", fmt='%d')
                
                print(f" Matriz salva em '{nome_csv}'")
                print(f" Resolução detectada: {largura}x{altura} (Nativa da A70)")
                print(f" Formato do dado: {formato}\n")

            # --- RENDERIZAÇÃO DO PREVIEW TÉRMICO ---
            # Converte para Mono8 ou BGR8 apenas para exibição em tempo real na tela do OpenCV
            image_converted = processor.Convert(image_result, PySpin.PixelFormat_BGR8)
            display_frame = image_converted.GetNDArray()

            # Libera o frame para a câmera continuar gravando
            image_result.Release()

            # Mostra a imagem na tela
            cv2.imshow("FLIR A70 - Live Preview", display_frame)

            # Se pressionar 'q', sai do programa
            if key == ord('q'):
                break

        # 4. Limpeza
        cam.EndAcquisition()
        cv2.destroyAllWindows()
        
    except PySpin.SpinnakerException as ex:
        print(f"Erro no Spinnaker: {ex}")

    finally:
        # Desconexão segura do hardware
        cam.DeInit()
        del cam
        cam_list.Clear()
        system.ReleaseInstance()
        print("Câmera desconectada com segurança.")

if __name__ == "__main__":
    main()