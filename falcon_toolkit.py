"""
FALCON SUPER TOOLKIT v1.0.1 - Advanced Animated Edition
Developer: Paul Mendoza (Python port)
Requires: customtkinter, psutil, Pillow
Run as Administrator for full functionality.
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import subprocess
import platform
import threading
import time
import random
import math
import sys
import os
import json
import ctypes
import webbrowser
from datetime import datetime

try:
    import psutil
except ImportError:
    psutil = None

try:
    from PIL import Image, ImageTk, ImageChops, ImageFilter
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


# ─────────────────────────────────────────────────────────────
#  ASSET PATHS
# ─────────────────────────────────────────────────────────────
def _asset_path(filename):
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "assets", filename)


def _data_path(filename):
    """Writable location for user settings (next to exe, or %APPDATA%)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


LOGO_PNG = _asset_path("falcon_logo.png")
LOGO_ICO = _asset_path("falcon_logo.ico")
SETTINGS_FILE = _data_path("falcon_settings.json")

APP_VERSION = "1.0.1"
APP_DEVELOPER = "Paul Mendoza"
APP_GITHUB = "https://github.com/paulmendoza24"


# ─────────────────────────────────────────────────────────────
#  SETTINGS STORE
# ─────────────────────────────────────────────────────────────
DEFAULT_SETTINGS = {
    "confirm_winutil": True,
    "confirm_mas": True,
    "animate_background": True,
    "typewriter_effect": True,
    "stats_refresh_ms": 1500,
    "start_maximized": False,
}


def load_settings():
    """Load settings from disk, merged with defaults."""
    settings = dict(DEFAULT_SETTINGS)
    try:
        if os.path.isfile(SETTINGS_FILE):
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            if isinstance(saved, dict):
                settings.update({k: v for k, v in saved.items()
                                 if k in DEFAULT_SETTINGS})
    except Exception as e:
        print(f"[Falcon] Could not load settings: {e}")
    return settings


def save_settings(settings):
    """Persist settings to disk."""
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        print(f"[Falcon] Could not save settings: {e}")
        return False


# ─────────────────────────────────────────────────────────────
#  THEME
# ─────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

COLORS = {
    "bg":         "#05070f",
    "bg_alt":     "#0a0f1e",
    "card":       "#0e1526",
    "card_hover": "#16203a",
    "accent":     "#00e5ff",
    "accent2":    "#a855f7",
    "accent3":    "#38bdf8",
    "success":    "#22c55e",
    "warning":    "#f59e0b",
    "danger":     "#ef4444",
    "text":       "#e5e7eb",
    "text_dim":   "#7c8ba3",
    "border":     "#1e293b",
    "glow":       "#00e5ff",
}

FONT_TITLE = ("Segoe UI", 28, "bold")
FONT_HEAD  = ("Segoe UI", 17, "bold")
FONT_BODY  = ("Segoe UI", 13)
FONT_SMALL = ("Segoe UI", 11)
FONT_MONO  = ("Consolas", 12)
FONT_LOGO  = ("Segoe UI", 34, "bold")


# ─────────────────────────────────────────────────────────────
#  LOGO PROCESSING HELPERS
# ─────────────────────────────────────────────────────────────
def _strip_white_background(img: "Image.Image", threshold: int = 18) -> "Image.Image":
    img = img.convert("RGBA")
    rgb = img.convert("RGB")
    white = Image.new("RGB", rgb.size, (255, 255, 255))
    diff = ImageChops.difference(rgb, white)
    r, g, b = diff.split()
    alpha = ImageChops.darker(ImageChops.darker(r, g), b)
    alpha = alpha.point(lambda p: 0 if p < threshold else min(255, int(p * 1.35)))
    existing = img.split()[3]
    final_alpha = existing if existing.getbbox() else alpha
    img.putalpha(final_alpha)
    return img


def _premultiply_glow(img: "Image.Image", color=(0, 229, 255),
                      spread: int = 6, intensity: float = 0.35) -> "Image.Image":
    w, h = img.size
    canvas = Image.new("RGBA", (w + spread * 2, h + spread * 2), (0, 0, 0, 0))
    glow = img.split()[3].filter(ImageFilter.GaussianBlur(spread))
    glow = glow.point(lambda p: int(p * intensity))
    glow_layer = Image.new("RGBA", glow.size, color + (0,))
    glow_layer.putalpha(glow)
    canvas.alpha_composite(glow_layer, (spread, spread))
    canvas.alpha_composite(img, (spread, spread))
    return canvas


# ─────────────────────────────────────────────────────────────
#  ICON HELPER
# ─────────────────────────────────────────────────────────────
def set_window_icon(window, size_hint: int = 32) -> bool:
    if os.name == "nt" and os.path.isfile(LOGO_ICO):
        try:
            window.iconbitmap(default=LOGO_ICO)
            return True
        except Exception as e:
            print(f"[Falcon] iconbitmap failed ({e}); falling back to PNG")
    if PIL_AVAILABLE and os.path.isfile(LOGO_PNG):
        try:
            base = Image.open(LOGO_PNG).convert("RGBA")
            base = _strip_white_background(base, threshold=18)
            photo = ImageTk.PhotoImage(
                base.resize((size_hint, size_hint), Image.LANCZOS))
            window.iconphoto(True, photo)
            window._icon_ref = photo
            return True
        except Exception as e:
            print(f"[Falcon] iconphoto failed: {e}")
    print("[Falcon] No icon available — window will show default Tk icon")
    return False


