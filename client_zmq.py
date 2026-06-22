import zmq
import cv2
import numpy as np

def main():
    # Conecta ao servidor ZeroMQ que está exposto pelo Docker
    context = zmq.Context()
    socket = context.socket(zmq.SUB)
    socket.connect("tcp://127.0.0.1:5555")
    
    # O filtro vazio b"" significa inscrever-se em todas as mensagens
    socket.setsockopt(zmq.SUBSCRIBE, b"")

    print("Cliente ZeroMQ conectado. Aguardando frames térmicos...")

    try:
        while True:
            # Recebe o pacote de bytes pela rede
            png_bytes = socket.recv()
            
            # Transforma os bytes recebidos em um array 1D
            np_arr = np.frombuffer(png_bytes, dtype=np.uint8)
            
            # Decodifica de volta para o formato original 2D de 16-bits
            # cv2.IMREAD_UNCHANGED garante que a matriz continue sendo uint16
            frame_16bit = cv2.imdecode(np_arr, cv2.IMREAD_UNCHANGED)
            
            if frame_16bit is not None:
                # Para processamento: a variável 'frame_16bit' contém seus dados originais!
                # temp_min = frame_16bit.min()
                # temp_max = frame_16bit.max()
                
                # Para exibição na tela: normaliza o range de 16 bits para 8 bits
                frame_display = cv2.normalize(frame_16bit, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)
                frame_colorido = cv2.applyColorMap(frame_display, cv2.COLORMAP_INFERNO)
                
                cv2.imshow("FLIR A70 - ZMQ Stream", frame_colorido)

            # Pressione 'q' na janela para sair
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\nEncerrando cliente...")
    finally:
        cv2.destroyAllWindows()
        socket.close()
        context.term()

if __name__ == "__main__":
    main()