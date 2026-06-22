import cv2

CAMERA_IP = "172.16.8.13"
# O caminho final (/avc ou /mpeg4) depende do canal configurado na interface Web da FLIR
rtsp_url = f"rtsp://{CAMERA_IP}:554/avc"
#rtsp_url = f"rtsp://{CAMERA_IP}:554/mpeg4"
#rtsp_url = f"rtsp://{CAMERA_IP}:554/mjpg"

cap = cv2.VideoCapture(rtsp_url)

if not cap.isOpened():
    print("Incapaz de conectar ao fluxo RTSP da câme.+ra FLIR A70.")
    exit()

while True:
    ret, frame = cap.read()
    if not ret:
        print("Falha na captura do frame de vídeo.")
        break
        
    # O frame já traz o processamento MSX aplicado diretamente pelo hardware da câmera
    cv2.imshow("FLIR A70 - Live Stream (MSX Habilitado)", frame)
    
    # Interrompe a execução ao pressionar a tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()