# Legenda IA para VLC 1.4.0

Primeira versão validada de ponta a ponta em um vídeo de aproximadamente
60 minutos no Windows.

## Destaques

- Áudio em inglês para legenda sincronizada em português do Brasil.
- Seleção automática da faixa de áudio inglesa.
- Processamento local, sem assinatura nem chave de API.
- Aceleração CUDA em GPU NVIDIA e opção de usar somente CPU.
- Fallback de memória para `small.en` e tradução pela CPU.
- Tempos por palavra, blocos com sobreposição e gravação segura do SRT.
- Barra de progresso e mensagens de erro em português.

## Máquina testada

- Windows 64 bits
- Intel Core i7-7700K
- NVIDIA GTX 1070 8 GB
- 16 GB de RAM
- Perfil `medium.en`

## Requisitos resumidos

- Windows 10 ou 11 de 64 bits
- Python 3.12 de 64 bits
- VLC Media Player
- 8 GB de RAM no mínimo; 16 GB recomendados
- 15 GB livres e SSD recomendado
- GPU NVIDIA opcional; sem ela, o processamento ocorre pela CPU e demora mais

## Instalação

1. Extraia o ZIP.
2. Instale Python 3.12 de 64 bits e VLC.
3. Execute `instalar.bat` uma vez.
4. Execute `iniciar.bat`.

Na primeira legenda, aguarde o download dos modelos de IA.

## Observação

O aplicativo cria um arquivo `.pt-BR.srt` ao lado do vídeo. Ele não modifica o
vídeo original e não gera um novo arquivo de vídeo com a legenda incorporada.
