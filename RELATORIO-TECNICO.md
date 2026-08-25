# Relatório técnico — Legenda IA para VLC 1.5.0

## Escopo

- Entrada fixa: faixa de áudio em inglês.
- Saída fixa: legenda SRT em português do Brasil.
- Processamento local; a internet é usada para instalar e baixar modelos.

## Qualidade e sincronismo

- Whisper com `word_timestamps=True`.
- Cortes de legenda limitados a duas linhas sem descarte de palavras.
- Tempos dos blocos calculados pela duração real do WAV.
- Blocos de 5 minutos com 12 segundos de sobreposição e janela protegida de
  6 segundos, evitando duplicações e falas cortadas nas divisões.
- Tradução com destino explícito `>>pob<<`, correspondente ao português
  brasileiro no modelo `Helsinki-NLP/opus-mt-tc-big-en-pt`.
- Pós-processamento conservador de vocabulário PT-PT para PT-BR.

## Estabilidade

- Whisper é liberado antes de carregar o tradutor.
- Fallback de `medium.en`/`turbo` para `small.en` em falta de VRAM.
- Fallback da tradução para CPU em falta de VRAM.
- Exceções de memória têm o traceback liberado antes da retentativa, evitando
  manter tensores e modelos antigos presos na memória.
- Extração FFmpeg cancelável.
- Pastas temporárias abandonadas são removidas no próximo uso.
- SRT salvo de forma atômica: um arquivo anterior só é substituído depois que
  a nova legenda foi gravada por completo.
- MP4 para TV salvo de forma atômica, sem alterar o vídeo original e sem deixar
  saída parcial após cancelamento ou falha.
- Local de saída verificado antes do processamento demorado.

## Vídeo com legenda permanente para TV

- Saída MP4 com vídeo H.264, áudio AAC 192 kbps, `yuv420p` e `faststart` para
  ampla compatibilidade com TVs, VLC e transmissão pela rede.
- Renderização da legenda pelo filtro `subtitles`/libass do FFmpeg.
- Escala garante dimensões pares sem mudar a proporção da imagem.
- A faixa inglesa detectada para a transcrição é mantida como áudio do MP4.
- NVIDIA `h264_nvenc` é usada quando disponível; uma falha dispara nova tentativa
  automática com `libx264` na CPU.
- O SRT é copiado para um diretório temporário com nome simples antes do filtro,
  evitando problemas de escape com `C:`, acentos, colchetes e apóstrofos.
- Progresso é calculado com `-progress pipe:1` e a duração real da mídia.

## Experiência de uso

- Seleção automática da faixa marcada como inglês, com fallback informado para
  a primeira faixa quando o vídeo não possui metadados de idioma.
- Barra de progresso por etapa e porcentagem aproximada.
- Opção manual para usar somente CPU.
- Caminho de uma instalação portátil do VLC é lembrado.
- Inicializador verifica código e dependências antes de abrir pelo `pythonw`.
- Instalador prioriza Python 3.12 de 64 bits, valida componentes e executa os
  testes automaticamente.

## Validação automatizada

Foram aprovados 27 testes, incluindo:

- UTF-8 e ausência de mojibake;
- formatação SRT e preservação de todas as palavras;
- sincronismo por palavra;
- sobreposição e deduplicação entre blocos;
- seleção real da faixa inglesa usando FFmpeg;
- carregamento correto de `AutoTokenizer.from_pretrained`;
- envio do marcador `>>pob<<` ao tradutor;
- fallback de memória do Whisper e da tradução;
- gravação atômica do SRT.
- criação real de MP4 com legenda queimada, H.264 e AAC;
- preservação byte a byte do vídeo original;
- fallback de NVENC para CPU;
- preservação de uma saída anterior quando a conversão falha.

## Validação final recomendada

Executar um filme completo no Windows com a GTX 1070 confirma o comportamento
do driver CUDA, dos modelos baixados e do VLC no computador de destino.
