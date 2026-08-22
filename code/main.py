import math
import threading
import tkinter as tk
import numpy as np
from scipy.ndimage import gaussian_filter1d

import audio_core
from tray_app import setup_tray

# --- 初始化 Tkinter 視窗 ---
root = tk.Tk()
root.title("雙模式系統音訊 FFT 等化器")

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

cx = screen_w // 2
cy = screen_h // 2

root.geometry(f"{screen_w}x{screen_h}+0+0")
root.overrideredirect(True)

TRANS_COLOR = "#000001"
root.configure(bg=TRANS_COLOR)
root.wm_attributes("-transparentcolor", TRANS_COLOR)
root.wm_attributes("-topmost", True)

canvas = tk.Canvas(root, bg=TRANS_COLOR, highlightthickness=0)
canvas.pack(fill="both", expand=True)

NUM_BARS = 60
BAR_WIDTH = 4

current_mode = 0
target_mode = 0
anim_progress = 1.0
is_animating = False
prev_mode = 0

anim_start_cx = cx
anim_start_cy = cy
sensitivity_factor = 14.0

horiz_length = screen_w / 3
horiz_start_x = (screen_w - horiz_length) / 2
TOP_MARGIN = 0

def get_bar_coords(mode, index, bar_length):
    if mode == 0:
        radius = 100
        angle = (2 * math.pi / NUM_BARS) * index + (math.pi / 2)
        x1 = cx + radius * math.cos(angle)
        y1 = cy + radius * math.sin(angle)
        x2 = cx + (radius + bar_length) * math.cos(angle)
        y2 = cy + (radius + bar_length) * math.sin(angle)
        return x1, y1, x2, y2
    elif mode == 4:
        spacing = horiz_length / NUM_BARS
        x1 = horiz_start_x + index * spacing
        y1 = TOP_MARGIN
        return x1, y1, x1, y1 + bar_length

drag_area_circle = canvas.create_oval(cx - 100, cy - 100, cx + 100, cy + 100, fill="#000002", outline="")
canvas.itemconfigure(drag_area_circle, state="normal")

horiz_btn_offset_x = 18
horiz_btn_y = 17

