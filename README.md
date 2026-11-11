# auto_seta

Resolve sozinho dois minigames do roubo de carro em servidores de GTA RP (FiveM):

- **Setas:** uma fileira de caixas com triângulos. O programa aperta as setas do teclado na ordem certa.
- **Números:** bolinhas numeradas num mostrador redondo. O programa clica nelas em ordem (1, 2, 3...)
  antes que o tempo de cada uma acabe.

> **Aviso:** a maioria dos servidores proíbe macros e automações, e usar este programa pode dar ban.
> Use por sua conta e risco. Os autores não se responsabilizam.

## Funcionalidades

- Uma janela (launcher) com uma aba para cada minigame, onde você ativa, calibra e testa cada um.
- Um único atalho liga e desliga o bot; ele resolve qualquer minigame ativo que aparecer.
- Calibração visual: a tela congela e você arrasta um retângulo em volta do minigame.
- Prévia da região capturada, mostrando a seta ou a ordem dos números que o programa enxergou.
- Atalhos configuráveis, inclusive com `CTRL`/`SHIFT`/`ALT` e com os botões laterais do mouse.
- Um bip ao ligar e outro ao desligar, para saber o estado sem sair do jogo.
- Teclas e cliques vão por `SendInput`, que o FiveM aceita (o `pyautogui` costuma ser ignorado).

## Como usar

1. Deixe o jogo em janela sem bordas (borderless). Em tela cheia exclusiva a captura sai preta.
2. Abra o `auto_seta.exe` e aceite o pedido de administrador. Sem ele, as teclas e os cliques podem não
   chegar ao jogo.
3. Calibre cada minigame uma vez, com ele aberto na tela:
   - Setas: aperte F7 e arraste um retângulo em volta do painel das setas.
   - Números: aperte F8 e arraste um retângulo em volta do mostrador redondo inteiro.

   `Esc` cancela. Depois de soltar, o launcher mostra a prévia e o que foi detectado.
4. Aperte F6 para ligar. O bip agudo avisa que ligou, e o grave, que desligou.

Se mudar a resolução ou a posição do jogo, calibre de novo. Na aba de cada minigame dá para desmarcar
"Resolver este minigame" se você quiser usar só um deles.

### Atalhos padrão

| Tecla | Ação |
|-------|------|
| F6 | Ligar / desligar |
| F7 | Calibrar setas |
| F8 | Calibrar números |
| F9 | Testar detecção dos minigames calibrados |

Para trocar um atalho, vá em "Teclas de atalho" no launcher, clique no botão da ação e aperte a tecla nova.
As setas não podem virar atalho, porque o próprio programa as aperta. Evite letras sozinhas, que também
disparam quando você digita no chat.

As regiões e os atalhos ficam salvos no `config.json`, ao lado do `.exe`.

## Como funciona

### Setas

1. Captura com [`mss`](https://github.com/BoboTiG/python-mss) só a região calibrada da tela.
2. Procura a caixa cinza, que é a seta da vez. As verdes já foram apertadas e as escuras ainda vão vir.
3. Dentro da caixa, separa o triângulo branco e calcula o centro de massa dele. Num triângulo, o centro
   fica mais perto da base, então a seta aponta para o lado oposto ao do centro.
4. Envia a seta via `SendInput` com scancode e a flag `EXTENDED`.
5. Só aperta de novo quando a caixa cinza muda de lugar. Se ela ficar parada por 0,5 s, tenta de novo.
   Antes de cada tecla há um atraso aleatório curto.

### Números

1. Separa os pixels brancos (os números) e os verdes (o contorno das bolinhas).
2. Um bloco branco só conta como número se tiver um círculo verde em volta e fundo escuro entre os dois.
   Assim o título, o contador "0/8" e o próprio minigame de setas não são confundidos com bolinhas.
3. Reconhece o dígito comparando o bloco com modelos de 1 a 9 desenhados com fontes negrito do Windows.
4. Clica na bolinha de menor número que estiver na tela. As anteriores já foram clicadas e sumiram,
   então a menor é sempre a próxima. Uma bolinha recém-clicada é ignorada por 0,8 s enquanto some.

Se algum número for lido errado, use a pasta `digitos/`, explicada em [Problemas comuns](#problemas-comuns).

## Rodar a partir do código

Precisa de Windows e Python 3.10 ou mais novo.

```bash
pip install mss numpy pillow
python launcher.py
```

## Compilar

```bash
build.bat
```

O script instala o PyInstaller e gera `dist/auto_seta.exe`, com o `LEIA-ME.txt` ao lado.

## Estrutura

```
auto_seta.py   núcleo: detecção das setas, teclado e mouse, config e o Bot (thread)
numeros.py     detecção e leitura das bolinhas numeradas
launcher.py    interface Tkinter, ponto de entrada do .exe
build.bat      gera o .exe com PyInstaller
LEIA-ME.txt    instruções que vão junto com o .exe
samples/       prints dos minigames usados para testar a detecção
```

## Problemas comuns

| Problema | Solução |
|----------|---------|
| Captura ou prévia preta | Coloque o jogo em janela sem bordas. |
| Detecta, mas o jogo não recebe a tecla ou o clique | Abra o programa como administrador. |
| Não detecta a seta | Aperte F9 com o minigame na tela e confira o `debug_setas.png`. Se precisar, ajuste `GRAY_MIN`, `GRAY_MAX` e `WHITE_MIN` em `auto_seta.py`. |
| Não acha as bolinhas | Aperte F9 com o minigame na tela e confira o `debug_numeros.png`. Os limiares de cor ficam no topo de `numeros.py`. |
| Lê um número errado | Cada teste salva os números recortados em `debug_digitos/`, com o nome começando pelo dígito lido. Copie recortes certos para uma pasta `digitos/` ao lado do `.exe`, renomeando para começar pelo dígito verdadeiro (ex.: `7.png`, `7_b.png`), e abra o programa de novo. |
| Seleção da região fora do lugar | Calibre com o mouse no mesmo monitor do jogo. |
