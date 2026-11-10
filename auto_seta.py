"""
auto_seta.py - Núcleo do bot que resolve o minigame de setas.

Como funciona:
  1. Captura só a região da tela onde o minigame aparece (calibrada uma vez).
  2. Procura a caixa CINZA (a seta que precisa ser apertada agora).
  3. Dentro dela, acha o triângulo branco e descobre a direção pela posição
     do centro de massa (num triângulo, o centro fica mais perto da base).
  4. Envia a seta via SendInput com scancode (funciona em jogos DirectInput).

A interface fica em launcher.py. Este módulo não usa print: tudo passa pelo
callback de eventos do Bot (o .exe roda sem console).
"""

import ctypes
import json
import os
import queue
import random
import sys
import threading
import time
import traceback

import mss
import mss.tools
import numpy as np

# mss 10+ usa mss.MSS (mss.mss foi depreciado); versões antigas só têm mss.mss
_new_mss = getattr(mss, "MSS", None) or mss.mss

# --------------------------------------------------------------------------
# Ajustes
# --------------------------------------------------------------------------
GRAY_MIN = 115          # caixa cinza: canais entre GRAY_MIN e GRAY_MAX
GRAY_MAX = 180
GRAY_SAT = 25           # diferença máxima entre R, G e B (cinza = pouca cor)
WHITE_MIN = 200         # triângulo branco: todos os canais acima disso
MIN_BOX_PX = 12         # altura mínima (px) da caixa cinza pra valer
DELAY_MIN = 0.04        # atraso aleatório antes de cada tecla (segundos)
DELAY_MAX = 0.09
RETRY_AFTER = 0.5       # se a caixa não andar nesse tempo, aperta de novo

# Pasta ao lado do .exe (quando empacotado) ou do .py (rodando direto).
# Dentro do .exe, __file__ aponta pra uma pasta temporária, por isso o sys.executable.
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(BASE_DIR, "config.json")
DEBUG_PNG = os.path.join(BASE_DIR, "debug.png")

# --------------------------------------------------------------------------
# Win32: DPI, mouse, teclado
# --------------------------------------------------------------------------
user32 = ctypes.windll.user32
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    user32.SetProcessDPIAware()

PUL = ctypes.POINTER(ctypes.c_ulong)


class KeyBdInput(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", PUL)]


class HardwareInput(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_short),
                ("wParamH", ctypes.c_ushort)]


class MouseInput(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", PUL)]


class InputUnion(ctypes.Union):
    _fields_ = [("ki", KeyBdInput), ("mi", MouseInput), ("hi", HardwareInput)]


class Input(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("ii", InputUnion)]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_SCANCODE = 0x0008

# Scancodes das setas (precisam da flag EXTENDED, senão viram o numpad)
SCAN = {"up": 0x48, "down": 0x50, "left": 0x4B, "right": 0x4D}


def _send(scan, up=False):
    flags = KEYEVENTF_SCANCODE | KEYEVENTF_EXTENDEDKEY
    if up:
        flags |= KEYEVENTF_KEYUP
    extra = ctypes.c_ulong(0)
    ii = InputUnion()
    ii.ki = KeyBdInput(0, scan, flags, 0, ctypes.pointer(extra))
    inp = Input(1, ii)
    user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))


def tap(direction):
    scan = SCAN[direction]
    _send(scan)
    time.sleep(random.uniform(0.025, 0.05))
    _send(scan, up=True)


def cursor_pos():
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y


