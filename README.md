# Legenda IA para VLC

Aplicativo gratuito para Windows que transforma áudio em inglês em legendas
sincronizadas em português do Brasil. Todo o processamento é feito localmente:
o programa extrai o áudio, transcreve com Whisper, traduz para PT-BR, cria um
arquivo `.srt` e abre o vídeo no VLC.

> Versão atual: **1.4.0** — testada em um vídeo de aproximadamente 60 minutos
> no Windows com
> **Intel Core i7-7700K, GTX 1070 8 GB e 16 GB de RAM**.

## O que o programa faz

- Procura automaticamente a faixa de áudio marcada como inglês.
- Transcreve o áudio com Whisper usando tempos de cada palavra.
- Traduz de inglês para português brasileiro com o destino `pob` do OPUS-MT.
- Divide o áudio em blocos de 5 minutos, com sobreposição para não cortar falas.
- Cria `Nome-do-video.pt-BR.srt` na mesma pasta do vídeo.
- Abre o vídeo no VLC com a legenda carregada.
- Usa CUDA em placas NVIDIA compatíveis e oferece fallback de memória.
- Exibe etapa, progresso aproximado e mensagens de erro em português.

O aplicativo **não modifica o vídeo e não cria um novo MP4/MKV**. A legenda
fica em um arquivo `.srt` separado, preservando o vídeo original.

## Em qual máquina roda?

O suporte oficial desta versão é para **Windows 10 ou 11 de 64 bits**.

| Perfil | Processador | RAM | GPU | Configuração indicada |
| --- | --- | --- | --- | --- |
| Mínimo funcional | x64 com 4 núcleos | 8 GB | Não é obrigatória | `small.en` + **Usar somente CPU**; processamento muito lento |
| Recomendado | 4 núcleos/8 threads ou melhor | 16 GB | NVIDIA CUDA com 6–8 GB de VRAM | `medium.en`; melhor equilíbrio entre qualidade e memória |
| Alto desempenho | 6 núcleos/12 threads ou melhor | 32 GB | NVIDIA com 8–12 GB de VRAM ou mais | `turbo`, se houver memória disponível |

Também é recomendado ter um SSD e pelo menos **15 GB livres** para o ambiente,
as dependências, os modelos de IA e os arquivos temporários.

### Avisos importantes sobre hardware

- **GTX 1070 8 GB:** configuração testada e recomendada com `medium.en`.
- **Placas NVIDIA com 4 GB:** prefira `small.en`; pode ocorrer fallback para CPU.
- **AMD, Intel integrada ou computador sem GPU NVIDIA:** o aplicativo funciona
  pela CPU, mas um filme de uma hora pode levar várias horas.
- **8 GB de RAM:** feche navegador, jogos e programas pesados. Se faltar memória,
  use `small.en` e marque **Usar somente CPU**.
- O instalador atual usa CUDA apenas em GPUs NVIDIA compatíveis. Ele não ativa
  aceleração AMD/Intel.
- Windows de 32 bits e Python de 32 bits não são suportados.
- Python 3.14 ainda não é suportado pelas dependências desta versão.

## Requisitos

