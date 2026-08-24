# Como contribuir

Contribuições são bem-vindas, principalmente para estabilidade, sincronismo,
qualidade do PT-BR, acessibilidade e redução do uso de memória.

## Antes de começar

1. Abra uma issue descrevendo o erro ou a melhoria.
2. Não publique vídeos, áudios, legendas, nomes de arquivos ou logs com dados
   pessoais.
3. Preserve o escopo atual: áudio em inglês para legenda em português do Brasil.
4. Evite aumentar o consumo de RAM/VRAM sem documentar o impacto.

## Preparação

No Windows com Python 3.12 de 64 bits:

```powershell
instalar.bat
```

## Testes obrigatórios

```powershell
python -m compileall -q app.py tests
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Mudanças em FFmpeg, Whisper, tradução, tempo ou formatação de SRT também devem
ser testadas manualmente com um vídeo curto antes de usar um filme completo.

## Padrão do código

- Arquivos Python e Markdown em UTF-8.
- Interface e mensagens destinadas ao usuário em português do Brasil.
- Funções pequenas, mensagens de erro claras e testes para toda correção.
- Nenhum token, senha, modelo baixado, mídia ou ambiente `.venv` no commit.

## Pull request

Explique o problema, a solução, o hardware usado e como a mudança foi testada.
Se alterar desempenho, informe RAM, GPU, VRAM e tempo aproximado.

