# Projeto: auto_seta

## Objetivo
Programa em Python que resolve automaticamente minigames do roubo de carro de um servidor de GTA RP (FiveM). Quando um minigame aparece, ele lê a tela e responde (teclas ou cliques). Hoje são dois: **setas** e **números**.

## Minigame 1: setas
- Painel escuro, semitransparente, com uma barra de progresso verde no topo.
- Abaixo dela vem uma fileira de ~12 caixas, cada uma com um triângulo indicando uma direção (cima, baixo, esquerda, direita).
- Estados das caixas:
  - **Verde**: seta já apertada corretamente.
  - **Cinza**: seta da vez, a que precisa ser apertada agora.
  - **Preta/escura**: setas futuras.
- Abaixo das caixas há 3 pontinhos verdes, que provavelmente indicam rodadas.
- As teclas são as setas do teclado.

## Minigame 2: números ("Clique nos números em ordem")
- Painel escuro com contador "0 / 8" e 3 pontinhos no topo, título branco e um mostrador redondo grande com contorno verde e marcações; no centro, um círculo com ícone de chave (verde). Barra de progresso verde embaixo.
- Bolinhas aparecem espalhadas no mostrador: contorno verde apagado (ex. RGB (24,63,49)–(35,114,86)), fundo escuro, número branco no meio. Por fora, um arco cinza é o tempo até ela sumir (a de menor número tem menos tempo).
- É preciso clicar com o mouse nas bolinhas em ordem crescente. Print de exemplo em `samples/numeros_1.png`.

## Arquivos
- `auto_seta.py`: núcleo. Detecção das setas (`detect`), teclado (`tap`) e mouse (`click`) via SendInput, config, atalhos e a classe `Bot`, que roda numa thread, cuida dos dois minigames e manda eventos por callback. Não usa `print`, porque o .exe roda sem console.
- `numeros.py`: detecção das bolinhas (`detect`) e leitura do dígito por modelos (`classify`).
- `launcher.py`: interface Tkinter (ponto de entrada do .exe). Liga/desliga; uma aba por minigame (`ModePanel`: ativo, calibrar, testar, prévia); calibração arrastando um retângulo num print congelado do monitor onde está o mouse (`RegionSelector`); troca de atalhos (clica e aperta a tecla; captura via GetAsyncKeyState). Fala com o bot por uma `queue` lida com `after(30)`.

Dependências: `pip install mss numpy pillow` (mss 10+: usar `mss.MSS`, via `_new_mss`). O resto usa ctypes/Win32 e tkinter, só funciona no Windows. Sem scipy de propósito, pra o .exe não inchar (componentes conexos são feitos à mão em `numeros._components`).

### Setas: funcionamento
1. Captura com `mss` apenas a região calibrada das setas.
2. Acha a caixa cinza (pixels com canais entre `GRAY_MIN` e `GRAY_MAX` e baixa saturação, `GRAY_SAT`) e pega o trecho contínuo em volta do pico de pixels cinza nas colunas e linhas. O corte é 30% do pico: com 60% a caixa saía cortada nas colunas/linhas do triângulo e a direção errava (visto em teste com imagem sintética).
3. Dentro da caixa, isola o triângulo branco (`WHITE_MIN`) e calcula o centro de massa. Num triângulo, o centro fica mais perto da base, então:
   - centro à esquerda → seta para a **direita**; centro à direita → **esquerda**
   - centro em cima → **baixo**; centro embaixo → **cima**
4. Envia a tecla via `SendInput` com **scancode + flag EXTENDED** (setas: up 0x48, down 0x50, left 0x4B, right 0x4D). Isso é necessário para o FiveM aceitar; pyautogui costuma ser ignorado.
5. Só aperta de novo quando a caixa cinza muda de posição. Se ela não andar em `RETRY_AFTER` segundos, tenta de novo. Há um atraso aleatório (`DELAY_MIN`–`DELAY_MAX`) antes de cada tecla.

### Números: funcionamento
1. Máscaras: branco (`WHITE_MIN`/`WHITE_SAT`), verde (`GREEN_DIFF`/`GREEN_MIN`, baixos porque o contorno é apagado), escuro (`DARK_MAX`).
2. Componentes brancos com formato de dígito viram candidatos. Só valem se houver um círculo verde em volta (raio entre 1,4 e 3,6 × altura do dígito, `RING_MIN` da circunferência verde) e fundo escuro entre o dígito e o círculo (`DARK_FRAC`). Isso descarta título, contador e as caixas verdes do minigame de setas.
3. O dígito é lido comparando com modelos 1–9 renderizados de fontes negrito do Windows (`FONTS`), normalizados em 24×24 mantendo a proporção. Modelos extras: pasta `digitos/` ao lado do programa (arquivos cujo nome começa pelo dígito). O teste (F9) salva os recortes em `debug_digitos/` pra montar essa pasta.
4. `Bot._step_numeros` clica na bolinha de menor número visível, ignorando por `CLICK_IGNORE` as recém-clicadas (estão sumindo). Clique: SendInput de movimento absoluto + SetCursorPos + down/up, com atraso aleatório `CLICK_DELAY_MIN`–`CLICK_DELAY_MAX`.
5. Testes feitos: o print de exemplo é lido certo (1, 2, 3) em escala 1×, 1,5× e 2×; com fontes que não estão nos modelos, 104/108 dígitos certos (erros só em fonte condensada bem pequena); nenhum detector dispara no minigame do outro.

### Atalhos (lidos com GetAsyncKeyState)
Configuráveis pelo launcher ou na seção `"teclas"` do `config.json` (`DEFAULT_KEYS` / `parse_key`; aceita `CTRL+F6`, `MOUSE4` etc.; setas são proibidas porque o bot as aperta). Padrão:
- **F6**: liga/desliga o bot inteiro (bip agudo/grave); resolve todo minigame ativo e calibrado
- **F7**: calibrar setas
- **F8**: calibrar números
- **F9**: testar todos os minigames calibrados (salva `debug_setas.png` / `debug_numeros.png`)

`config.json` = `{"setas": {"regiao", "ativo"}, "numeros": {"regiao", "ativo"}, "teclas": {...}}`. Formatos antigos (só região; `regiao` no topo; atalho `calibrar`/`canto_sup_esq`) são migrados em `load_config`.

### Observações
- O jogo deve estar em janela sem bordas (tela cheia exclusiva deixa a captura preta).
- Pode ser preciso rodar como administrador para o SendInput chegar ao jogo.
- O processo é DPI-aware para as coordenadas do mouse baterem com as do `mss`.
- A última seta da fileira (▲) aparece meio acinzentada no jogo, por isso `GRAY_MIN` está em 115. Talvez precise de ajuste com o `debug_setas.png`.

## Status
- Nenhum dos dois foi **testado no jogo** ainda; só com prints e imagens sintéticas.
- Próximos passos: calibrar as regiões, testar com F9 e ajustar limiares de cor se necessário. No minigame de números, confirmar que o clique via SendInput chega na NUI do FiveM.

## Distribuição
- `build.bat` gera `dist\auto_seta.exe` a partir de `launcher.py` com PyInstaller (`--onefile --windowed --uac-admin`) e copia o `LEIA-ME.txt` para `dist\`.
- Empacotado, `config.json`, `debug_*.png`, `digitos/` e `debug_digitos/` ficam ao lado do .exe (`BASE_DIR` via `sys.executable`).
- Repositório privado: https://github.com/MatCristo/auto_seta

## Aviso
O servidor provavelmente proíbe macros. Existe risco de ban, e o usuário está ciente.
