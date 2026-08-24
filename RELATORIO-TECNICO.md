# Relatório técnico — Legenda IA para VLC 1.4.0

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
- Local de saída verificado antes do processamento demorado.

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

Foram aprovados 20 testes, incluindo:

- UTF-8 e ausência de mojibake;
- formatação SRT e preservação de todas as palavras;
- sincronismo por palavra;
- sobreposição e deduplicação entre blocos;
- seleção real da faixa inglesa usando FFmpeg;
- carregamento correto de `AutoTokenizer.from_pretrained`;
- envio do marcador `>>pob<<` ao tradutor;
- fallback de memória do Whisper e da tradução;
- gravação atômica do SRT.

## Validação final recomendada

Executar um filme completo no Windows com a GTX 1070 confirma o comportamento
do driver CUDA, dos modelos baixados e do VLC no computador de destino.
