# Legenda IA para VLC 1.5.0

Esta versão junta as duas etapas do fluxo: o aplicativo continua criando a
legenda PT-BR em SRT e agora também pode gerar uma cópia do vídeo com a legenda
incorporada permanentemente para transmissão à TV.

## Novidade principal

Depois de gerar a legenda, clique em **Criar vídeo legendado para TV**. O programa
cria:

```text
Filme.legendado-PT-BR.mp4
```

O vídeo original permanece intacto. O novo MP4 usa H.264/AAC e pode ser aberto
no VLC para transmissão em **Reprodução > Renderizador**. Como a legenda está
desenhada na imagem, ela aparece na TV mesmo quando o renderizador não aceita o
arquivo SRT externo.

## Desempenho e fallback

- Tenta NVIDIA NVENC para usar a GPU na recodificação.
- Se a aceleração NVIDIA falhar, repete automaticamente pela CPU com `libx264`.
- A opção **Usar somente CPU** também vale para a criação do vídeo para TV.
- Mostra a porcentagem da conversão.

## Proteção dos arquivos

- Nunca altera o filme ou episódio original.
- Salva primeiro em um arquivo parcial oculto.
- Só substitui o destino quando a conversão termina com sucesso.
- Remove arquivos parciais ao cancelar ou falhar.
- Preserva uma conversão anterior completa caso a nova tentativa dê erro.

## Validação

A versão passou em 27 testes. O teste de integração cria um vídeo real, incorpora
uma legenda com FFmpeg, confirma H.264/AAC e verifica que o original permaneceu
exatamente igual.

## Observação

A legenda não pode ser desligada no MP4 para TV. Para assistir sem legenda, use
o arquivo de vídeo original, que continua na mesma pasta.
