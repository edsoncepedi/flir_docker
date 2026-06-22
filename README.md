# Documentação: Streaming FLIR A70 via Docker e ZeroMQ

Este repositório contém a infraestrutura e os scripts necessários para capturar dados térmicos brutos (16-bits) de uma câmera FLIR A70 (via conexão GigE Ethernet) e transmiti-los em tempo real para uma aplicação host utilizando ZeroMQ.

## 1. Arquitetura do Sistema

O Spinnaker SDK (oficial da FLIR) possui restrições rigorosas de compatibilidade de sistema operacional e exige o Ubuntu 22.04. Para isolar essa dependência e manter o ambiente de desenvolvimento principal limpo e atualizado, a arquitetura foi dividida em duas partes:

1. **Servidor (Container Docker):** Roda um ambiente isolado baseado no Ubuntu 22.04 e Python 3.10. Ele inicializa a câmera, extrai as matrizes radiométricas puras (`Mono16`), codifica os frames em PNG (compressão *lossless* de 16-bits) e publica os bytes via ZeroMQ (Padrão PUB) na porta 5555.
2. **Cliente (Host):** Roda diretamente na máquina principal. Ele se inscreve no tópico ZeroMQ (Padrão SUB), recebe os bytes em tempo real e decodifica a matriz térmica, entregando o `ndarray` original de 16-bits para processamento ou exibição.

## 2. Estrutura de Diretórios Necessária

Para que a compilação do Docker funcione sem problemas, a raiz do projeto deve conter a seguinte estrutura exata:

```text
/flir_docker
 ├── Dockerfile
 ├── server_zmq.py                     # Script do servidor (captura e transmissão)
 ├── spinnaker_SDK/
 │    └── spinnaker-4.3.0.189-amd64/   # Pasta extraída com os arquivos .deb
 └── spinnaker_python/
      └── spinnaker_python-4.3.0.189-cp310-cp310-linux_x86_64.whl # Wheel do PySpin
```
## 3. O Ambiente Docker (Spinnaker SDK)

A construção da imagem Docker (`Dockerfile`) resolve diversos gargalos técnicos crônicos de hardwares industriais em containers:

* **Extração Direta (`dpkg-deb -x`):** Em vez de usar `apt-get install` nos arquivos `.deb` da FLIR, os arquivos são descompactados diretamente no sistema. Isso impede que os scripts internos do pacote tentem reiniciar o serviço `udev` (que não existe em containers) e abortem a compilação.
* **Variáveis de Ambiente GigE:** A configuração define o caminho `GENICAM_GENTL64_PATH`. Sem essa variável estrita, a API do Spinnaker não consegue localizar os drivers GenTL necessários para descobrir as câmeras de rede.
* **Rede Host:** O container deve operar sem isolamento de rede (`--network host`) para permitir a troca de pacotes de broadcast e Jumbo Frames exigidos pela FLIR A70.

## 4. Como Compilar a Imagem

Com todos os arquivos posicionados, abra o terminal na pasta raiz do projeto e execute a construção da imagem. O processo fará a instalação de dependências como bibliotecas de vídeo (`libavcodec`, `libswscale`) e do próprio Python.

```bash
docker build -t flir_streamer .
```

> **Nota:** Caso o Spinnaker SDK ou o wheel do PySpin sejam atualizados no futuro, certifique-se de que os nomes dos arquivos e caminhos no `Dockerfile` reflitam a nova versão.

## 3. O Ambiente Docker (Spinnaker SDK)

A construção da imagem Docker (`Dockerfile`) resolve diversos gargalos técnicos crônicos de hardwares industriais em containers:

* **Extração Direta (`dpkg-deb -x`):** Em vez de usar `apt-get install` nos arquivos `.deb` da FLIR, os arquivos são descompactados diretamente no sistema. Isso impede que os scripts internos do pacote tentem reiniciar o serviço `udev` (que não existe em containers) e abortem a compilação.
* **Variáveis de Ambiente GigE:** A configuração define o caminho `GENICAM_GENTL64_PATH`. Sem essa variável estrita, a API do Spinnaker não consegue localizar os drivers GenTL necessários para descobrir as câmeras de rede.
* **Rede Host:** O container deve operar sem isolamento de rede (`--network host`) para permitir a troca de pacotes de broadcast e Jumbo Frames exigidos pela FLIR A70.

## 4. Como Compilar a Imagem

Com todos os arquivos posicionados, abra o terminal na pasta raiz do projeto e execute a construção da imagem. O processo fará a instalação de dependências como bibliotecas de vídeo (`libavcodec`, `libswscale`) e do próprio Python.

```bash
docker build -t flir_streamer .
```

> **Nota:** Caso o Spinnaker SDK ou o wheel do PySpin sejam atualizados no futuro, certifique-se de que os nomes dos arquivos e caminhos no `Dockerfile` reflitam a nova versão.

## 5. Como Executar a Aplicação

### 5.1. Iniciando o Servidor de Streaming (Container)

Inicie o container em background (`-d`) com os privilégios necessários de rede e dispositivos. O script `server_zmq.py` foi configurado como o comando padrão (`CMD`) da imagem, portanto ele ligará automaticamente.

```bash
docker run -d --privileged --network host --name flir_server flir_streamer
```

Para verificar se a câmera foi detectada e a transmissão está ativa, acompanhe os logs:

```bash
docker logs -f flir_server
```

**Saída esperada:**
```text
Câmera inicializada com sucesso.
PixelFormat configurado para Mono16 (16-bit raw).
Servidor ZeroMQ aguardando conexões na porta 5555...
Frame 0042 transmitido via ZMQ...
```

### 5.2. Consumindo os Dados (Cliente)

No seu ambiente de desenvolvimento principal (host), certifique-se de ter as bibliotecas `pyzmq`, `opencv-python` e `numpy` instaladas.

Execute o script cliente configurado para escutar a porta do container:

```bash
python client_zmq.py
```

O cliente reconstruirá perfeitamente a matriz de 16 bits para uso analítico e normalizará os valores para 8 bits apenas para renderizar uma interface de visualização.
## 6. Troubleshooting e Boas Práticas

* **Nenhuma Câmera FLIR Detectada:** Como a A70 se comunica via Ethernet, certifique-se de que a placa de rede do seu computador esteja configurada na mesma sub-rede da câmera e com pacotes Jumbo habilitados (MTU 9000). O Docker herda essa configuração graças ao `--network host`.
* **Latência ou Travamentos Visuais:** O OpenCV só atualiza as janelas de exibição corretamente se o `cv2.waitKey(1)` estiver no loop principal do cliente. Não utilize `time.sleep()`, pois isso causará estouro de buffer de memória no Spinnaker.
* **Cliente Recebe Dados, Mas a Tela Está Preta:** As matrizes de 16 bits nativas possuem valores de pico que raramente atingem o máximo absoluto (65535). Na decodificação com OpenCV (`cv2.IMREAD_UNCHANGED`), a matriz exibida pode parecer escura se não for explicitamente normalizada usando `cv2.normalize(frame, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)`.
* **Encerrando o Sistema:** Para parar o servidor corretamente e liberar a porta de rede, pare o container em vez de matá-lo à força. Isso permite que o script Python acione o bloco `finally` para liberar a câmera do Spinnaker.
  ```bash
  docker stop flir_server
  docker rm flir_server
  ```
