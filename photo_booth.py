import os
import sys
import time
import json
import shutil
from threading import Thread, Event
from PIL import Image, ImageTk
Image.MAX_IMAGE_PIXELS = None
import tkinter as tk
from tkinter import messagebox
import cv2
print(cv2.data.haarcascades)
import numpy as np

# -----------------------------
# PATH HELPER
# -----------------------------
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# -----------------------------
# CONFIG
# -----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, 'frozen', False) else __file__))
WATCH_FOLDER  = os.path.join(BASE_DIR, "session")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")
USED_FOLDER   = os.path.join(BASE_DIR, "used")
LAYOUT_PATH   = None
REQUIRED_SHOTS = 3
session_running = Event()

_base_images = {}

# -----------------------------
# THEME
# -----------------------------
BG          = "#0f0f0f"
BG_PANEL    = "#1a1a1a"
BG_CARD     = "#222222"
ACCENT      = "#e8c97a"       # warm gold
ACCENT_DIM  = "#7a6835"
FG          = "#f0ece0"
FG_DIM      = "#888070"
DANGER      = "#c0392b"
SUCCESS     = "#27ae60"
BORDER      = "#333333"
FONT_TITLE  = ("Georgia", 28, "bold")
FONT_SUB    = ("Georgia", 11, "italic")
FONT_LABEL  = ("Courier", 10)
FONT_BTN    = ("Courier", 11, "bold")
FONT_HINT   = ("Courier", 9)

