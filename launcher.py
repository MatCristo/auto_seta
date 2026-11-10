"""
launcher.py - Janela do auto_seta.

Tudo que antes era só por atalho dá pra fazer aqui:
  - ligar / desligar o bot
  - calibrar a região (arrastando um retângulo num print congelado da tela)
  - testar a detecção (mostra o print da região e a seta encontrada)
  - trocar as teclas de atalho (clica no botão e aperta a tecla nova)

O bot roda numa thread separada; ele manda eventos por uma fila e a janela
lê essa fila a cada 30 ms (o tkinter não pode ser mexido de outra thread).
"""

import base64
import queue
import time
import tkinter as tk
from tkinter import messagebox

import auto_seta as core

# ---------------------------------------------------------------- visual
BG = "#16181d"
PANEL = "#1f2229"
LINE = "#2c3039"
TEXT = "#e6e8ee"
MUTED = "#8b919e"
GREEN = "#3ecf6e"
RED = "#e5534b"
YELLOW = "#e3b341"
ACCENT = "#4c8dff"

FONT = ("Segoe UI", 10)
FONT_B = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 15, "bold")
FONT_SMALL = ("Segoe UI", 9)
FONT_MONO = ("Consolas", 9)

ARROW = {"up": "▲", "down": "▼", "left": "◀", "right": "▶"}


def button(master, text, command, bg=PANEL, fg=TEXT, **kw):
    b = tk.Button(master, text=text, command=command, bg=bg, fg=fg,
                  activebackground=LINE, activeforeground=TEXT,
                  relief="flat", bd=0, padx=12, pady=6, font=FONT,
                  cursor="hand2", highlightthickness=0, **kw)
    return b


def section(master, title):
    frame = tk.Frame(master, bg=PANEL, padx=14, pady=12,
                     highlightbackground=LINE, highlightthickness=1)
    frame.pack(fill="x", pady=(0, 10))
    tk.Label(frame, text=title.upper(), bg=PANEL, fg=MUTED,
             font=("Segoe UI", 8, "bold")).pack(anchor="w", pady=(0, 8))
    return frame


# ---------------------------------------------------------------- seleção
class RegionSelector(tk.Toplevel):
    """Print congelado em tela cheia; arraste um retângulo em volta do painel."""

    def __init__(self, master, png, mon, on_done):
        super().__init__(master)
        self.mon, self.on_done = mon, on_done
        self.overrideredirect(True)
        self.attributes("-topmost", True)
        self.geometry(f"{mon['width']}x{mon['height']}+{mon['left']}+{mon['top']}")

        self.img = tk.PhotoImage(data=base64.b64encode(png))
        self.cv = tk.Canvas(self, width=mon["width"], height=mon["height"],
                            highlightthickness=0, cursor="crosshair", bg="black")
        self.cv.pack()
        self.cv.create_image(0, 0, image=self.img, anchor="nw")

        msg = ("Arraste um retângulo em volta do painel das setas  •  "
               "Esc cancela")
        tx = mon["width"] // 2
        self.cv.create_rectangle(tx - 300, 14, tx + 300, 50, fill="#000000",
                                 outline=YELLOW, width=2)
        self.cv.create_text(tx, 32, text=msg, fill="white", font=FONT_B)

        self.start = None
        self.rect = None
        self.cv.bind("<ButtonPress-1>", self._press)
        self.cv.bind("<B1-Motion>", self._drag)
        self.cv.bind("<ButtonRelease-1>", self._release)
        self.bind("<Escape>", lambda e: self._finish(None))
        self.after(50, self._grab_focus)

    def _grab_focus(self):
        self.lift()
        self.focus_force()
        try:
            self.grab_set()
        except tk.TclError:
            pass

    def _press(self, e):
        self.start = (e.x, e.y)
        if self.rect:
            self.cv.delete(self.rect)
        self.rect = self.cv.create_rectangle(e.x, e.y, e.x, e.y,
                                             outline=GREEN, width=2)

    def _drag(self, e):
        if self.start:
            self.cv.coords(self.rect, *self.start, e.x, e.y)

    def _release(self, e):
        if not self.start:
            return
        x0, y0 = self.start
        left, top = min(x0, e.x), min(y0, e.y)
        w, h = abs(e.x - x0), abs(e.y - y0)
        if w < 30 or h < 15:
            self.start = None
            return  # clique sem arrastar: ignora e deixa tentar de novo
        self._finish({"left": self.mon["left"] + left,
                      "top": self.mon["top"] + top,
                      "width": w, "height": h})

    def _finish(self, region):
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        self.on_done(region)


