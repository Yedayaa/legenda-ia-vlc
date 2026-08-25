# Histórico de versões

As mudanças relevantes do projeto são registradas neste arquivo.

## 1.5.0 — 2026-08-24

### Adicionado

- Botão **Criar vídeo legendado para TV** após a geração do SRT.
- Exportação MP4 H.264/AAC com a legenda incorporada permanentemente.
- Aceleração de vídeo NVIDIA NVENC com fallback automático para `libx264`/CPU.
- Progresso real da recodificação e abertura automática do resultado no VLC.
- Verificação do filtro `subtitles`/libass e dos codificadores do FFmpeg.

### Segurança e estabilidade

- O vídeo original nunca é alterado.
- O novo MP4 é produzido em arquivo temporário e só substitui o destino após a
  conclusão bem-sucedida.
- Falhas e cancelamentos removem a saída parcial e preservam uma versão anterior.
- Caminhos Windows com acentos e letras de unidade não são enviados diretamente
  ao filtro de legenda, evitando erros de escape.
- A faixa de áudio inglesa escolhida para a transcrição também é usada no MP4.

### Validação

- Teste real de criação de MP4 com legenda queimada, vídeo H.264 e áudio AAC.
- Testes de fallback NVIDIA → CPU e preservação do arquivo em caso de falha.

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