# -----------------------------
# PREPARE IMAGE
# -----------------------------
def prepare_image(img, slot_w, slot_h):
    img_ratio  = img.width  / img.height
    slot_ratio = slot_w / slot_h
    if img_ratio > slot_ratio:
        new_h = slot_h
        new_w = int(img.width * slot_h / img.height)
    else:
        new_w = slot_w
        new_h = int(img.height * slot_w / img.width)
    scaled = img.resize((new_w, new_h), Image.LANCZOS)
    init_ox = (new_w - slot_w) // 2
    init_oy = (new_h - slot_h) // 2
    img_cv = cv2.cvtColor(np.array(scaled), cv2.COLOR_RGB2BGR)
    gray   = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    faces = face_cascade.detectMultiScale(gray, 1.3, 5)
    if len(faces) > 0:
        x, y, w, h = faces[0]
        cx = x + w // 2
        cy = y + h // 2
        init_ox = max(0, min(cx - slot_w // 2, new_w - slot_w))
        init_oy = max(0, min(cy - slot_h // 2, new_h - slot_h))
    return scaled, init_ox, init_oy

# -----------------------------
# SLOT HELPERS
# -----------------------------
def _render_slot(s, scale):
    slot = s["slot"]
    ox   = int(s["ox"])
    oy   = int(s["oy"])
    crop = s["scaled_img"].crop((ox, oy, ox + slot["w"], oy + slot["h"]))
    if crop.size != (slot["w"], slot["h"]):
        crop = crop.resize((slot["w"], slot["h"]), Image.LANCZOS)
    pw = int(slot["w"] * scale)
    ph = int(slot["h"] * scale)
    return crop.resize((pw, ph), Image.LANCZOS)

def _clamp_offset(s):
    slot = s["slot"]
    s["ox"] = max(0.0, min(float(s["ox"]), s["scaled_img"].width  - slot["w"]))
    s["oy"] = max(0.0, min(float(s["oy"]), s["scaled_img"].height - slot["h"]))

def _refresh_slot(s, scale):
    preview = _render_slot(s, scale)
    new_tk  = ImageTk.PhotoImage(preview)
    s["tk_img"] = new_tk
    editor_canvas.itemconfig(s["canvas_item"], image=new_tk)

# -----------------------------
# LAYOUT
# -----------------------------
def load_layout():
    with open(LAYOUT_PATH, "r") as f:
        return json.load(f)

def open_editor(pil_images):
    root.after(0, lambda: _open_editor_main(pil_images))

def _open_editor_main(pil_images):
    global editor_canvas, strip_label

    layout = load_layout()
    strip_label.pack_forget()

    for widget in main_frame.pack_slaves():
        if getattr(widget, "_managed", False):
            widget.destroy()

    width, height = layout["width"], layout["height"]
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    scale = min(screen_w / width, screen_h / height) * 0.6

    # Editor section header
    editor_header = tk.Label(
        main_frame,
        text="— ADJUST YOUR PHOTOS —",
        bg=BG, fg=ACCENT,
        font=FONT_LABEL
    )
    editor_header._managed = True
    editor_header.pack(pady=(10, 4))

    editor_canvas = tk.Canvas(
        main_frame,
        width=int(width * scale), height=int(height * scale),
        bg=BG_CARD, cursor="fleur",
        highlightthickness=2, highlightbackground=ACCENT
    )
    editor_canvas._managed = True
    editor_canvas.pack()

    slots_state = []

    for idx, (pil_img, slot) in enumerate(zip(pil_images, layout["slots"])):
        scaled_img, init_ox, init_oy = prepare_image(
            pil_img.convert("RGB"), slot["w"], slot["h"])

        s = {
            "scaled_img": scaled_img,
            "slot": slot,
            "ox": float(init_ox),
            "oy": float(init_oy),
            "zoom": 1.0,
        }
        _base_images[idx] = scaled_img.copy()

        preview     = _render_slot(s, scale)
        tk_img      = ImageTk.PhotoImage(preview)
        canvas_item = editor_canvas.create_image(
            slot["x"] * scale, slot["y"] * scale, anchor="nw", image=tk_img)
        s["canvas_item"] = canvas_item
        s["tk_img"]      = tk_img
        s["base_idx"]    = idx

        # Slot label number
        editor_canvas.create_text(
            slot["x"] * scale + 8, slot["y"] * scale + 8,
            anchor="nw", text=f"#{idx+1}",
            fill=ACCENT, font=("Courier", 9, "bold")
        )

        border_tag = f"border_{idx}"
        border = editor_canvas.create_rectangle(
            slot["x"] * scale,               slot["y"] * scale,
            (slot["x"] + slot["w"]) * scale, (slot["y"] + slot["h"]) * scale,
            outline=ACCENT_DIM, width=1, fill="", tags=border_tag)
        editor_canvas.tag_raise(border, canvas_item)
        s["border_tag"] = border_tag

        slots_state.append(s)

    editor_canvas._slot_refs = slots_state

    # ------------------------------------------------------------------
    # INTERACTION
    # ------------------------------------------------------------------
    drag = {"state": None, "active_border": None}

    def find_slot(ex, ey):
        for i, s in enumerate(slots_state):
            sl = s["slot"]
            if (sl["x"] * scale <= ex <= (sl["x"] + sl["w"]) * scale and
                    sl["y"] * scale <= ey <= (sl["y"] + sl["h"]) * scale):
                return i
        return None

    def on_press(event):
        idx = find_slot(event.x, event.y)
        if idx is not None:
            drag["state"] = {"idx": idx, "mx": event.x, "my": event.y}
            # Reset all borders to dim
            for s in slots_state:
                editor_canvas.itemconfig(s["border_tag"], outline=ACCENT_DIM, width=1)
            # Highlight the active slot border
            editor_canvas.itemconfig(slots_state[idx]["border_tag"], outline=ACCENT, width=2)

    def on_drag(event):
        if drag["state"] is None:
            return
        idx = drag["state"]["idx"]
        s   = slots_state[idx]
        dx = (event.x - drag["state"]["mx"]) / scale
        dy = (event.y - drag["state"]["my"]) / scale
        drag["state"]["mx"] = event.x
        drag["state"]["my"] = event.y
        s["ox"] -= dx
        s["oy"] -= dy
        _clamp_offset(s)
        _refresh_slot(s, scale)

    def on_release(event):
        drag["state"] = None

    def on_scroll(event):
        if event.delta:
            direction = 1 if event.delta > 0 else -1
        elif event.num == 4:
            direction = 1
        else:
            direction = -1

        idx = find_slot(event.x, event.y)
        if idx is None:
            return
        s    = slots_state[idx]
        slot = s["slot"]

        new_zoom = max(1.0, min(5.0, s["zoom"] + direction * 0.15))
        if new_zoom == s["zoom"]:
            return

        base = _base_images[s["base_idx"]]
        prev_scale_w = s["scaled_img"].width  / base.width
        prev_scale_h = s["scaled_img"].height / base.height
        cx_base = (s["ox"] + slot["w"] / 2) / prev_scale_w
        cy_base = (s["oy"] + slot["h"] / 2) / prev_scale_h

        new_w = max(slot["w"], int(base.width  * new_zoom / s["zoom"] * prev_scale_w))
        new_h = max(slot["h"], int(base.height * new_zoom / s["zoom"] * prev_scale_h))

        new_scaled = base.resize((new_w, new_h), Image.LANCZOS)
        s["scaled_img"] = new_scaled
        s["zoom"]       = new_zoom

        new_scale_w = new_w / base.width
        new_scale_h = new_h / base.height
        s["ox"] = cx_base * new_scale_w - slot["w"] / 2
        s["oy"] = cy_base * new_scale_h - slot["h"] / 2
        _clamp_offset(s)
        _refresh_slot(s, scale)
        return "break"  # ← stops the event from bubbling up to the page scrollbar

    editor_canvas.bind("<ButtonPress-1>",   on_press)
    editor_canvas.bind("<B1-Motion>",       on_drag)
    editor_canvas.bind("<ButtonRelease-1>", on_release)
    editor_canvas.bind("<MouseWheel>",      on_scroll)
    editor_canvas.bind("<Button-4>",        on_scroll)
    editor_canvas.bind("<Button-5>",        on_scroll)

    # ------------------------------------------------------------------
    # HINT + SAVE
    # ------------------------------------------------------------------
    hint = tk.Label(
        main_frame,
        text="✦  drag to pan inside each slot   |   scroll wheel to zoom  ✦",
        bg=BG, fg=FG_DIM, font=FONT_HINT
    )
    hint._managed = True
    hint.pack(pady=(4, 6))

    def save():
        final = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        for s in slots_state:
            slot = s["slot"]
            ox   = int(s["ox"])
            oy   = int(s["oy"])
            crop = s["scaled_img"].crop(
                (ox, oy, ox + slot["w"], oy + slot["h"]))
            if crop.size != (slot["w"], slot["h"]):
                crop = crop.resize((slot["w"], slot["h"]), Image.LANCZOS)
            final.paste(crop.convert("RGBA"), (slot["x"], slot["y"]))

        overlay_path = resource_path(layout.get("overlay", ""))
        if layout.get("overlay") and os.path.exists(overlay_path):
            overlay = Image.open(overlay_path).convert("RGBA").resize((width, height), Image.LANCZOS)
            # Remove near-white pixels from the Canva overlay
            overlay_data = np.array(overlay)
            r, g, b, a = overlay_data[:,:,0], overlay_data[:,:,1], overlay_data[:,:,2], overlay_data[:,:,3]
            white_mask = (r > 240) & (g > 240) & (b > 240)
            overlay_data[:,:,3] = np.where(white_mask, 0, a)
            overlay = Image.fromarray(overlay_data, "RGBA")
            final.alpha_composite(overlay)

        output_path = os.path.join(OUTPUT_FOLDER, f"strip_{int(time.time())}.jpg")
        final.convert("RGB").save(output_path)

        for widget in main_frame.pack_slaves():
            if getattr(widget, "_managed", False):
                widget.destroy()
        strip_label.pack(pady=10)
        display_strip(output_path)

    save_btn = tk.Button(
        main_frame, text="⬇  SAVE STRIP", command=save,
        bg=ACCENT, fg="#0f0f0f",
        font=("Courier", 12, "bold"),
        relief="flat", cursor="hand2",
        padx=24, pady=8,
        activebackground="#d4b460", activeforeground="#0f0f0f"
    )
    save_btn._managed = True
    save_btn.pack(pady=8)


# -----------------------------
# SESSION LOOP
# -----------------------------
def session_loop():
    while session_running.is_set():
        try:
            files = [os.path.join(WATCH_FOLDER, f) for f in os.listdir(WATCH_FOLDER)
                     if f.lower().endswith((".jpg", ".png"))]
            if len(files) >= REQUIRED_SHOTS:
                latest = sorted(files, key=os.path.getmtime, reverse=True)[:REQUIRED_SHOTS]
                pil_images = [Image.open(f).convert("RGB") for f in latest]
                for f in latest:
                    shutil.move(f, os.path.join(USED_FOLDER, os.path.basename(f)))
                _base_images.clear()
                open_editor(pil_images)
        except Exception as e:
            print(e)
        time.sleep(1)

# -----------------------------
# GUI HELPERS
# -----------------------------
def display_strip(path):
    img = Image.open(path)
    screen_w, screen_h = root.winfo_screenwidth(), root.winfo_screenheight()
    img.thumbnail((screen_w * 0.6, screen_h * 0.7))
    tk_img = ImageTk.PhotoImage(img)
    strip_label.config(image=tk_img, bg=BG)
    strip_label.image = tk_img

def _make_divider(parent):
    f = tk.Frame(parent, bg=BORDER, height=1)
    f.pack(fill="x", padx=40, pady=8)

def _make_label(parent, text, font=None, fg=None):
    return tk.Label(parent, text=text, bg=BG,
                    fg=fg or FG_DIM, font=font or FONT_LABEL)

# -----------------------------
# SESSION CONTROL WITH STATE FEEDBACK
# -----------------------------
def start_session():
    global LAYOUT_PATH, REQUIRED_SHOTS
    layout_name = layout_var.get()
    LAYOUT_PATH = resource_path(f"layouts/{layout_name}/layout.json")
    try:
        layout = load_layout()
        REQUIRED_SHOTS = len(layout["slots"])
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load layout: {e}")
        return

    if not session_running.is_set():
        session_running.set()
        Thread(target=session_loop, daemon=True).start()

        # Update button states
        btn_start.config(
            text="● SESSION ACTIVE",
            bg=SUCCESS, fg="#ffffff",
            relief="flat"
        )
        btn_stop.config(
            text="■ STOP SESSION",
            bg=DANGER, fg="#ffffff",
            state="normal"
        )
        status_var.set(f"WATCHING  ·  {REQUIRED_SHOTS} SHOTS REQUIRED  ·  DROP INTO /session")
        status_label.config(fg=SUCCESS)
        layout_menu.config(state="disabled")
        btn_layout.config(state="disabled")

def stop_session():
    session_running.clear()

    btn_start.config(
        text="▶  START SESSION",
        bg=BG_CARD, fg=ACCENT,
        relief="flat"
    )
    btn_stop.config(
        text="■ STOP",
        bg=BG_CARD, fg=FG_DIM,
        state="disabled"
    )
    status_var.set("IDLE  ·  SELECT A LAYOUT AND START A SESSION")
    status_label.config(fg=FG_DIM)
    layout_menu.config(state="normal")
    btn_layout.config(state="normal")

def choose_layout():
    global LAYOUT_PATH, REQUIRED_SHOTS
    layout_name = layout_var.get()
    LAYOUT_PATH = resource_path(f"layouts/{layout_name}/layout.json")
    try:
        layout = load_layout()
        REQUIRED_SHOTS = len(layout["slots"])
        status_var.set(f"LAYOUT: {layout_name.upper()}  ·  {REQUIRED_SHOTS} PHOTOS PER STRIP")
        status_label.config(fg=ACCENT)
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load layout: {e}")

# -----------------------------
# MAIN GUI
# -----------------------------
def setup_gui():
    global layout_var, strip_label, root, main_frame, editor_canvas
    global btn_start, btn_stop, btn_layout, layout_menu, status_var, status_label

    root = tk.Tk()
    root.title("PHOTOBOOTH")
    root.configure(bg=BG)
    root.attributes("-fullscreen", True)
    root.bind("<Escape>", lambda e: root.attributes("-fullscreen", False))

    # Scrollable main frame
    canvas_scroll = tk.Canvas(root, bg=BG, highlightthickness=0)
    scrollbar = tk.Scrollbar(root, orient="vertical", command=canvas_scroll.yview,
                             bg=BG_PANEL, troughcolor=BG)
    canvas_scroll.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    canvas_scroll.pack(side="left", fill="both", expand=True)

    main_frame = tk.Frame(canvas_scroll, bg=BG)
    main_frame_id = canvas_scroll.create_window((0, 0), window=main_frame, anchor="n")

    def on_frame_configure(e):
        canvas_scroll.configure(scrollregion=canvas_scroll.bbox("all"))
    def on_canvas_configure(e):
        canvas_scroll.itemconfig(main_frame_id, width=e.width)
    main_frame.bind("<Configure>", on_frame_configure)
    canvas_scroll.bind("<Configure>", on_canvas_configure)

    # Mouse wheel scroll
    def _scroll(e):
        canvas_scroll.yview_scroll(int(-1 * (e.delta / 120)), "units")
    root.bind("<MouseWheel>", _scroll)

    # ── HEADER ─────────────────────────────────────────────────────────
    header = tk.Frame(main_frame, bg=BG)
    header.pack(fill="x", pady=(32, 0))

    logo_path = resource_path(os.path.join("assets", "logoWObg.png"))
    try:
        logo_img = Image.open(logo_path).convert("RGBA")
        logo_h = 100
        logo_w = int(logo_img.width * logo_h / logo_img.height)
        logo_img = logo_img.resize((logo_w, logo_h), Image.LANCZOS)
        bg_layer = Image.new("RGBA", logo_img.size, "#0f0f0fff")
        bg_layer.alpha_composite(logo_img)
        logo_tk = ImageTk.PhotoImage(bg_layer.convert("RGB"))
        logo_label = tk.Label(header, image=logo_tk, bg=BG, bd=0)
        logo_label.image = logo_tk
        logo_label.pack()
    except Exception:
        tk.Label(header, text="PHOTOBOOTH", bg=BG, fg=FG,
                 font=FONT_TITLE).pack()

    tk.Label(header, text="studio  ·  session manager",
             bg=BG, fg=ACCENT, font=FONT_SUB).pack(pady=(2, 0))

    # Gold rule
    tk.Frame(main_frame, bg=ACCENT, height=1).pack(fill="x", padx=60, pady=(16, 0))

    # ── STATUS BAR ─────────────────────────────────────────────────────
    status_var = tk.StringVar(value="IDLE  ·  SELECT A LAYOUT AND START A SESSION")
    status_label = tk.Label(
        main_frame, textvariable=status_var,
        bg=BG_PANEL, fg=FG_DIM,
        font=FONT_HINT, pady=6
    )
    status_label.pack(fill="x", padx=0, pady=(0, 0))

    # ── CONTROL PANEL ──────────────────────────────────────────────────
    panel = tk.Frame(main_frame, bg=BG_PANEL,
                     highlightthickness=1, highlightbackground=BORDER)
    panel.pack(padx=60, pady=20, fill="x")

    # Layout row
    layout_row = tk.Frame(panel, bg=BG_PANEL)
    layout_row.pack(fill="x", padx=20, pady=(16, 8))

    tk.Label(layout_row, text="LAYOUT", bg=BG_PANEL, fg=FG_DIM,
             font=FONT_LABEL).pack(side="left", padx=(0, 12))

    layout_var = tk.StringVar(value="classic")
    layout_menu = tk.OptionMenu(layout_row, layout_var, "classic", "4R")
    layout_menu.config(
        bg=BG_CARD, fg=FG, font=FONT_LABEL,
        activebackground=ACCENT, activeforeground=BG,
        highlightthickness=0, relief="flat",
        indicatoron=True, bd=0
    )
    layout_menu["menu"].config(bg=BG_CARD, fg=FG, font=FONT_LABEL,
                                activebackground=ACCENT, activeforeground=BG)
    layout_menu.pack(side="left", padx=(0, 12))

    btn_layout = tk.Button(
        layout_row, text="APPLY",
        command=choose_layout,
        bg=BG_CARD, fg=ACCENT,
        font=FONT_HINT, relief="flat",
        padx=10, pady=4, cursor="hand2",
        activebackground=ACCENT, activeforeground=BG
    )
    btn_layout.pack(side="left")

    # Divider
    tk.Frame(panel, bg=BORDER, height=1).pack(fill="x", padx=20)

    # Session buttons row
    btn_row = tk.Frame(panel, bg=BG_PANEL)
    btn_row.pack(fill="x", padx=20, pady=(12, 16))

    btn_start = tk.Button(
        btn_row, text="▶  START SESSION",
        command=start_session,
        bg=BG_CARD, fg=ACCENT,
        font=FONT_BTN, relief="flat",
        padx=20, pady=10, cursor="hand2",
        activebackground=SUCCESS, activeforeground="#ffffff"
    )
    btn_start.pack(side="left", padx=(0, 10))

    btn_stop = tk.Button(
        btn_row, text="■ STOP",
        command=stop_session,
        bg=BG_CARD, fg=FG_DIM,
        font=FONT_BTN, relief="flat",
        padx=20, pady=10, cursor="hand2",
        state="disabled",
        activebackground=DANGER, activeforeground="#ffffff"
    )
    btn_stop.pack(side="left")

    # Folder info
    info_row = tk.Frame(panel, bg=BG_PANEL)
    info_row.pack(fill="x", padx=20, pady=(0, 14))
    tk.Label(info_row,
             text=f"session → {WATCH_FOLDER}",
             bg=BG_PANEL, fg=FG_DIM, font=FONT_HINT).pack(side="left")

    # ── OUTPUT PREVIEW ─────────────────────────────────────────────────
    tk.Frame(main_frame, bg=ACCENT, height=1).pack(fill="x", padx=60, pady=(4, 0))

    preview_label = tk.Label(main_frame, text="OUTPUT PREVIEW",
                             bg=BG, fg=FG_DIM, font=FONT_LABEL)
    preview_label.pack(pady=(10, 0))

    strip_label = tk.Label(main_frame, bg=BG)
    strip_label.pack(pady=10)

    # ── FOOTER ─────────────────────────────────────────────────────────
    tk.Label(main_frame,
             text="ESC  to exit fullscreen",
             bg=BG, fg=BORDER, font=FONT_HINT).pack(pady=(0, 20))

    editor_canvas = None
    root.mainloop()

# -----------------------------
# INIT FOLDERS
# -----------------------------
for folder in [WATCH_FOLDER, OUTPUT_FOLDER, USED_FOLDER]:
    os.makedirs(folder, exist_ok=True)

if __name__ == "__main__":
    setup_gui()