- Windows 10 ou 11 de 64 bits.
- [Python 3.12.10 de 64 bits](https://www.python.org/downloads/release/python-31210/)
  — recomendado. Também são aceitos Python 3.10, 3.11 ou 3.13.
- [VLC Media Player](https://www.videolan.org/vlc/).
- Internet durante a instalação e o primeiro uso, para baixar dependências e
  modelos.
- Driver NVIDIA atualizado, caso a GPU seja usada.

## Instalação

1. Baixe o projeto e extraia todos os arquivos para uma pasta comum.
2. Instale o VLC.
3. Instale o Python 3.12.10 de 64 bits e marque **Add python.exe to PATH**.
4. Dê dois cliques em `instalar.bat` e aguarde a mensagem de conclusão.
5. Dê dois cliques em `iniciar.bat`.

Os modelos de IA são baixados automaticamente no primeiro processamento. Isso
pode demorar e consumir vários gigabytes de internet e armazenamento.

## Como usar

1. Clique em **Selecionar** e escolha o filme ou episódio.
2. Use **Recomendado — medium.en** na GTX 1070 ou GPU equivalente.
3. Deixe **Usar somente CPU** desmarcado quando houver GPU NVIDIA compatível.
4. Clique em **Gerar legenda e abrir no VLC**.
5. Aguarde até a legenda ser salva e o VLC abrir.

Exemplo de saída:

```text
Filme.mkv
Filme.pt-BR.srt
```

Para levar o conteúdo a outro computador ou à TV, mantenha os dois arquivos na
mesma pasta. Alguns aparelhos reconhecem a legenda automaticamente quando os
nomes são iguais antes do `.pt-BR.srt`.

## Modos de qualidade

| Opção | Uso aproximado | Quando usar |
| --- | --- | --- |
| `small.en` | Menor uso de VRAM e RAM | GPU com pouca memória ou prioridade para velocidade |
| `medium.en` | Cerca de 5 GB de VRAM durante a transcrição | Opção recomendada e testada na GTX 1070 8 GB |
| `turbo` | Maior exigência de memória | GPU mais folgada; pode cair para `small.en` se faltar VRAM |

O uso real varia conforme driver, versão das bibliotecas, duração do áudio e
outros programas abertos.

## Como funciona

1. O FFmpeg encontra a faixa de áudio em inglês e converte o som em blocos WAV.
2. O Whisper reconhece as falas e registra seus tempos.
3. O modelo OPUS-MT traduz as frases para português brasileiro.
4. O programa ajusta os cortes, limita as linhas e grava o SRT de forma atômica.
5. O VLC recebe o vídeo original e o SRT pronto.

Se a transcrição estourar a memória da GPU, o programa tenta `small.en`. Se a
tradução estourar a VRAM, ela é repetida pela CPU. Os modelos são liberados entre
as etapas para reduzir o pico de memória.

## Privacidade

- O vídeo e o áudio não são enviados para um servidor de transcrição.
- O processamento da legenda acontece no próprio computador.
- A internet é usada para instalar pacotes e baixar os modelos na primeira vez.
- Arquivos temporários são removidos ao final e restos antigos são limpos na
  próxima execução.

## Solução de problemas

### A janela fecha ou não abre

Execute `iniciar-diagnostico.bat`. Ele mantém o terminal aberto e mostra o erro.
O log também fica em:

```text
%TEMP%\LegendaIAVLC\app.log
```

### Python não foi encontrado

Instale o Python 3.12.10 de 64 bits pelo instalador tradicional do python.org,
marque **Add python.exe to PATH**, reinicie o Windows e execute `instalar.bat`.
Ter apenas o Python Manager ou Python 3.14 pode não ser suficiente.

### Falta de memória

Feche programas pesados e tente `small.en`. Se ainda falhar, marque
**Usar somente CPU**. Não force `turbo` em uma GPU com pouca VRAM.

### O VLC não foi encontrado

O programa permite selecionar manualmente o arquivo `vlc.exe` e lembra esse
caminho para os próximos usos.

### A faixa escolhida não está em inglês

O programa prioriza a faixa marcada como `eng`/`en`. Arquivos sem idioma nos
metadados usam a primeira faixa de áudio; nesse caso, ajuste a ordem das faixas
no arquivo ou use uma versão com metadados corretos.

## Desenvolvimento e testes

O projeto usa apenas a biblioteca padrão durante a descoberta dos testes; os
modelos pesados são simulados nos testes unitários.

```powershell
python -m compileall -q app.py tests
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

O fluxo de integração com FFmpeg é executado quando um binário `ffmpeg` está
disponível; caso contrário, esse teste é pulado.

## Estrutura do repositório

```text
app.py                       Aplicativo principal
instalar.bat                 Cria o ambiente e instala as dependências
iniciar.bat                  Inicialização normal
iniciar-diagnostico.bat      Inicialização com terminal visível
requirements.txt             Dependências Python
tests/                       Testes automáticos
.github/workflows/           Verificação automática no GitHub
LEIA-ME-PRIMEIRO.txt         Guia simples para o usuário final
RELATORIO-TECNICO.md         Decisões técnicas e validações
THIRD_PARTY_NOTICES.md       Créditos e licenças de terceiros
```

## Limitações conhecidas

- O escopo é fixo: áudio em inglês para legenda em português do Brasil.
- Tradução automática pode errar nomes, gírias, música e falas sobrepostas.
- A qualidade depende da clareza e do idioma real da faixa selecionada.
- O aplicativo gera SRT separado; não incorpora a legenda permanentemente.
- Instalação e interface foram preparadas para Windows, não para macOS/Linux.

## Créditos e licença

O projeto usa Whisper, PyTorch, Transformers, FFmpeg e o modelo
`Helsinki-NLP/opus-mt-tc-big-en-pt`. Consulte
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) antes de redistribuir.

Ainda não foi escolhida uma licença para o código deste repositório. Até que um
arquivo `LICENSE` seja adicionado, não presuma autorização para redistribuição,
modificação ou uso comercial do código.