# ─────────────────────────────────────────────────────────────
#  BACKGROUND
# ─────────────────────────────────────────────────────────────
class ConstellationBackground(tk.Canvas):
    def __init__(self, master, **kwargs):
        super().__init__(master, highlightthickness=0, **kwargs)
        self.configure(bg=COLORS["bg"])
        self.width, self.height = 1280, 800
        self.nodes = []
        self._animating = True
        self._t = 0.0
        self._gradient_ids = []

        self.bind("<Configure>", self._on_resize)
        self._build_gradient()
        self._spawn_nodes()
        self._animate()

    def _on_resize(self, e):
        if e.width < 20 or e.height < 20:
            return
        self.width, self.height = e.width, e.height
        self.delete("all")
        self._gradient_ids.clear()
        self._build_gradient()
        self._spawn_nodes()

    def _build_gradient(self):
        steps = 90
        for i in range(steps):
            f = i / steps
            r = int(5 + 40 * math.sin(f * math.pi) ** 2)
            g = int(8 + 60 * math.sin(f * math.pi * 1.5) ** 2)
            b = int(20 + 90 * math.sin(f * math.pi * 0.8) ** 2)
            y0 = int(self.height * i / steps)
            y1 = int(self.height * (i + 1) / steps) + 1
            rid = self.create_rectangle(0, y0, self.width, y1,
                                        fill=f"#{r:02x}{g:02x}{b:02x}",
                                        outline="", tags="grad")
            self._gradient_ids.append(rid)

    def _spawn_nodes(self):
        self.delete("node", "link", "halo")
        self.nodes.clear()
        count = max(28, (self.width * self.height) // 26000)
        for _ in range(count):
            self.nodes.append({
                "x": random.uniform(0, self.width),
                "y": random.uniform(0, self.height),
                "vx": random.uniform(-0.4, 0.4),
                "vy": random.uniform(-0.4, 0.4),
                "r": random.uniform(1.4, 3.2),
                "color": random.choice([COLORS["accent"], COLORS["accent2"],
                                        COLORS["accent3"], "#67e8f9"]),
                "pulse": random.random(),
            })

    def _animate(self):
        if not self._animating:
            return
        self._t += 0.016
        w, h = self.width, self.height
        self.delete("link", "halo")

        for n in self.nodes:
            pulse = 0.6 + 0.4 * math.sin(self._t * 2 + n["pulse"] * 6.28)
            r = n["r"] * 3.2 * pulse
            self.create_oval(n["x"] - r, n["y"] - r, n["x"] + r, n["y"] + r,
                             fill="", outline=n["color"], width=1, tags="halo")

        nodes = self.nodes
        for i in range(len(nodes)):
            a = nodes[i]
            for j in range(i + 1, len(nodes)):
                b = nodes[j]
                dx, dy = a["x"] - b["x"], a["y"] - b["y"]
                d2 = dx * dx + dy * dy
                if d2 < 130 * 130:
                    d = math.sqrt(d2)
                    alpha = max(0.0, 1 - d / 130)
                    color = self._blend(COLORS["bg"], COLORS["accent"], alpha * 0.55)
                    self.create_line(a["x"], a["y"], b["x"], b["y"],
                                     fill=color, width=1, tags="link")

        self.delete("node")
        for n in nodes:
            n["x"] += n["vx"]
            n["y"] += n["vy"]
            if n["x"] < 0 or n["x"] > w:
                n["vx"] *= -1
            if n["y"] < 0 or n["y"] > h:
                n["vy"] *= -1
            n["x"] = max(0, min(w, n["x"]))
            n["y"] = max(0, min(h, n["y"]))
            self.create_oval(n["x"] - n["r"], n["y"] - n["r"],
                             n["x"] + n["r"], n["y"] + n["r"],
                             fill=n["color"], outline="", tags="node")

        self.after(16, self._animate)

    @staticmethod
    def _blend(c1, c2, t):
        c1 = c1.lstrip("#"); c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        return f"#{r:02x}{g:02x}{b:02x}"


# ─────────────────────────────────────────────────────────────
#  RIPPLE BUTTON
# ─────────────────────────────────────────────────────────────
class RippleButton(ctk.CTkFrame):
    def __init__(self, master, title, subtitle, icon, command=None,
                 accent=COLORS["accent"], delay=0, **kwargs):
        super().__init__(master, fg_color=COLORS["card"],
                         corner_radius=16, border_width=1,
                         border_color=COLORS["border"], **kwargs)
        self.command = command
        self.accent = accent
        self._hovered = False

        self.grid_propagate(False)
        self.configure(height=118)

        self.strip = ctk.CTkFrame(self, width=4, fg_color=accent, corner_radius=2)
        self.strip.pack(side="left", fill="y", padx=(10, 0), pady=14)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(side="left", fill="both", expand=True, padx=16, pady=14)

        top = ctk.CTkFrame(body, fg_color="transparent")
        top.pack(fill="x")

        self.icon_lbl = ctk.CTkLabel(top, text=icon, font=("Segoe UI", 22),
                                     text_color=accent, width=30,
                                     fg_color="transparent")
        self.icon_lbl.pack(side="left")

        self.title_lbl = ctk.CTkLabel(top, text=title, font=FONT_HEAD,
                                      text_color=COLORS["text"], anchor="w",
                                      fg_color="transparent")
        self.title_lbl.pack(side="left", padx=(10, 0))

        self.arrow = ctk.CTkLabel(top, text="›", font=("Segoe UI", 22, "bold"),
                                  text_color=COLORS["text_dim"], width=20,
                                  fg_color="transparent")
        self.arrow.pack(side="right")

        self.sub_lbl = ctk.CTkLabel(body, text=subtitle, font=FONT_SMALL,
                                    text_color=COLORS["text_dim"], anchor="w",
                                    fg_color="transparent")
        self.sub_lbl.pack(fill="x", padx=(40, 0), pady=(2, 0))

        for w in (self, body, top, self.icon_lbl, self.title_lbl,
                  self.sub_lbl, self.strip, self.arrow):
            w.bind("<Enter>", self._on_enter)
            w.bind("<Leave>", self._on_leave)
            w.bind("<Button-1>", self._on_click)
            try:
                w.configure(cursor="hand2")
            except Exception:
                pass

    def _on_enter(self, _):
        if self._hovered:
            return
        self._hovered = True
        self.configure(border_color=self.accent, fg_color=COLORS["card_hover"])
        try:
            self.arrow.configure(text_color=self.accent)
        except Exception:
            pass

    def _on_leave(self, _):
        self._hovered = False
        self.configure(border_color=COLORS["border"], fg_color=COLORS["card"])
        try:
            self.arrow.configure(text_color=COLORS["text_dim"])
        except Exception:
            pass

    def _on_click(self, _):
        try:
            self.configure(border_color=self.accent,
                           fg_color=self._blend(self.accent, COLORS["card"], 0.85))
            self.after(120, lambda: self.configure(
                fg_color=COLORS["card_hover"], border_color=self.accent))
        except Exception:
            pass
        if self.command:
            self.after(60, self.command)

    @staticmethod
    def _blend(c1, c2, t):
        c1 = c1.lstrip("#"); c2 = c2.lstrip("#")
        r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
        r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
        return f"#{int(r1+(r2-r1)*t):02x}{int(g1+(g2-g1)*t):02x}{int(b1+(b2-b1)*t):02x}"


# ─────────────────────────────────────────────────────────────
#  STAT RING
# ─────────────────────────────────────────────────────────────
class StatRing(tk.Canvas):
    def __init__(self, master, label, color, size=76, **kwargs):
        super().__init__(master, width=size, height=size,
                         highlightthickness=0, bg=COLORS["card"], **kwargs)
        self.size = size
        self.label = label
        self.color = color
        self.value = 0.0
        self._target = 0.0
        self._draw()
        self._tick()

    def set_value(self, v):
        self._target = max(0.0, min(100.0, float(v)))
        if self._target > 80:
            self.color = COLORS["danger"]
        elif self._target > 60:
            self.color = COLORS["warning"]
        else:
            self.color = COLORS["accent"] if self.label == "CPU" else COLORS["accent2"]

    def _draw(self):
        self.delete("all")
        c = self.size / 2
        r = c - 8
        self.create_oval(c - r, c - r, c + r, c + r,
                         outline=COLORS["border"], width=6)
        extent = -359.9 * (self.value / 100.0)
        if self.value > 0.5:
            self.create_arc(c - r, c - r, c + r, c + r,
                            start=90, extent=extent,
                            outline=self.color, width=6, style="arc")
            self.create_arc(c - r - 3, c - r - 3, c + r + 3, c + r + 3,
                            start=90, extent=extent,
                            outline=self.color, width=1, style="arc")
        self.create_text(c, c - 4, text=f"{int(self.value)}%",
                         fill=COLORS["text"], font=("Segoe UI", 15, "bold"))
        self.create_text(c, c + 14, text=self.label,
                         fill=COLORS["text_dim"], font=("Segoe UI", 9, "bold"))

    def _tick(self):
        diff = self._target - self.value
        if abs(diff) > 0.3:
            self.value += diff * 0.18
            self._draw()
        self.after(30, self._tick)


# ─────────────────────────────────────────────────────────────
#  TOAST
# ─────────────────────────────────────────────────────────────
class Toast(ctk.CTkToplevel):
    def __init__(self, master, message, kind="info"):
        super().__init__(master)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        color = {"info": COLORS["accent"], "success": COLORS["success"],
                 "warn": COLORS["warning"], "error": COLORS["danger"]}[kind]

        frame = ctk.CTkFrame(self, fg_color=COLORS["card"],
                             corner_radius=12, border_width=1, border_color=color)
        frame.pack(fill="both", expand=True)

        ctk.CTkFrame(frame, width=4, fg_color=color, corner_radius=2
                     ).pack(side="left", fill="y", padx=(6, 0), pady=8)
        ctk.CTkLabel(frame, text=message, font=FONT_BODY,
                     text_color=COLORS["text"], fg_color="transparent"
                     ).pack(padx=16, pady=14)

        self.update_idletasks()
        w, h = self.winfo_reqwidth(), self.winfo_reqheight()
        x = master.winfo_x() + master.winfo_width() - w - 30
        y = master.winfo_y() + master.winfo_height() - h - 30

        self.geometry(f"{w}x{h}+{x}+{y+60}")
        self.attributes("-alpha", 0.0)
        self._fade_in(x, y, w, h)

    def _fade_in(self, x, y, w, h):
        for i in range(24):
            try:
                self.attributes("-alpha", i / 24)
                self.geometry(f"{w}x{h}+{x}+{y + 60 - i * 2}")
                self.update()
                time.sleep(0.012)
            except tk.TclError:
                return
        self.after(2400, self._fade_out)

    def _fade_out(self):
        try:
            for i in range(24, 0, -1):
                self.attributes("-alpha", i / 24)
                self.update()
                time.sleep(0.01)
            self.destroy()
        except Exception:
            pass
# ─────────────────────────────────────────────────────────────
#  SPLASH SCREEN (3 seconds)
# ─────────────────────────────────────────────────────────────
class SplashScreen(ctk.CTkToplevel):
    """Frameless centered splash shown for DURATION ms before main app."""

    DURATION_MS = 3000
    WIDTH  = 480
    HEIGHT = 300

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)          # no title bar / borders
        self.attributes("-topmost", True)
        self.configure(fg_color=COLORS["bg"])
        self.resizable(False, False)

        # ── Center on primary screen ──
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - self.WIDTH) // 2
        y = (sh - self.HEIGHT) // 2
        self.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        # ── Soft border + rounded card ──
        card = ctk.CTkFrame(self, fg_color=COLORS["card"],
                            corner_radius=20, border_width=2,
                            border_color=COLORS["accent"])
        card.pack(fill="both", expand=True, padx=2, pady=2)

        # ── Logo (or glyph fallback) ──
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(expand=True, fill="both", padx=24, pady=20)

        self._splash_img = None
        if PIL_AVAILABLE and os.path.isfile(LOGO_PNG):
            try:
                base = Image.open(LOGO_PNG).convert("RGBA")
                base = _strip_white_background(base, threshold=18)
                h = 130
                w = int(base.width * (h / base.height))
                img = base.resize((w, h), Image.LANCZOS)
                img = _premultiply_glow(img, color=(0, 229, 255),
                                        spread=8, intensity=0.45)
                self._splash_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=img.size)
                ctk.CTkLabel(inner, text="", image=self._splash_img,
                             fg_color="transparent"
                             ).pack(pady=(4, 8))
            except Exception as e:
                print(f"[Falcon] Splash logo failed: {e}")

        if self._splash_img is None:
            ctk.CTkLabel(inner, text="◈", font=("Segoe UI", 72, "bold"),
                         text_color=COLORS["accent"], fg_color="transparent"
                         ).pack(pady=(10, 4))

        ctk.CTkLabel(inner, text="FALCON SUPER TOOLKIT",
                     font=("Segoe UI", 22, "bold"),
                     text_color=COLORS["text"], fg_color="transparent"
                     ).pack()
        ctk.CTkLabel(inner, text=f"v{APP_VERSION}  •  Initializing...",
                     font=("Segoe UI", 11),
                     text_color=COLORS["text_dim"], fg_color="transparent"
                     ).pack(pady=(2, 14))

        # ── Loading bar ──
        self.bar = ctk.CTkProgressBar(card, height=6,
                                      corner_radius=3,
                                      fg_color=COLORS["border"],
                                      progress_color=COLORS["accent"])
        self.bar.pack(fill="x", padx=32, pady=(0, 18))
        self.bar.set(0.0)

        # ── Animate ──
        self._start_time = time.time()
        self._animate_bar()

    def _animate_bar(self):
        elapsed = (time.time() - self._start_time) * 1000  # ms
        progress = min(1.0, elapsed / self.DURATION_MS)
        try:
            self.bar.set(progress)
        except tk.TclError:
            return

        if progress >= 1.0:
            self._fade_out()
            return

        # Let the main window keep building underneath
        try:
            self.update()
        except tk.TclError:
            return
        self.after(16, self._animate_bar)

    def _fade_out(self):
        """Smoothly fade the splash out, then destroy it."""
        try:
            steps = 12
            for i in range(steps, -1, -1):
                self.attributes("-alpha", i / steps)
                self.update()
                time.sleep(0.012)
            self.destroy()
        except tk.TclError:
            pass