# ---------------------------------------------------------------- janela
class Launcher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("auto_seta")
        self.configure(bg=BG)
        self.resizable(False, True)
        self.minsize(460, 560)

        self.events = queue.Queue()
        cfg, erro = core.load_config()
        self.bot = core.Bot(cfg, lambda kind, data: self.events.put((kind, data)))
        core.save_config(cfg)  # cria/completa o config.json
        self.preview_img = None
        self.capture = None
        self.key_buttons = {}
        self.presses = 0

        self._build()
        self._refresh_all()
        if erro:
            self.log(erro)
        if not core.is_admin():
            self.admin_lbl.pack(fill="x", pady=(0, 10))
        self.log("Pronto. Calibre a região com o minigame aberto na tela.")

        self.bot.start()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(30, self._poll_events)

    # ------------------------------------------------------------ layout
    def _build(self):
        root = tk.Frame(self, bg=BG, padx=16, pady=14)
        root.pack(fill="both", expand=True)

        head = tk.Frame(root, bg=BG)
        head.pack(fill="x", pady=(0, 12))
        tk.Label(head, text="auto_seta", bg=BG, fg=TEXT,
                 font=FONT_TITLE).pack(side="left")
        tk.Label(head, text="minigame de setas", bg=BG, fg=MUTED,
                 font=FONT_SMALL).pack(side="left", padx=(8, 0), pady=(6, 0))

        self.admin_lbl = tk.Label(
            root, bg="#3a2a12", fg=YELLOW, font=FONT_SMALL, justify="left",
            anchor="w", padx=10, pady=6, wraplength=420,
            text="Sem administrador: se as setas não chegarem ao jogo, feche e "
                 "abra com \"Executar como administrador\".")

        # --- status
        s = section(root, "Bot")
        row = tk.Frame(s, bg=PANEL)
        row.pack(fill="x")
        self.dot = tk.Canvas(row, width=14, height=14, bg=PANEL,
                             highlightthickness=0)
        self.dot.pack(side="left")
        self.dot_id = self.dot.create_oval(2, 2, 12, 12, fill=RED, outline="")
        self.status_lbl = tk.Label(row, text="DESLIGADO", bg=PANEL, fg=TEXT,
                                   font=FONT_B)
        self.status_lbl.pack(side="left", padx=(6, 0))
        self.toggle_btn = button(row, "Ligar", self._toggle, bg=GREEN,
                                 fg="#0b1a10")
        self.toggle_btn.pack(side="right")
        self.count_lbl = tk.Label(s, text="", bg=PANEL, fg=MUTED,
                                  font=FONT_SMALL, anchor="w")
        self.count_lbl.pack(fill="x", pady=(6, 0))

        # --- região
        s = section(root, "Região da tela")
        self.region_lbl = tk.Label(s, text="", bg=PANEL, fg=TEXT, font=FONT,
                                   anchor="w")
        self.region_lbl.pack(fill="x")
        tk.Label(s, bg=PANEL, fg=MUTED, font=FONT_SMALL, anchor="w",
                 justify="left", wraplength=420,
                 text="Com o minigame na tela, aperte a tecla de calibrar: a tela "
                      "congela e você arrasta um retângulo em volta do painel.").pack(
            fill="x", pady=(4, 8))
        row = tk.Frame(s, bg=PANEL)
        row.pack(fill="x")
        self.calib_btn = button(row, "Calibrar em 3 s", self._calibrate_delayed)
        self.calib_btn.pack(side="left")
        self.debug_btn = button(row, "Testar detecção", self._debug)
        self.debug_btn.pack(side="left", padx=(8, 0))

        self.preview = tk.Label(s, bg="#0d0f12", fg=MUTED, font=FONT_SMALL,
                                text="(a prévia aparece aqui ao testar)",
                                height=5)
        self.preview.pack(fill="x", pady=(10, 0))
        self.result_lbl = tk.Label(s, text="", bg=PANEL, fg=TEXT, font=FONT_B,
                                   anchor="w")
        self.result_lbl.pack(fill="x", pady=(6, 0))

        # --- teclas
        s = section(root, "Teclas de atalho")
        for action, label in core.KEY_LABELS.items():
            row = tk.Frame(s, bg=PANEL)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, bg=PANEL, fg=TEXT, font=FONT,
                     anchor="w").pack(side="left")
            b = button(row, "", lambda a=action: self._start_capture(a),
                       bg=LINE, width=22)
            b.configure(font=FONT_B)
            b.pack(side="right")
            self.key_buttons[action] = b
        row = tk.Frame(s, bg=PANEL)
        row.pack(fill="x", pady=(8, 0))
        tk.Label(row, text="Clique e aperte a tecla nova (Esc cancela).",
                 bg=PANEL, fg=MUTED, font=FONT_SMALL).pack(side="left")
        button(row, "Restaurar padrão", self._reset_keys,
               bg=PANEL, fg=MUTED).pack(side="right")

        # --- log
        s = section(root, "Registro")
        s.pack_configure(fill="both", expand=True, pady=0)
        self.log_txt = tk.Text(s, height=7, bg="#0d0f12", fg=MUTED,
                               font=FONT_MONO, relief="flat", bd=0,
                               wrap="word", state="disabled", padx=8, pady=6)
        self.log_txt.pack(fill="both", expand=True)

    # ------------------------------------------------------------ helpers
    def log(self, msg):
        self.log_txt.configure(state="normal")
        self.log_txt.insert("end", time.strftime("%H:%M:%S  ") + msg + "\n")
        self.log_txt.see("end")
        self.log_txt.configure(state="disabled")

    def _keys(self):
        return self.bot.cfg["teclas"]

    def _refresh_all(self):
        keys = self._keys()
        on = self.bot.active
        self.dot.itemconfigure(self.dot_id, fill=GREEN if on else RED)
        self.status_lbl.configure(text="LIGADO" if on else "DESLIGADO")
        self.toggle_btn.configure(
            text=f"{'Desligar' if on else 'Ligar'}  ({keys['ligar_desligar']})",
            bg=RED if on else GREEN, fg="#1a0b0b" if on else "#0b1a10")
        self.debug_btn.configure(text=f"Testar detecção  ({keys['debug']})")

        r = self.bot.cfg["regiao"]
        if r:
            self.region_lbl.configure(
                fg=TEXT, text=f"x {r['left']}, y {r['top']}  •  "
                              f"{r['width']} × {r['height']} px")
        else:
            self.region_lbl.configure(
                fg=YELLOW, text=f"Não calibrada. Aperte {keys['calibrar']} "
                                f"com o minigame na tela.")

        for action, b in self.key_buttons.items():
            if not (self.capture and self.capture["action"] == action):
                b.configure(text=keys[action], bg=LINE, fg=TEXT)

    # ------------------------------------------------------------ ações
    def _toggle(self):
        self.bot.toggle()

    def _debug(self):
        self.bot.request("debug")

    def _calibrate_delayed(self):
        """Dá 3 s pra pessoa voltar pro jogo antes de congelar a tela."""
        self.calib_btn.configure(state="disabled")

        def tick(n):
            if n == 0:
                self.calib_btn.configure(text="Calibrar em 3 s", state="normal")
                self.bot.request("calibrar")
                return
            self.calib_btn.configure(text=f"Congelando em {n}…")
            self.after(1000, tick, n - 1)

        self.iconify()
        tick(3)

    def _open_selector(self, png, mon):
        def done(region):
            self.deiconify()
            if region:
                self.bot.set_region(region)
                self.log(f"Região salva: {region['width']}×{region['height']} "
                         f"em ({region['left']}, {region['top']}).")
                self._refresh_all()
                self.bot.request("debug")  # já mostra a prévia
            else:
                self.log("Calibração cancelada.")

        RegionSelector(self, png, mon, done)

    def _show_debug(self, png, res):
        img = tk.PhotoImage(data=base64.b64encode(png))
        factor = max(1, -(-img.width() // 420))  # arredonda pra cima
        if factor > 1:
            img = img.subsample(factor)
        self.preview_img = img
        self.preview.configure(image=img, text="", height=img.height())
        if res:
            d = res[0]
            self.result_lbl.configure(
                fg=GREEN, text=f"Seta da vez: {ARROW[d]}  {core.DIR_PT[d]}")
            self.log(f"Teste: detectou {core.DIR_PT[d]} (debug.png salvo).")
        else:
            self.result_lbl.configure(
                fg=YELLOW, text="Nenhuma seta cinza encontrada nesse print.")
            self.log("Teste: nada detectado (debug.png salvo). Normal se o "
                     "minigame não estava aberto.")

    # ------------------------------------------------------------ teclas
    def _start_capture(self, action):
        if self.capture:
            return
        self.bot.capturing = True
        self.capture = {"action": action, "armed": False}
        self.key_buttons[action].configure(text="aperte uma tecla…",
                                           bg=ACCENT, fg="white")
        self.after(20, self._poll_capture)

    def _poll_capture(self):
        cap = self.capture
        if not cap:
            return
        down = core.key_down
        pressed = [vk for vk in core.CAPTURE_VKS if down(vk)]

        # espera soltar tudo (inclusive o clique que abriu a captura)
        if not cap["armed"]:
            if not pressed and not down(0x01) and not down(0x1B):
                cap["armed"] = True
            self.after(20, self._poll_capture)
            return

        if down(0x1B):
            self._end_capture(None)
            return
        if not pressed:
            self.after(20, self._poll_capture)
            return

        mods = [name for name, vk in core.MOD_NAMES.items() if down(vk)]
        self._end_capture("+".join(mods + [core.VK_TO_NAME[pressed[0]]]))

    def _end_capture(self, text):
        action = self.capture["action"]
        self.capture = None
        if text:
            other = next((a for a, t in self._keys().items()
                          if a != action and core.same_binding(t, text)), None)
            if other:
                self.log(f"{text} já é usada em '{core.KEY_LABELS[other]}'.")
            else:
                keys = dict(self._keys())
                keys[action] = text
                self.bot.set_keys(keys)
                self.log(f"'{core.KEY_LABELS[action]}' agora é {text}.")
                if len(text) == 1:
                    self.log("Dica: letra sozinha também dispara quando você "
                             "digita no chat do jogo.")
        # recria os atalhos com o estado atual, pra tecla recém-apertada
        # não disparar a ação na hora
        self.bot.set_keys(self._keys())
        self.bot.capturing = False
        self._refresh_all()

    def _reset_keys(self):
        self.bot.set_keys(dict(core.DEFAULT_KEYS))
        self.log("Teclas restauradas para o padrão.")
        self._refresh_all()

    # ------------------------------------------------------------ eventos
    def _poll_events(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == "log":
                    self.log(data)
                elif kind == "estado":
                    self.log("Bot ligado." if data else "Bot desligado.")
                    self._refresh_all()
                elif kind == "tecla":
                    self.presses += 1
                    self.count_lbl.configure(
                        text=f"Última: {ARROW[data]} {core.DIR_PT[data]}  •  "
                             f"{self.presses} setas apertadas")
                elif kind == "calibrar":
                    self._open_selector(*data)
                elif kind == "debug":
                    self._show_debug(*data)
                elif kind == "erro":
                    self.log("ERRO no bot:\n" + data)
                    self._refresh_all()
                    messagebox.showerror(
                        "auto_seta", "O bot parou por um erro. Veja o registro.")
        except queue.Empty:
            pass
        self.after(30, self._poll_events)

    def _close(self):
        self.bot.stop()
        self.destroy()


def main():
    try:
        Launcher().mainloop()
    except Exception:
        import traceback
        messagebox.showerror("auto_seta", traceback.format_exc())


if __name__ == "__main__":
    main()