def key_down(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


# --------------------------------------------------------------------------
# Teclas de atalho configuráveis
# --------------------------------------------------------------------------
DEFAULT_KEYS = {
    "ligar_desligar": "F6",
    "calibrar": "F7",
    "debug": "F9",
}

KEY_LABELS = {
    "ligar_desligar": "Ligar / desligar",
    "calibrar": "Calibrar região",
    "debug": "Testar detecção",
}

# Nomes extras (o primeiro de cada código é o nome "oficial")
VK_NAMES = {
    "INSERT": 0x2D, "INS": 0x2D, "DELETE": 0x2E, "DEL": 0x2E,
    "HOME": 0x24, "END": 0x23, "PAGEUP": 0x21, "PGUP": 0x21,
    "PAGEDOWN": 0x22, "PGDN": 0x22, "PAUSE": 0x13, "SCROLLLOCK": 0x91,
    "CAPSLOCK": 0x14, "TAB": 0x09, "SPACE": 0x20, "ENTER": 0x0D,
    "ESC": 0x1B, "BACKSPACE": 0x08,
    "MOUSE3": 0x04, "MOUSE4": 0x05, "MOUSE5": 0x06,
}
MOD_NAMES = {"CTRL": 0x11, "SHIFT": 0x10, "ALT": 0x12}

# código -> nome, usado quando a tecla é escolhida pelo launcher
VK_TO_NAME = {}
for _i in range(1, 25):
    VK_TO_NAME[0x6F + _i] = f"F{_i}"
for _c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
    VK_TO_NAME[ord(_c)] = _c
for _i in range(10):
    VK_TO_NAME[0x60 + _i] = f"NUM{_i}"
for _n, _vk in VK_NAMES.items():
    VK_TO_NAME.setdefault(_vk, _n)

# Teclas que podem virar atalho no "aperte uma tecla" do launcher.
# Fora: ESC (cancela), modificadores (só combinados) e as setas (o bot usa).
CAPTURE_VKS = [vk for vk in VK_TO_NAME if vk != 0x1B]


def parse_key(text):
    """'F6', 'K', 'CTRL+F6', 'MOUSE4', 'NUM5'... -> (vk, [vks dos modificadores])."""
    parts = [p for p in str(text).upper().replace(" ", "").split("+") if p]
    if not parts:
        raise ValueError("vazia")
    *mods, main = parts
    mod_vks = []
    for m in mods:
        if m not in MOD_NAMES:
            raise ValueError(f"modificador desconhecido: {m}")
        mod_vks.append(MOD_NAMES[m])
    if main in VK_NAMES:
        vk = VK_NAMES[main]
    elif main in MOD_NAMES:
        vk = MOD_NAMES[main]
    elif len(main) == 1 and main.isascii() and main.isalnum():
        vk = ord(main)
    elif main[0] == "F" and main[1:].isdigit() and 1 <= int(main[1:]) <= 24:
        vk = 0x6F + int(main[1:])
    elif main.startswith("NUM") and main[3:].isdigit() and len(main) == 4:
        vk = 0x60 + int(main[3])
    else:
        raise ValueError(f"tecla desconhecida: {main}")
    return vk, mod_vks


def same_binding(a, b):
    try:
        ka, kb = parse_key(a), parse_key(b)
    except ValueError:
        return False
    return ka[0] == kb[0] and sorted(ka[1]) == sorted(kb[1])


class Hotkeys:
    """Detecta o momento em que a tecla é apertada (borda de subida)."""

    def __init__(self, bindings):
        # bindings: {acao: (vk, [modificadores])}
        self.bindings = bindings
        # começa com o estado atual, pra não disparar uma tecla que já
        # estava apertada quando o atalho foi trocado
        self.prev = {a: self._is_down(a) for a in bindings}

    def _is_down(self, action):
        vk, mods = self.bindings[action]
        return key_down(vk) and all(key_down(m) for m in mods)

    def pressed(self, action):
        down = self._is_down(action)
        hit = down and not self.prev[action]
        self.prev[action] = down
        return hit


def build_bindings(keys, log=lambda msg: None):
    """Converte os nomes do config em códigos; tecla inválida volta pro padrão."""
    bindings = {}
    for action, text in keys.items():
        try:
            bindings[action] = parse_key(text)
        except ValueError as e:
            log(f"Tecla inválida em '{KEY_LABELS[action]}': {text!r} ({e}). "
                f"Usando {DEFAULT_KEYS[action]}.")
            keys[action] = DEFAULT_KEYS[action]
            bindings[action] = parse_key(DEFAULT_KEYS[action])
    return bindings


# --------------------------------------------------------------------------
# Detecção
# --------------------------------------------------------------------------
def _main_run(counts, frac=0.3):
    """Pega o trecho contínuo em volta do pico (ignora ruído espalhado)."""
    peak = int(counts.argmax())
    # 0.3: as colunas/linhas que passam pelo triângulo branco têm bem menos
    # cinza que as bordas da caixa, e com um corte alto a caixa saía cortada.
    limit = counts[peak] * frac
    a = peak
    while a > 0 and counts[a - 1] >= limit:
        a -= 1
    b = peak
    while b < len(counts) - 1 and counts[b + 1] >= limit:
        b += 1
    return a, b


def detect(img):
    """Recebe BGRA (numpy). Retorna (direção, x_centro_caixa) ou None."""
    b = img[:, :, 0].astype(np.int16)
    g = img[:, :, 1].astype(np.int16)
    r = img[:, :, 2].astype(np.int16)
    mx = np.maximum(np.maximum(r, g), b)
    mn = np.minimum(np.minimum(r, g), b)

    gray = (mn >= GRAY_MIN) & (mx <= GRAY_MAX) & ((mx - mn) <= GRAY_SAT)
    cols = gray.sum(axis=0)
    if cols.max() < MIN_BOX_PX:
        return None
    x0, x1 = _main_run(cols)
    rows = gray[:, x0:x1 + 1].sum(axis=1)
    if rows.max() < MIN_BOX_PX * 0.5:
        return None
    y0, y1 = _main_run(rows)
    if (y1 - y0) < MIN_BOX_PX or (x1 - x0) < MIN_BOX_PX:
        return None

    box_mn = mn[y0:y1 + 1, x0:x1 + 1]
    white = box_mn >= WHITE_MIN
    if white.sum() < 8:
        return None

    ys, xs = np.nonzero(white)
    wx0, wx1, wy0, wy1 = xs.min(), xs.max(), ys.min(), ys.max()
    dx = (xs.mean() - (wx0 + wx1) / 2) / max(1, wx1 - wx0)
    dy = (ys.mean() - (wy0 + wy1) / 2) / max(1, wy1 - wy0)

    # O centro de massa fica do lado da BASE do triângulo,
    # ou seja, oposto à ponta.
    if abs(dx) > abs(dy):
        direction = "right" if dx < 0 else "left"
    else:
        direction = "down" if dy < 0 else "up"
    return direction, (x0 + x1) // 2


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
def load_config():
    cfg, erro = {}, None
    if os.path.exists(CONFIG):
        try:
            with open(CONFIG, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as e:
            erro = f"Erro lendo config.json ({e}). Usando o padrão."
            cfg = {}
    if "left" in cfg:  # formato bem antigo: o arquivo era só a região
        cfg = {"regiao": cfg}
    old = cfg.get("teclas", {})
    if "calibrar" not in old and "canto_sup_esq" in old:  # versão com F7/F8
        old["calibrar"] = old["canto_sup_esq"]
    keys = dict(DEFAULT_KEYS)
    keys.update({k: v for k, v in old.items() if k in DEFAULT_KEYS})
    cfg["teclas"] = keys
    cfg.setdefault("regiao", None)
    return cfg, erro


def save_config(cfg):
    with open(CONFIG, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)


# --------------------------------------------------------------------------
# Bot (roda numa thread; conversa com a interface por eventos)
# --------------------------------------------------------------------------
DIR_PT = {"up": "cima", "down": "baixo", "left": "esquerda", "right": "direita"}


class Bot:
    """
    Eventos enviados por on_event(tipo, dados):
      ("log", texto)
      ("estado", ligado: bool)
      ("tecla", direção)
      ("calibrar", (png_bytes, monitor))  -> print congelado pra escolher a região
      ("debug", (png_bytes, resultado))   -> print da região + detecção
      ("erro", traceback)
    """

    def __init__(self, cfg, on_event):
        self.cfg = cfg
        self.on_event = on_event
        self.active = False
        self.capturing = False      # launcher esperando uma tecla nova
        self.requests = queue.Queue()
        self._stop = threading.Event()
        self.hk = Hotkeys(build_bindings(cfg["teclas"], self.log))
        self._reset_tracking()
        self.thread = threading.Thread(target=self._run, daemon=True)

    # ---- chamado pela interface ----
    def start(self):
        self.thread.start()

    def stop(self):
        self._stop.set()

    def set_keys(self, keys):
        self.cfg["teclas"] = keys
        self.hk = Hotkeys(build_bindings(keys, self.log))
        save_config(self.cfg)

    def set_region(self, region):
        self.cfg["regiao"] = region
        self._reset_tracking()
        save_config(self.cfg)

    def toggle(self):
        if not self.cfg["regiao"]:
            self.log("Calibre a região antes de ligar.")
            return
        self.active = not self.active
        self._reset_tracking()
        self.on_event("estado", self.active)
        self._beep(self.active)

    def request(self, what):
        """'calibrar' ou 'debug': o print é tirado na thread do bot."""
        self.requests.put(what)

    # ---- internos ----
    def log(self, msg):
        self.on_event("log", msg)

    def _reset_tracking(self):
        self.last_pos = None
        self.last_press = 0.0
        self.last_seen = 0.0

    @staticmethod
    def _beep(on):
        # retorno sonoro, já que dentro do jogo não dá pra ver o launcher
        try:
            import winsound
            threading.Thread(target=winsound.Beep,
                             args=(1200 if on else 600, 90), daemon=True).start()
        except Exception:
            pass

    def _run(self):
        try:
            with _new_mss() as sct:
                self._loop(sct)
        except Exception:
            self.active = False
            self.on_event("erro", traceback.format_exc())

    def _handle_requests(self, sct):
        while True:
            try:
                what = self.requests.get_nowait()
            except queue.Empty:
                return
            if what == "calibrar":
                x, y = cursor_pos()
                mon = next((m for m in sct.monitors[1:]
                            if m["left"] <= x < m["left"] + m["width"]
                            and m["top"] <= y < m["top"] + m["height"]),
                           sct.monitors[1])
                shot = sct.grab(mon)
                png = mss.tools.to_png(shot.rgb, shot.size, level=1)
                self.on_event("calibrar", (png, dict(mon)))
            elif what == "debug":
                region = self.cfg["regiao"]
                if not region:
                    self.log("Calibre a região antes de testar.")
                    continue
                shot = sct.grab(region)
                png = mss.tools.to_png(shot.rgb, shot.size)
                with open(DEBUG_PNG, "wb") as f:
                    f.write(png)
                self.on_event("debug", (png, detect(np.array(shot))))

    def _loop(self, sct):
        while not self._stop.is_set():
            if not self.capturing:
                hk = self.hk
                if hk.pressed("ligar_desligar"):
                    self.toggle()
                if hk.pressed("calibrar"):
                    self.request("calibrar")
                if hk.pressed("debug"):
                    self.request("debug")
            self._handle_requests(sct)

            region = self.cfg["regiao"]
            if not self.active or not region:
                time.sleep(0.03)
                continue

            res = detect(np.array(sct.grab(region)))
            now = time.time()

            if res is None:
                if now - self.last_seen > 0.4:
                    self.last_pos = None  # minigame sumiu / nova rodada
                time.sleep(0.01)
                continue

            self.last_seen = now
            direction, pos = res

            same_box = self.last_pos is not None and abs(pos - self.last_pos) < 5
            if same_box and now - self.last_press < RETRY_AFTER:
                time.sleep(0.005)
                continue

            time.sleep(random.uniform(DELAY_MIN, DELAY_MAX))
            tap(direction)
            self.last_pos = pos
            self.last_press = time.time()
            self.on_event("tecla", direction)