# ─────────────────────────────────────────────────────────────
#  SETTINGS WINDOW
# ─────────────────────────────────────────────────────────────
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, settings_store, on_save):
        super().__init__(master)
        self.title("Settings — Falcon Super Toolkit")
        self.geometry("620x680")
        self.configure(fg_color=COLORS["bg_alt"])
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        set_window_icon(self, size_hint=32)

        self.settings = dict(settings_store)
        self.on_save = on_save
        self.vars = {}

        self._fade_in()
        self._build_ui()

    def _fade_in(self):
        self.attributes("-alpha", 0.0)
        for i in range(16):
            try:
                self.attributes("-alpha", i / 16)
                self.update()
                time.sleep(0.008)
            except tk.TclError:
                return

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=64)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="  ⚙️  SETTINGS",
                     font=("Segoe UI", 18, "bold"),
                     text_color=COLORS["accent"], fg_color="transparent"
                     ).pack(side="left", padx=22, pady=18)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        # ── Section: Behaviour ──
        self._section(body, "BEHAVIOUR")
        self._switch(body, "confirm_winutil",
                     "Confirm before launching WinUtil",
                     "Show a confirmation dialog before running Chris Titus' script.")
        self._switch(body, "confirm_mas",
                     "Confirm before launching MAS",
                     "Show a confirmation dialog before running Massgrave.")
        self._switch(body, "start_maximized",
                     "Start maximized",
                     "Launch the toolkit in a maximized window.")

        # ── Section: Appearance ──
        self._section(body, "APPEARANCE")
        self._switch(body, "animate_background",
                     "Animated constellation background",
                     "Turn off to reduce CPU usage on low-end machines.")
        self._switch(body, "typewriter_effect",
                     "Typewriter welcome text",
                     "Disable for instant text on slower systems.")

        # ── Section: Performance ──
        self._section(body, "PERFORMANCE")
        refresh_card = ctk.CTkFrame(body, fg_color=COLORS["card"],
                                    corner_radius=12, border_width=1,
                                    border_color=COLORS["border"])
        refresh_card.pack(fill="x", pady=6)

        ctk.CTkLabel(refresh_card, text="CPU / RAM refresh interval",
                     font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"], fg_color="transparent",
                     anchor="w").pack(anchor="w", padx=16, pady=(12, 0))
        ctk.CTkLabel(refresh_card,
                     text="How often the stat rings update (milliseconds).",
                     font=FONT_SMALL, text_color=COLORS["text_dim"],
                     fg_color="transparent", anchor="w"
                     ).pack(anchor="w", padx=16, pady=(0, 6))

        val_lbl = ctk.CTkLabel(refresh_card,
                               text=f"{self.settings['stats_refresh_ms']} ms",
                               font=("Segoe UI", 12, "bold"),
                               text_color=COLORS["accent"],
                               fg_color="transparent")
        val_lbl.pack(anchor="e", padx=16)

        def _on_slider(v):
            ms = int(v)
            self.settings["stats_refresh_ms"] = ms
            val_lbl.configure(text=f"{ms} ms")

        slider = ctk.CTkSlider(refresh_card, from_=500, to=5000,
                               number_of_steps=45,
                               command=_on_slider,
                               fg_color=COLORS["border"],
                               progress_color=COLORS["accent"],
                               button_color=COLORS["accent"],
                               button_hover_color="#00b8d4")
        slider.set(self.settings["stats_refresh_ms"])
        slider.pack(fill="x", padx=16, pady=(0, 14))

        # ── Footer buttons ──
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkButton(footer, text="Reset to Defaults", width=150, height=38,
                      fg_color="transparent", border_width=1,
                      border_color=COLORS["warning"], text_color=COLORS["warning"],
                      hover_color="#2a1a00", corner_radius=8,
                      command=self._reset_defaults).pack(side="left")

        ctk.CTkButton(footer, text="Cancel", width=100, height=38,
                      fg_color="transparent", border_width=1,
                      border_color=COLORS["border"], text_color=COLORS["text_dim"],
                      hover_color=COLORS["card_hover"], corner_radius=8,
                      command=self.destroy).pack(side="right", padx=(8, 0))

        ctk.CTkButton(footer, text="Save", width=120, height=38,
                      fg_color=COLORS["accent"], text_color="#001018",
                      hover_color="#00b8d4", corner_radius=8,
                      command=self._save).pack(side="right")

    def _section(self, parent, title):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        wrap.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(wrap, text=f"◢  {title}",
                     font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["accent"], fg_color="transparent"
                     ).pack(side="left")
        ctk.CTkFrame(wrap, height=1, fg_color=COLORS["border"]
                     ).pack(side="left", fill="x", expand=True, padx=(12, 0))

    def _switch(self, parent, key, title, description):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"],
                            corner_radius=12, border_width=1,
                            border_color=COLORS["border"])
        card.pack(fill="x", pady=6)

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=12)

        text = ctk.CTkFrame(row, fg_color="transparent")
        text.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(text, text=title, font=("Segoe UI", 13, "bold"),
                     text_color=COLORS["text"], fg_color="transparent",
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(text, text=description, font=FONT_SMALL,
                     text_color=COLORS["text_dim"], fg_color="transparent",
                     anchor="w", wraplength=420, justify="left"
                     ).pack(anchor="w", pady=(2, 0))

        var = tk.BooleanVar(value=bool(self.settings.get(key, False)))
        self.vars[key] = var
        ctk.CTkSwitch(row, text="", variable=var, width=48,
                      progress_color=COLORS["accent"],
                      button_color=COLORS["text"],
                      button_hover_color=COLORS["accent2"]
                      ).pack(side="right", padx=(12, 0))

    def _reset_defaults(self):
        self.settings = dict(DEFAULT_SETTINGS)
        for key, var in self.vars.items():
            var.set(bool(self.settings.get(key, False)))
        Toast(self.master, "Settings reset to defaults (unsaved)", "warn")

    def _save(self):
        for key, var in self.vars.items():
            self.settings[key] = bool(var.get())
        if save_settings(self.settings):
            Toast(self.master, "Settings saved", "success")
            try:
                self.on_save(self.settings)
            except Exception as e:
                print(f"[Falcon] on_save callback failed: {e}")
            self.destroy()
        else:
            Toast(self.master, "Could not save settings", "error")


# ─────────────────────────────────────────────────────────────
#  ABOUT WINDOW
# ─────────────────────────────────────────────────────────────
class AboutWindow(ctk.CTkToplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("About — Falcon Super Toolkit")
        self.geometry("620x680")
        self.configure(fg_color=COLORS["bg_alt"])
        self.transient(master)
        self.grab_set()
        self.resizable(False, False)

        set_window_icon(self, size_hint=32)

        self.attributes("-alpha", 0.0)
        for i in range(16):
            try:
                self.attributes("-alpha", i / 16)
                self.update()
                time.sleep(0.008)
            except tk.TclError:
                return

        self._build_ui()

    def _build_ui(self):
        # Header
        header = ctk.CTkFrame(self, fg_color=COLORS["card"],
                              corner_radius=0, height=64)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="  ℹ️  ABOUT",
                     font=("Segoe UI", 18, "bold"),
                     text_color=COLORS["accent"], fg_color="transparent"
                     ).pack(side="left", padx=22, pady=18)

        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        # ── Logo + Name ──
        hero = ctk.CTkFrame(body, fg_color=COLORS["card"],
                            corner_radius=16, border_width=1,
                            border_color=COLORS["border"])
        hero.pack(fill="x", pady=(0, 12))

        hero_inner = ctk.CTkFrame(hero, fg_color="transparent")
        hero_inner.pack(padx=20, pady=20)

        if PIL_AVAILABLE and os.path.isfile(LOGO_PNG):
            try:
                base = Image.open(LOGO_PNG).convert("RGBA")
                base = _strip_white_background(base, threshold=18)
                h = 90
                w = int(base.width * (h / base.height))
                img = base.resize((w, h), Image.LANCZOS)
                img = _premultiply_glow(img, spread=5, intensity=0.30)
                self._about_img = ctk.CTkImage(
                    light_image=img, dark_image=img, size=img.size)
                ctk.CTkLabel(hero_inner, text="", image=self._about_img,
                             fg_color="transparent").pack(side="left", padx=(0, 18))
            except Exception as e:
                print(f"[Falcon] About logo failed: {e}")

        txt = ctk.CTkFrame(hero_inner, fg_color="transparent")
        txt.pack(side="left", anchor="center")
        ctk.CTkLabel(txt, text="FALCON SUPER TOOLKIT",
                     font=("Segoe UI", 22, "bold"),
                     text_color=COLORS["text"], fg_color="transparent",
                     anchor="w").pack(anchor="w")
        ctk.CTkLabel(txt, text=f"Version {APP_VERSION}  •  Advanced Animated Edition",
                     font=FONT_SMALL, text_color=COLORS["accent"],
                     fg_color="transparent", anchor="w").pack(anchor="w", pady=(2, 0))

        # ── Info sections ──
        self._info_card(body, "DEVELOPER", [
            ("Name", APP_DEVELOPER),
            ("GitHub", APP_GITHUB),
        ], link_key="GitHub")

        self._info_card(body, "ENVIRONMENT", [
            ("Python", platform.python_version()),
            ("OS", f"{platform.system()} {platform.release()}"),
            ("Architecture", platform.machine()),
            ("Admin", "Yes" if self._is_admin() else "No"),
            ("Pillow", "Installed" if PIL_AVAILABLE else "Missing"),
            ("psutil", "Installed" if psutil else "Missing"),
        ])

        self._info_card(body, "COMPONENTS", [
            ("GUI", "customtkinter"),
            ("Background", "Constellation network (Canvas)"),
            ("Icons", "Pillow + .ico"),
            ("Settings file", os.path.basename(SETTINGS_FILE)),
        ])

        # ── Buttons ──
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkButton(footer, text="Open GitHub", width=150, height=38,
                      fg_color="transparent", border_width=1,
                      border_color=COLORS["accent"], text_color=COLORS["accent"],
                      hover_color=COLORS["card_hover"], corner_radius=8,
                      command=self._open_github).pack(side="left")

        ctk.CTkButton(footer, text="Close", width=120, height=38,
                      fg_color=COLORS["accent"], text_color="#001018",
                      hover_color="#00b8d4", corner_radius=8,
                      command=self.destroy).pack(side="right")

    def _info_card(self, parent, title, rows, link_key=None):
        card = ctk.CTkFrame(parent, fg_color=COLORS["card"],
                            corner_radius=12, border_width=1,
                            border_color=COLORS["border"])
        card.pack(fill="x", pady=6)

        ctk.CTkLabel(card, text=title, font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["accent"], fg_color="transparent"
                     ).pack(anchor="w", padx=16, pady=(10, 4))

        for k, v in rows:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=16, pady=2)
            ctk.CTkLabel(row, text=k, font=FONT_SMALL,
                         text_color=COLORS["text_dim"], width=140,
                         fg_color="transparent", anchor="w"
                         ).pack(side="left")

            if link_key and k == link_key:
                link = ctk.CTkLabel(row, text=v, font=FONT_MONO,
                                    text_color=COLORS["accent"],
                                    fg_color="transparent", anchor="w",
                                    cursor="hand2")
                link.pack(side="left")
                link.bind("<Button-1>", lambda _e, u=v: webbrowser.open(u))
            else:
                ctk.CTkLabel(row, text=v, font=FONT_MONO,
                             text_color=COLORS["text"], fg_color="transparent",
                             anchor="w", wraplength=380, justify="left"
                             ).pack(side="left")

        # spacer
        ctk.CTkFrame(card, height=6, fg_color="transparent").pack()

    @staticmethod
    def _is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _open_github(self):
        try:
            webbrowser.open(APP_GITHUB)
        except Exception as e:
            Toast(self.master, f"Could not open browser: {e}", "error")


