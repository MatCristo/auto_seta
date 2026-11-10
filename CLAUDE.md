# Projeto: auto_seta

## Objetivo
Script em Python que resolve automaticamente o minigame de roubo de carro de um servidor de GTA RP (FiveM). Quando o minigame aparece, o script lê a tela e aperta as setas do teclado na ordem certa.

## Como é o minigame
- Painel escuro, semitransparente, com uma barra de progresso verde no topo.
- Abaixo dela vem uma fileira de ~12 caixas, cada uma com um triângulo indicando uma direção (cima, baixo, esquerda, direita).
- Estados das caixas:
  - **Verde**: seta já apertada corretamente.
  - **Cinza**: seta da vez, a que precisa ser apertada agora.
  - **Preta/escura**: setas futuras.
- Abaixo das caixas há 3 pontinhos verdes, que provavelmente indicam rodadas.
- As teclas são as setas do teclado.

## Arquivos
- `auto_seta.py`: núcleo (detecção, SendInput, config, classe `Bot` que roda numa thread e manda eventos por callback). Não usa `print`, porque o .exe roda sem console.
- `launcher.py`: interface Tkinter (ponto de entrada do .exe). Liga/desliga, calibra arrastando um retângulo num print congelado do monitor onde está o mouse (`RegionSelector`), mostra a prévia/resultado da detecção e troca atalhos (clica e aperta a tecla; captura via GetAsyncKeyState). Fala com o bot por uma `queue` lida com `after(30)`.

Dependências: `pip install mss numpy` (mss 10+: usar `mss.MSS`, via `_new_mss`). O resto usa ctypes/Win32 e tkinter, só funciona no Windows.

### Funcionamento
1. Captura com `mss` apenas a região calibrada da tela.
2. Acha a caixa cinza (pixels com canais entre `GRAY_MIN` e `GRAY_MAX` e baixa saturação, `GRAY_SAT`) e pega o trecho contínuo em volta do pico de pixels cinza nas colunas e linhas. O corte é 30% do pico: com 60% a caixa saía cortada nas colunas/linhas do triângulo e a direção errava (visto em teste com imagem sintética).
3. Dentro da caixa, isola o triângulo branco (`WHITE_MIN`) e calcula o centro de massa. Num triângulo, o centro fica mais perto da base, então:
   - centro à esquerda → seta para a **direita**; centro à direita → **esquerda**
   - centro em cima → **baixo**; centro embaixo → **cima**
4. Envia a tecla via `SendInput` com **scancode + flag EXTENDED** (setas: up 0x48, down 0x50, left 0x4B, right 0x4D). Isso é necessário para o FiveM aceitar; pyautogui costuma ser ignorado.
5. Só aperta de novo quando a caixa cinza muda de posição. Se ela não andar em `RETRY_AFTER` segundos, tenta de novo. Há um atraso aleatório (`DELAY_MIN`–`DELAY_MAX`) antes de cada tecla.

### Atalhos (lidos com GetAsyncKeyState)
Configuráveis pelo launcher ou na seção `"teclas"` do `config.json` (`DEFAULT_KEYS` / `parse_key`; aceita `CTRL+F6`, `MOUSE4` etc.; setas são proibidas porque o bot as aperta). `config.json` = `{"regiao": ..., "teclas": ...}`; formatos antigos são migrados ao carregar. Padrão:
- **F6**: liga/desliga o bot (bip agudo/grave)
- **F7**: calibrar (congela a tela e abre a seleção)
- **F9**: salva `debug.png` da região e mostra a detecção no launcher

### Observações
- O jogo deve estar em janela sem bordas (tela cheia exclusiva deixa a captura preta).
- Pode ser preciso rodar como administrador para o SendInput chegar ao jogo.
- O processo é DPI-aware para as coordenadas do mouse baterem com as do `mss`.
- A última seta da fileira (▲) aparece meio acinzentada no jogo, por isso `GRAY_MIN` está em 115. Talvez precise de ajuste com o `debug.png`.

## Status
- Código escrito, ainda **não testado no jogo**.
- Próximos passos: calibrar a região, testar a detecção com F9 e ajustar os limiares de cor se necessário.

## Distribuição
- `build.bat` gera `dist\auto_seta.exe` a partir de `launcher.py` com PyInstaller (`--onefile --windowed --uac-admin`) e copia o `LEIA-ME.txt` para `dist\`.
- Empacotado, `config.json` e `debug.png` ficam ao lado do .exe (`BASE_DIR` via `sys.executable`).

## Aviso
O servidor provavelmente proíbe macros. Existe risco de ban, e o usuário está ciente.
