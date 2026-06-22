# O Spinnaker 4.3.0 homologa perfeitamente com Ubuntu 22.04
FROM ubuntu:22.04

# Evita prompts interativos
ENV DEBIAN_FRONTEND=noninteractive

# 1. Instala o Python 3.10 e as dependências nativas (incluindo o Qt5 para cobrir toda a API)
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    python3.10-dev \
    libavcodec58 libavformat58 libswscale5 libswresample3 libavutil56 \
    libusb-1.0-0 libpcre2-16-0 libdouble-conversion3 \
    qtbase5-dev qtchooser qt5-qmake qtbase5-dev-tools \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 2. Copia os recursos para o container
COPY spinnaker_SDK/spinnaker-4.3.0.189-amd64/ /tmp/spinnaker_sdk/
COPY spinnaker_python/spinnaker_python-4.3.0.189-cp310-cp310-linux_x86_64.whl /tmp/
COPY server_zmq.py /app/

# 3. EXTRAÇÃO DIRETA: Descompacta TODOS os pacotes .deb
# Como estamos usando dpkg-deb -x, os scripts que quebravam o udev são ignorados
RUN for deb in /tmp/spinnaker_sdk/*.deb; do dpkg-deb -x "$deb" /; done \
    && ldconfig

# 4. Configura as variáveis de ambiente essenciais da FLIR (Crucial para GigE)
ENV LD_LIBRARY_PATH=/opt/spinnaker/lib:/usr/lib:/usr/local/lib
ENV GENICAM_GENTL64_PATH=/opt/spinnaker/lib/spinnaker-gentl

# 5. Instala o wrapper PySpin e dependências Python
RUN python3.10 -m pip install --upgrade pip
RUN python3.10 -m pip install /tmp/spinnaker_python-4.3.0.189-cp310-cp310-linux_x86_64.whl
RUN python3.10 -m pip install opencv-python "numpy<2.0" pyzmq

# 6. Limpa os arquivos temporários
RUN rm -rf /tmp/spinnaker_sdk /tmp/*.whl

# 7. Inicia o servidor automaticamente
CMD ["python3.10", "server_zmq.py"]