# ─────────────────────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────────────────────
class FalconToolkit(ctk.CTk):
    HEADER_LOGO_HEIGHT = 120
    WATERMARK_HEIGHT   = 260
    WATERMARK_OPACITY  = 0.12

    def __init__(self):
        super().__init__()
        self.title(f"FALCON SUPER TOOLKIT v{APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1100, 760)
        self.configure(fg_color=COLORS["bg"])

        self.settings = load_settings()

        if self.settings.get("start_maximized"):
            try:
                self.state("zoomed")
            except Exception:
                pass

        set_window_icon(self, size_hint=32)

        self._logo_img_header = None
        self._logo_img_watermark = None
        self._load_logo_images()

        self.bg = ConstellationBackground(self)
        self.bg.place(relx=0, rely=0, relwidth=1, relheight=1)
        if not self.settings.get("animate_background", True):
            self.bg._animating = False

        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._build_header()
        self._build_dashboard()

        # self.protocol("WM_DELETE_WINDOW", self._exit)
        self.protocol("WM_DELETE_WINDOW", self._on_close_button)

    def _on_close_button(self):
        """Title-bar X — same confirmation, just explicit for clarity."""
        self._exit()

    # ── Logo loading ────────────────────────────────────────
    def _load_logo_images(self):
        if not PIL_AVAILABLE or not os.path.isfile(LOGO_PNG):
            if not os.path.isfile(LOGO_PNG):
                print(f"[Falcon] Logo not found at: {LOGO_PNG} — using glyph fallback.")
            if not PIL_AVAILABLE:
                print("[Falcon] Pillow not installed — logo will not be displayed.")
            return
        try:
            base = Image.open(LOGO_PNG).convert("RGBA")
            base = _strip_white_background(base, threshold=18)

            h = self.HEADER_LOGO_HEIGHT
            w = int(base.width * (h / base.height))
            header_img = base.resize((w, h), Image.LANCZOS)
            header_img = _premultiply_glow(header_img,
                                           color=(0, 229, 255),
                                           spread=6, intensity=0.35)
            hw, hh = header_img.size
            self._logo_img_header = ctk.CTkImage(
                light_image=header_img, dark_image=header_img, size=(hw, hh))

            wh = self.WATERMARK_HEIGHT
            ww = int(base.width * (wh / base.height))
            wm = base.resize((ww, wh), Image.LANCZOS).copy()
            wm.putalpha(wm.split()[3].point(
                lambda p: int(p * self.WATERMARK_OPACITY)))
            wm = _premultiply_glow(wm, color=(0, 229, 255),
                                   spread=4, intensity=0.20)
            wmw, wmh = wm.size
            self._logo_img_watermark = ctk.CTkImage(
                light_image=wm, dark_image=wm, size=(wmw, wmh))
        except Exception as e:
            print(f"[Falcon] Failed to load logo: {e}")

    # ── Header ──────────────────────────────────────────────
    def _build_header(self):
        header = ctk.CTkFrame(self.container, fg_color="transparent")
        header.pack(fill="x", padx=44, pady=(16, 6))

        logo = ctk.CTkFrame(header, fg_color="transparent")
        logo.pack(side="left")

        row = ctk.CTkFrame(logo, fg_color="transparent")
        row.pack(anchor="w")

        if self._logo_img_header is not None:
            self.logo_glyph = ctk.CTkLabel(
                row, text="", image=self._logo_img_header,
                fg_color="transparent", bg_color="transparent", width=0)
            self.logo_glyph.pack(side="left", padx=(0, 18))
            self._pulse_subtitle()
        else:
            self.logo_glyph = ctk.CTkLabel(
                row, text="◈", font=("Segoe UI", 56, "bold"),
                text_color=COLORS["accent"], fg_color="transparent", width=70)
            self.logo_glyph.pack(side="left", padx=(0, 8))
            self._spin_logo()

        text_block = ctk.CTkFrame(row, fg_color="transparent")
        text_block.pack(side="left", anchor="center")

        self.logo_lbl = ctk.CTkLabel(
            text_block, text="FALCON SUPER TOOLKIT",
            font=FONT_LOGO, text_color=COLORS["text"],
            fg_color="transparent", anchor="w")
        self.logo_lbl.pack(anchor="w")

        self.subtitle = ctk.CTkLabel(
            text_block,
            text=f"SYSTEM OPTIMIZATION  •  DIAGNOSTICS  •  v{APP_VERSION}",
            font=("Segoe UI", 12, "bold"),
            text_color=COLORS["accent"], fg_color="transparent", anchor="w")
        self.subtitle.pack(anchor="w", pady=(2, 0))

        status = ctk.CTkFrame(header, fg_color="transparent")
        status.pack(side="right")

        self.clock_lbl = ctk.CTkLabel(status, text="",
                                      font=("Segoe UI", 13, "bold"),
                                      text_color=COLORS["accent"],
                                      fg_color="transparent")
        self.clock_lbl.pack(anchor="e")

        admin_txt = "● ADMINISTRATOR" if self._is_admin() else "● STANDARD USER"
        admin_col = COLORS["success"] if self._is_admin() else COLORS["warning"]
        ctk.CTkLabel(status, text=admin_txt, font=FONT_SMALL,
                     text_color=admin_col, fg_color="transparent").pack(anchor="e")

        self._tick_clock()

        ctk.CTkFrame(self.container, height=1, fg_color=COLORS["border"]
                     ).pack(fill="x", padx=44, pady=(10, 0))

    def _tick_clock(self):
        try:
            self.clock_lbl.configure(
                text=datetime.now().strftime("%b %d, %Y  •  %H:%M:%S"))
        except Exception:
            return
        self.after(1000, self._tick_clock)

    def _spin_logo(self):
        glyphs = ["◈", "◇", "◈", "◆", "◈", "◇"]
        self._spin_idx = (getattr(self, "_spin_idx", 0) + 1) % len(glyphs)
        try:
            self.logo_glyph.configure(
                text=glyphs[self._spin_idx],
                text_color=COLORS["accent"] if self._spin_idx % 2 == 0
                else COLORS["accent2"])
        except Exception:
            return
        self.after(900, self._spin_logo)

    def _pulse_subtitle(self):
        self._pulse_t = getattr(self, "_pulse_t", 0.0) + 0.10
        try:
            hue = COLORS["accent"] if math.sin(self._pulse_t) > 0 else COLORS["accent2"]
            self.subtitle.configure(text_color=hue)
        except Exception:
            return
        self.after(120, self._pulse_subtitle)

    # ── Dashboard ───────────────────────────────────────────
    def _build_dashboard(self):
        wrapper = ctk.CTkFrame(self.container, fg_color="transparent")
        wrapper.pack(fill="both", expand=True, padx=44, pady=18)

        greet = ctk.CTkFrame(wrapper, fg_color=COLORS["card"],
                             corner_radius=18, border_width=1,
                             border_color=COLORS["border"])
        greet.pack(fill="x", pady=(0, 18))
        greet.grid_propagate(False)
        greet.configure(height=170)

        if self._logo_img_watermark is not None:
            wm = ctk.CTkLabel(greet, text="", image=self._logo_img_watermark,
                              fg_color="transparent", bg_color="transparent")
            wm.place(relx=1.0, rely=0.5, anchor="e", x=-12)
            wm.lower()

        inner = ctk.CTkFrame(greet, fg_color="transparent")
        inner.pack(fill="x", padx=26, pady=20)
        inner.lift()

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)

        self.welcome_lbl = ctk.CTkLabel(
            left, text="", font=("Segoe UI", 22, "bold"),
            text_color=COLORS["text"], fg_color="transparent", anchor="w")
        self.welcome_lbl.pack(anchor="w")

        ctk.CTkLabel(
            left,
            text="System optimization, activation, and diagnostics at your fingertips.",
            font=FONT_BODY, text_color=COLORS["text_dim"], fg_color="transparent"
        ).pack(anchor="w", pady=(6, 0))

        stats = ctk.CTkFrame(inner, fg_color="transparent")
        stats.pack(side="right")

        self.cpu_ring = StatRing(stats, "CPU", COLORS["accent"], size=82)
        self.cpu_ring.pack(side="left", padx=8)
        self.ram_ring = StatRing(stats, "RAM", COLORS["accent2"], size=82)
        self.ram_ring.pack(side="left", padx=8)

        if self.settings.get("typewriter_effect", True):
            self._typewriter("Welcome back, Administrator", self.welcome_lbl)
        else:
            self.welcome_lbl.configure(text="Welcome back, Administrator")

        self._update_stats()

        sec = ctk.CTkFrame(wrapper, fg_color="transparent")
        sec.pack(fill="x", pady=(6, 12))
        ctk.CTkLabel(sec, text="◢  TOOLS", font=("Segoe UI", 12, "bold"),
                     text_color=COLORS["text_dim"], fg_color="transparent"
                     ).pack(side="left")
        ctk.CTkFrame(sec, height=1, fg_color=COLORS["border"]
                     ).pack(side="left", fill="x", expand=True, padx=(12, 0))

        grid = ctk.CTkFrame(wrapper, fg_color="transparent")
        grid.pack(fill="both", expand=True)

        tools = [
            ("WinUtil Optimizer", "Chris Titus Tech — Windows optimization",
             "⚡", COLORS["accent"], self.launch_winutil),
            ("MAS Information", "Microsoft Activation Scripts project",
             "🔑", COLORS["accent2"], self.launch_mas),
            ("Activation Settings", "Open Windows activation panel",
             "⚙️", COLORS["success"], self.open_activation),
            ("System Information", "Hardware, OS, and uptime details",
             "💻", COLORS["warning"], self.show_system_info),
            ("Settings", "Preferences, animations, refresh rate",
             "🛠️", COLORS["accent3"], self.show_settings),
            ("About", "Version, credits, and environment details",
             "ℹ️", COLORS["accent2"], self.show_about),
        ]

        self.cards = []
        for i, (title, subtitle, icon, accent, cmd) in enumerate(tools):
            r, c = divmod(i, 2)
            btn = RippleButton(grid, title, subtitle, icon, command=cmd, accent=accent)
            btn.grid(row=r, column=c, sticky="nsew",
                     padx=(0, 12) if c == 0 else (12, 0), pady=(0, 14))
            self.cards.append(btn)

        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        for r in range(3):
            grid.grid_rowconfigure(r, weight=1)

        footer = ctk.CTkFrame(wrapper, fg_color="transparent")
        footer.pack(fill="x", pady=(8, 0))

        ctk.CTkLabel(footer,
                     text=f"Developer: {APP_DEVELOPER}  •  {APP_GITHUB}",
                     font=FONT_SMALL, text_color=COLORS["text_dim"],
                     fg_color="transparent").pack(side="left")

        ctk.CTkButton(footer, text="Exit", width=100, height=34,
                      fg_color="transparent", border_width=1,
                      border_color=COLORS["danger"], text_color=COLORS["danger"],
                      hover_color="#2a1010", corner_radius=8,
                      command=self._exit).pack(side="right")

    def _typewriter(self, text, label, i=0):
        try:
            label.configure(text=text[:i] + ("▌" if i < len(text) else ""))
        except Exception:
            return
        if i < len(text):
            self.after(35, lambda: self._typewriter(text, label, i + 1))

    def _update_stats(self):
        try:
            if psutil:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                self.cpu_ring.set_value(cpu)
                self.ram_ring.set_value(ram)
        except Exception:
            pass
        delay = max(300, int(self.settings.get("stats_refresh_ms", 1500)))
        self.after(delay, self._update_stats)

    # ── Settings / About ────────────────────────────────────
    def show_settings(self):
        SettingsWindow(self, self.settings, on_save=self._on_settings_saved)

    def _on_settings_saved(self, new_settings):
        self.settings.update(new_settings)

        # Apply background animation toggle live
        try:
            if self.settings.get("animate_background", True):
                if not self.bg._animating:
                    self.bg._animating = True
                    self.bg._animate()
            else:
                self.bg._animating = False
        except Exception as e:
            print(f"[Falcon] Background toggle failed: {e}")

    def show_about(self):
        AboutWindow(self)

    # ── Actions ─────────────────────────────────────────────
    def launch_winutil(self):
        if self.settings.get("confirm_winutil", True):
            if not messagebox.askyesno(
                "Launch WinUtil",
                "Launch Chris Titus Tech's WinUtil?\n\n"
                "This third-party utility makes system changes.\n"
                "Review changes before applying."):
                return
        Toast(self, "Launching WinUtil...", "info")
        self._run_powershell("irm https://christitus.com/win | iex")

    def launch_mas(self):
        if self.settings.get("confirm_mas", True):
            if not messagebox.askyesno(
                "Launch MAS",
                "Launch Massgrave Activation Scripts?\n\n"
                "Third-party licensing project. Use legitimate methods."):
                return
        Toast(self, "Launching MAS...", "info")
        self._run_powershell("irm https://get.activated.win | iex")

    def open_activation(self):
        try:
            subprocess.Popen("start ms-settings:activation", shell=True)
            Toast(self, "Opening Activation Settings", "success")
        except Exception as e:
            Toast(self, f"Failed: {e}", "error")

    def _run_powershell(self, command):
        def worker():
            try:
                flags = subprocess.CREATE_NEW_CONSOLE if os.name == "nt" else 0
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-Command",
                     f"Start-Process powershell -Verb RunAs "
                     f"-ArgumentList '-NoProfile -Command \"{command}\"'"],
                    creationflags=flags)
            except Exception as e:
                self.after(0, lambda: Toast(self, f"Error: {e}", "error"))
        threading.Thread(target=worker, daemon=True).start()

    def show_system_info(self):
        win = ctk.CTkToplevel(self)
        win.title("System Information")
        win.geometry("680x600")
        win.configure(fg_color=COLORS["bg_alt"])
        win.transient(self)
        win.grab_set()

        set_window_icon(win, size_hint=32)

        win.attributes("-alpha", 0.0)
        for i in range(16):
            try:
                win.attributes("-alpha", i / 16)
                win.update()
                time.sleep(0.01)
            except tk.TclError:
                return

        header = ctk.CTkFrame(win, fg_color=COLORS["card"],
                              corner_radius=0, height=64)
        header.pack(fill="x")
        ctk.CTkLabel(header, text="  💻  SYSTEM INFORMATION",
                     font=("Segoe UI", 18, "bold"),
                     text_color=COLORS["accent"], fg_color="transparent"
                     ).pack(side="left", padx=22, pady=18)

        body = ctk.CTkScrollableFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=18, pady=18)

        try:
            info = self._gather_system_info()
        except Exception as e:
            info = {"Error": {"Message": str(e)}}

        for section, rows in info.items():
            card = ctk.CTkFrame(body, fg_color=COLORS["card"],
                                corner_radius=12, border_width=1,
                                border_color=COLORS["border"])
            card.pack(fill="x", pady=6)

            ctk.CTkLabel(card, text=section, font=("Segoe UI", 12, "bold"),
                         text_color=COLORS["accent"], fg_color="transparent"
                         ).pack(anchor="w", padx=16, pady=(10, 4))

            for k, v in rows.items():
                row = ctk.CTkFrame(card, fg_color="transparent")
                row.pack(fill="x", padx=16, pady=2)
                ctk.CTkLabel(row, text=f"{k}", font=FONT_SMALL,
                             text_color=COLORS["text_dim"], width=150,
                             fg_color="transparent", anchor="w"
                             ).pack(side="left")
                ctk.CTkLabel(row, text=f"{v}", font=FONT_MONO,
                             text_color=COLORS["text"], fg_color="transparent",
                             anchor="w").pack(side="left")

        ctk.CTkButton(win, text="Close", command=win.destroy,
                      fg_color=COLORS["accent"], text_color="#001018",
                      hover_color="#00b8d4", height=38, corner_radius=8
                      ).pack(pady=14)

    def _gather_system_info(self):
        os_info = platform.uname()
        vm = psutil.virtual_memory() if psutil else None
        uptime = time.time() - (psutil.boot_time() if psutil else time.time())
        days, rem = divmod(int(uptime), 86400)
        hours, rem = divmod(rem, 3600)
        mins, _ = divmod(rem, 60)

        try:
            bios = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_BIOS).SerialNumber"],
                text=True, timeout=5).strip()
        except Exception:
            bios = "N/A"

        return {
            "COMPUTER": {
                "Name": platform.node(),
                "Manufacturer": self._wmic("Win32_ComputerSystem", "Manufacturer"),
                "Model": self._wmic("Win32_ComputerSystem", "Model"),
            },
            "WINDOWS": {
                "OS": os_info.system + " " + os_info.release,
                "Version": os_info.version,
                "Architecture": os_info.machine,
            },
            "HARDWARE": {
                "CPU": os_info.processor or "N/A",
                "RAM": f"{vm.total / (1024**3):.2f} GB" if vm else "N/A",
                "BIOS Serial": bios,
            },
            "UPTIME": {
                "Runtime": f"{days} Days, {hours} Hours, {mins} Minutes",
            },
        }

    def _wmic(self, cls, prop):
        try:
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 f"(Get-CimInstance {cls}).{prop}"],
                text=True, timeout=5, stderr=subprocess.DEVNULL).strip()
            return out or "N/A"
        except Exception:
            return "N/A"

    @staticmethod
    def _is_admin():
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except Exception:
            return False

    def _exit(self):
        # Prevent double-prompting if user clicks X while dialog is open
        if getattr(self, "_confirming_exit", False):
            return
        self._confirming_exit = True

        try:
            confirmed = messagebox.askyesno(
                "Exit Falcon Super Toolkit",
                "Are you sure you want to close FALCON SUPER TOOLKIT?\n\n"
                "Your saved settings will be kept.",
                icon="question",
                parent=self,
            )
        except Exception:
            confirmed = True  # fail open — allow exit if dialog errors
        finally:
            self._confirming_exit = False

        if not confirmed:
            return

        # ── Shutdown sequence ──
        try:
            self.bg._animating = False
        except Exception:
            pass

        for i in range(12, 0, -1):
            try:
                self.attributes("-alpha", i / 12)
                self.update()
                time.sleep(0.012)
            except tk.TclError:
                break

        self.destroy()


