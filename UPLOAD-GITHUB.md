# Como publicar este projeto no GitHub

Nome sugerido para o repositório: `legenda-ia-vlc`.

## Método simples pelo navegador

1. Entre em <https://github.com/new>.
2. Em **Repository name**, escreva `legenda-ia-vlc`.
3. Escolha **Public** para qualquer pessoa ver ou **Private** para deixar oculto.
4. Não marque as opções de criar README, `.gitignore` ou licença, pois estes
   arquivos já estão no pacote.
5. Clique em **Create repository**.
6. Extraia `Legenda-IA-VLC-GitHub.zip` no computador.
7. Na página do repositório vazio, clique em **uploading an existing file**.
   Se essa opção não aparecer, use **Add file > Upload files**.
8. Abra a pasta extraída, selecione **todo o conteúdo dentro dela** e arraste
   para o GitHub. Não envie somente o ZIP e não crie uma pasta duplicada.
9. Em **Commit changes**, escreva `Publica versão 1.5.0` e confirme.

Depois do envio, a aba **Actions** executará automaticamente os testes. Um sinal
verde indica que a sintaxe e os testes unitários passaram.

## Criar uma versão para download

O repositório contém o código-fonte. Para oferecer o pacote pronto ao usuário:

1. Abra **Releases** no lado direito da página do repositório.
2. Clique em **Create a new release**.
3. Crie a tag `v1.5.0`.
4. Use o título `Legenda IA para VLC 1.5.0`.
5. Anexe o arquivo `Legenda-IA-VLC.zip` que já foi testado.
6. Avise que o usuário precisa instalar Python 3.12 e VLC antes de executar.
7. Publique a release.

## Antes de tornar público

- O pacote já ignora vídeos, legendas, logs, modelos e a pasta `.venv`.
- Não publique capturas de tela que mostrem seu nome de usuário ou caminhos do
  Windows.
- O projeto ainda não tem uma licença própria. Escolha uma licença antes de
  autorizar cópia, modificação, redistribuição ou uso comercial por terceiros.
