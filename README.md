# auto_seta

Resolve sozinho o minigame de setas do roubo de carro em servidores de GTA RP (FiveM).
Quando o minigame aparece, o programa lê a tela e aperta as setas do teclado na ordem certa.

> **Aviso:** a maioria dos servidores proíbe macros e automações, e usar este programa pode dar ban.
> Use por sua conta e risco. Os autores não se responsabilizam.

## Funcionalidades

- Uma janela (launcher) para ligar e desligar o bot, calibrar, testar a detecção e trocar os atalhos.
- Calibração visual: a tela congela e você arrasta um retângulo em volta do painel das setas.
- Prévia da região capturada, mostrando qual seta o programa enxergou.
- Atalhos configuráveis, inclusive com `CTRL`/`SHIFT`/`ALT` e com os botões laterais do mouse.
- Um bip ao ligar e outro ao desligar, para saber o estado sem sair do jogo.
- As teclas vão por `SendInput` com scancode, que o FiveM aceita (o `pyautogui` costuma ser ignorado).


## Como usar

1. Deixe o jogo em janela sem bordas (borderless). Em tela cheia exclusiva a captura sai preta.
2. Abra o `auto_seta.exe` e aceite o pedido de administrador. Sem ele, as teclas podem não chegar ao jogo.
3. Calibre uma vez: com o minigame aberto na tela, aperte F7, arraste um retângulo em volta do
   painel das setas e solte. `Esc` cancela.
4. Confira a prévia no launcher. Se ela mostrar a seta certa, está pronto.
5. Aperte F6 para ligar. O bip agudo avisa que ligou, e o grave, que desligou.

Se mudar a resolução ou a posição do jogo, calibre de novo.

### Atalhos padrão

| Tecla | Ação |
|-------|------|
| F6 | Ligar / desligar |
| F7 | Calibrar região |
| F9 | Testar detecção (salva `debug.png`) |

Para trocar um atalho, vá em "Teclas de atalho" no launcher, clique no botão da ação e aperte a tecla nova.
As setas não podem virar atalho, porque o próprio programa as aperta. Evite letras sozinhas, que também
disparam quando você digita no chat.

A região e os atalhos ficam salvos no `config.json`, ao lado do `.exe`.

## Como funciona

1. Captura com [`mss`](https://github.com/BoboTiG/python-mss) só a região calibrada da tela.
2. Procura a caixa cinza, que é a seta da vez. As verdes já foram apertadas e as escuras ainda vão vir.
3. Dentro da caixa, separa o triângulo branco e calcula o centro de massa dele. Num triângulo, o centro
   fica mais perto da base, então a seta aponta para o lado oposto ao do centro.
4. Envia a seta via `SendInput` com scancode e a flag `EXTENDED`.
5. Só aperta de novo quando a caixa cinza muda de lugar. Se ela ficar parada por 0,5 s, tenta de novo.
   Antes de cada tecla há um atraso aleatório curto.

## Rodar a partir do código

Precisa de Windows e Python 3.10 ou mais novo.

```bash
pip install mss numpy
python launcher.py
```

## Compilar

```bash
build.bat
```

O script instala o PyInstaller e gera `dist/auto_seta.exe`, com o `LEIA-ME.txt` ao lado.

## Estrutura

```
auto_seta.py   núcleo: detecção, envio de teclas, config e o Bot (thread)
launcher.py    interface Tkinter, ponto de entrada do .exe
build.bat      gera o .exe com PyInstaller
LEIA-ME.txt    instruções que vão junto com o .exe
```

## Problemas comuns

| Problema | Solução |
|----------|---------|
| Captura ou prévia preta | Coloque o jogo em janela sem bordas. |
| Detecta a seta, mas o jogo não recebe | Abra o programa como administrador. |
| Não detecta a seta | Aperte F9 com o minigame na tela e confira o `debug.png`. Se precisar, ajuste `GRAY_MIN`, `GRAY_MAX` e `WHITE_MIN` em `auto_seta.py`. |
| Seleção da região fora do lugar | Calibre com o mouse no mesmo monitor do jogo. |