# ─────────────────────────────────────────────────────────────
#  ADMIN ELEVATION
# ─────────────────────────────────────────────────────────────
def relaunch_as_admin():
    if FalconToolkit._is_admin():
        return False
    if getattr(sys, "frozen", False):
        exe = sys.executable
        params = " ".join(f'"{a}"' for a in sys.argv[1:])
    else:
        exe = sys.executable
        script = os.path.abspath(sys.argv[0])
        params = f'"{script}" ' + " ".join(f'"{a}"' for a in sys.argv[1:])
    try:
        ret = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", exe, params, None, 1)
        return ret > 32
    except Exception:
        return False


if __name__ == "__main__":
    if os.name == "nt":
        # ── Unique App User Model ID so the taskbar icon groups correctly ──
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "PaulMendoza.FalconSuperToolkit.1")
        except Exception:
            pass

        if relaunch_as_admin():
            sys.exit(0)
        if not FalconToolkit._is_admin():
            try:
                root = tk.Tk()
                set_window_icon(root, size_hint=32)
                root.withdraw()
                messagebox.showerror(
                    "Administrator Required",
                    "FALCON SUPER TOOLKIT requires administrator privileges.\n\n"
                    "Please right-click and select 'Run as administrator'.")
                root.destroy()
            except Exception as e:
                print(f"[Falcon] Admin dialog error: {e}")
            sys.exit(1)

    # ── 1. Create the main window but keep it hidden ──
    app = FalconToolkit()
    app.withdraw()

    # ── 2. Show the 3-second splash on top ──
    splash = SplashScreen(app)
    splash.update()

    # ── 3. Reveal the main window once the splash finishes ──
    def _reveal():
        try:
            app.deiconify()
            app.lift()
            app.focus_force()
        except Exception:
            pass

    app.after(SplashScreen.DURATION_MS, _reveal)

    # ── 4. Run the event loop ──
    app.mainloop()