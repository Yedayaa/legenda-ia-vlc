# Histórico de versões

As mudanças relevantes do projeto são registradas neste arquivo.

## 1.4.0 — 2026-08-24

### Adicionado

- Seleção automática da faixa de áudio marcada como inglês.
- Teste real de integração com FFmpeg e arquivo de duas faixas.
- Tempos por palavra do Whisper para melhorar os cortes das legendas.
- Sobreposição protegida entre blocos de áudio.
- Gravação atômica do SRT.
- Memorização do caminho de instalações portáteis do VLC.
- Cancelamento da extração de áudio e limpeza de temporários antigos.

### Melhorado

- Processamento em blocos de 5 minutos para reduzir RAM e VRAM.
- Cálculo temporal pela duração real do WAV, evitando desvio acumulado.
- Tradução com destino explícito `pob` para português do Brasil.
- Liberação de modelos e cache da GPU entre transcrição e tradução.
- Mensagens de dependência, memória e gravação em português.
- Instalador para Python 3.10–3.13, priorizando Python 3.12 de 64 bits.

### Corrigido

- Palavras descartadas ao quebrar legendas em duas linhas.
- Erro `NoneType` causado por streams ausentes na execução gráfica.
- Carregamento do tokenizer com `AutoTokenizer.from_pretrained`.
- Fallback incompleto em erros de memória durante transcrição e tradução.
- Texto corrompido por encoding incorreto.

## 1.3.0

- Barra de progresso determinada de 0% a 100%.
- Opção manual **Usar somente CPU**.
- Pós-processamento de vocabulário brasileiro ampliado.
- Mensagens genéricas para diferentes placas de vídeo.

## 1.2.0

- Fallback de `medium.en` para `small.en`.
- Fallback da tradução para CPU.
- Divisão do áudio em blocos para reduzir uso de memória.

## 1.1.x

- Primeira interface gráfica funcional.
- Transcrição de inglês, tradução para português e geração de SRT para o VLC.