horiz_drag_bg = canvas.create_oval(0, 0, 0, 0, fill="#1a1a1a", outline="#333333", width=1, state="hidden")
horiz_arrow_up = canvas.create_line(0, 0, 0, 0, fill="#00FF7F", width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
horiz_arrow_down = canvas.create_line(0, 0, 0, 0, fill="#00FF7F", width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
horiz_arrow_left = canvas.create_line(0, 0, 0, 0, fill="#00FF7F", width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
horiz_arrow_right = canvas.create_line(0, 0, 0, 0, fill="#00FF7F", width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")

rectangles = [canvas.create_line(0, 0, 0, 0, width=BAR_WIDTH, fill="#00FF7F", capstyle="round") for _ in range(NUM_BARS)]

is_running = True
tray_icon = None

def get_is_running():
    return is_running

def on_closing():
    global is_running
    is_running = False
    if tray_icon:
        tray_icon.stop()
    root.quit()
    root.destroy()

def lerp(a, b, t):
    return a + (b - a) * t

def update_horiz_drag_btn_coords():
    hx = horiz_start_x - horiz_btn_offset_x
    hy = horiz_btn_y
    r = 12
    canvas.coords(horiz_drag_bg, hx - r, hy - r, hx + r, hy + r)
    canvas.coords(horiz_arrow_up, hx, hy, hx, hy - 7)
    canvas.coords(horiz_arrow_down, hx, hy, hx, hy + 7)
    canvas.coords(horiz_arrow_left, hx, hy, hx - 7, hy)
    canvas.coords(horiz_arrow_right, hx, hy, hx + 7, hy)

def toggle_mode():
    global current_mode, target_mode, prev_mode, anim_progress, is_animating, anim_start_cx, anim_start_cy
    if is_animating: return
    prev_mode = current_mode
    target_mode = 4 if current_mode == 0 else 0
    anim_progress = 0.0
    is_animating = True
    
    anim_start_cx = cx
    anim_start_cy = cy
    
    if target_mode == 4:
        canvas.itemconfigure(drag_area_circle, state="hidden")
        update_horiz_drag_btn_coords()
        canvas.itemconfigure(horiz_drag_bg, state="normal")
        canvas.itemconfigure(horiz_arrow_up, state="normal")
        canvas.itemconfigure(horiz_arrow_down, state="normal")
        canvas.itemconfigure(horiz_arrow_left, state="normal")
        canvas.itemconfigure(horiz_arrow_right, state="normal")
    else:
        canvas.itemconfigure(horiz_drag_bg, state="hidden")
        canvas.itemconfigure(horiz_arrow_up, state="hidden")
        canvas.itemconfigure(horiz_arrow_down, state="hidden")
        canvas.itemconfigure(horiz_arrow_left, state="hidden")
        canvas.itemconfigure(horiz_arrow_right, state="hidden")

    animate_step()

def set_sensitivity(value):
    global sensitivity_factor
    sensitivity_factor = value

def get_sensitivity():
    return sensitivity_factor

# --- 右鍵選單 ---
context_menu = tk.Menu(root, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
context_menu.add_command(label="切換顯示模式 (圓形 / 橫向)", command=toggle_mode)

sens_menu = tk.Menu(context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
sens_menu.add_command(label="低 (8.0)", command=lambda: set_sensitivity(8.0))
sens_menu.add_command(label="中 (14.0)", command=lambda: set_sensitivity(14.0))
sens_menu.add_command(label="高 (22.0)", command=lambda: set_sensitivity(22.0))
sens_menu.add_command(label="極高 (32.0)", command=lambda: set_sensitivity(32.0))
context_menu.add_cascade(label="靈敏度設定", menu=sens_menu)

context_menu.add_separator()
context_menu.add_command(label="結束程式", command=on_closing)

def show_context_menu(event):
    try:
        context_menu.tk_popup(event.x_root, event.y_root)
    finally:
        context_menu.grab_release()

canvas.bind("<Button-3>", show_context_menu)
canvas.bind("<Button-2>", show_context_menu)

# 啟動系統匣
tray_icon = setup_tray(toggle_mode, set_sensitivity, get_sensitivity, lambda: root.after(0, on_closing))
threading.Thread(target=tray_icon.run, daemon=True).start()

def animate_step():
    global anim_progress, current_mode, is_animating, cx, cy
    if anim_progress < 1.0:
        anim_progress = min(1.0, anim_progress + 0.06)
        if target_mode == 0:
            cx = lerp(anim_start_cx, screen_w // 2, anim_progress)
            cy = lerp(anim_start_cy, screen_h // 2, anim_progress)
            canvas.coords(drag_area_circle, cx - 100, cy - 100, cx + 100, cy + 100)
        root.after(16, animate_step)
    else:
        current_mode = target_mode
        if target_mode == 0:
            cx = screen_w // 2
            cy = screen_h // 2
            canvas.coords(drag_area_circle, cx - 100, cy - 100, cx + 100, cy + 100)
            canvas.itemconfigure(drag_area_circle, state="normal")
        is_animating = False

# 視窗拖曳
x_offset, y_offset = 0, 0
is_dragging = False

def start_move(event):
    global x_offset, y_offset, is_dragging
    if current_mode == 0:
        if math.hypot(event.x - cx, event.y - cy) <= 100:
            is_dragging = True
            x_offset, y_offset = event.x, event.y
    elif current_mode == 4:
        hx = horiz_start_x - horiz_btn_offset_x
        hy = horiz_btn_y
        if abs(event.x - hx) <= 12 and abs(event.y - hy) <= 12:
            is_dragging = True
            x_offset, y_offset = event.x, event.y

def do_move(event):
    global cx, cy, horiz_start_x, x_offset, y_offset
    if is_dragging:
        dx, dy = event.x - x_offset, event.y - y_offset
        if current_mode == 0:
            cx += dx
            cy += dy
            max_r = 230
            cx = max(max_r, min(screen_w - max_r, cx))
            cy = max(max_r, min(screen_h - max_r, cy))
            canvas.coords(drag_area_circle, cx - 100, cy - 100, cx + 100, cy + 100)
        elif current_mode == 4:
            horiz_start_x += dx
            horiz_start_x = max(20, min(screen_w - horiz_length, horiz_start_x))
            update_horiz_drag_btn_coords()
        x_offset = event.x
        y_offset = event.y

def stop_move(event):
    global is_dragging
    is_dragging = False

canvas.bind("<Button-1>", start_move)
canvas.bind("<B1-Motion>", do_move)
canvas.bind("<ButtonRelease-1>", stop_move)

# 啟動音訊執行緒
threading.Thread(target=audio_core.capture_audio_thread, args=(get_is_running,), daemon=True).start()

fft_smooth = np.zeros(NUM_BARS)

def update_ui():
    global fft_smooth

    windowed = audio_core.audio_buffer * np.hanning(len(audio_core.audio_buffer))
    fft_data = np.abs(np.fft.rfft(windowed))
    freqs = np.fft.rfftfreq(len(audio_core.audio_buffer), 1.0 / audio_core.SAMPLE_RATE)
    freq_points = np.logspace(np.log10(20.0), np.log10(15000.0), NUM_BARS + 1)

    raw_bars = np.zeros(NUM_BARS)
    for i in range(NUM_BARS):
        idx_s = np.searchsorted(freqs, freq_points[i])
        idx_e = max(idx_s + 1, np.searchsorted(freqs, freq_points[i + 1]))
        bin_val = np.max(fft_data[idx_s:idx_e])
        t_val = i / (NUM_BARS - 1)
        comp = (0.4 + (t_val / 0.3) * 0.6) if t_val < 0.3 else (1.0 + ((t_val - 0.3) / 0.7) ** 1.8 * 8.0)
        raw_bars[i] = bin_val * comp

    smoothed = gaussian_filter1d(raw_bars, sigma=1.1)
    fft_smooth = fft_smooth * 0.7 + smoothed * 0.3

    for index, rect_id in enumerate(rectangles):
        val = fft_smooth[index]
        bar_len = min(130, np.cbrt(val) * sensitivity_factor)

        r = int(min(255, val * 10 + (index / NUM_BARS) * 180))
        g = int(max(0, 255 - val * 10 - (index / NUM_BARS) * 120))
        b = int(min(255, 120 + (index / NUM_BARS) * 135))

        x1_old, y1_old, x2_old, y2_old = get_bar_coords(prev_mode, index, bar_len)
        x1_new, y1_new, x2_new, y2_new = get_bar_coords(target_mode, index, bar_len)

        x1 = lerp(x1_old, x1_new, anim_progress)
        y1 = lerp(y1_old, y1_new, anim_progress)
        x2 = lerp(x2_old, x2_new, anim_progress)
        y2 = lerp(y2_old, y2_new, anim_progress)

        canvas.coords(rect_id, x1, y1, x2, y2)
        canvas.itemconfig(rect_id, fill=f"#{r:02x}{g:02x}{b:02x}")

    if current_mode == 4:
        update_horiz_drag_btn_coords()

    root.after(20, update_ui)

update_ui()
root.bind("<Escape>", on_closing)
root.mainloop()