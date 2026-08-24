import math
import threading
import tkinter as tk
from tkinter import colorchooser
import numpy as np
from PIL import Image, ImageTk, ImageDraw, ImageEnhance
from scipy.ndimage import gaussian_filter1d
import json
import os

import audio_core
import media_core
import media_info_core

# 設定檔儲存於 AppData 的路徑邏輯
APP_NAME = "MyEqualizerApp"

def get_config_path():
    appdata_dir = os.getenv('APPDATA')
    if not appdata_dir:
        appdata_dir = os.path.expanduser("~")
    target_dir = os.path.join(appdata_dir, APP_NAME)
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
        except Exception:
            target_dir = appdata_dir
    return os.path.join(target_dir, "config.json")

def load_config():
    path = get_config_path()
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_config(config_data):
    path = get_config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)
    except Exception:
        pass


class EqualizerWindow:
    def __init__(self, root, screen_w, screen_h, on_closing_cb, update_tray_cb=None):
        self.root = root
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.on_closing_cb = on_closing_cb
        self.update_tray_cb = update_tray_cb

        # 讀取 AppData 中的設定（涵蓋 5 個核心設定）
        config = load_config()
        self.current_mode = config.get("mode", 0)
        self.target_mode = self.current_mode
        self.sensitivity_factor = config.get("sensitivity", 14.0)
        self.current_theme = config.get("theme", "green")
        self.custom_theme_color = tuple(config.get("custom_color", [0, 255, 127]))
        self.saved_opacity = config.get("opacity", 1.0)
        saved_source = config.get("source", "system")
        audio_core.set_audio_source(saved_source)

        self.cx = screen_w // 2
        self.cy = screen_h // 2

        self.canvas = tk.Canvas(root, bg="#000001", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.NUM_BARS = 72
        self.BAR_WIDTH = 2
        self.NUM_SIDE_BARS = 90

        self.anim_progress = 1.0
        self.is_animating = False
        self.prev_mode = 0

        self.anim_start_cx = self.cx
        self.anim_start_cy = self.cy
        self.is_playing = True

        self.horiz_length = screen_w / 3
        self.horiz_start_x = (screen_w - self.horiz_length) / 2
        self.TOP_MARGIN = 0

        self.current_image_tk = None
        self.pad_img = None
        self.image_rotation_angle = 0.0
        self.last_title = None
        
        self.full_title = ""
        self.marquee_offset = 0

        self.init_ui_elements()
        self.init_context_menu()
        self.bind_events()

        # 套用儲存的透明度
        self.root.after(100, lambda: self.change_opacity(self.saved_opacity))

        self.fft_smooth = np.zeros(self.NUM_BARS)
        self.left_fft_smooth = np.zeros(self.NUM_SIDE_BARS)
        self.right_fft_smooth = np.zeros(self.NUM_SIDE_BARS)

        self.update_ui()
        self.poll_media_info()
        self.update_marquee()

    def save_current_settings(self):
        """將 5 個設定儲存至 AppData 內的 config.json"""
        config = {
            "mode": self.current_mode,
            "opacity": self.get_opacity(),
            "sensitivity": self.sensitivity_factor,
            "theme": self.current_theme,
            "custom_color": list(self.custom_theme_color),
            "source": audio_core.get_audio_source()
        }
        save_config(config)

    def notify_tray(self):
        if self.update_tray_cb:
            try:
                self.update_tray_cb()
            except Exception:
                pass

    def get_theme_hex(self):
        if self.current_theme == "cyan":
            return "#00E5FF"
        elif self.current_theme == "orange":
            return "#FFA500"
        elif self.current_theme == "custom":
            r, g, b = self.custom_theme_color
            return f"#{r:02x}{g:02x}{b:02x}"
        return "#00FF7F"

    def is_audio_active(self):
        if audio_core.audio_buffer is not None and len(audio_core.audio_buffer) > 0:
            return np.max(np.abs(audio_core.audio_buffer)) > 0.015
        return False

    def get_bar_coords(self, mode, index, bar_length):
        if mode == 0:
            radius = 100
            angle = (2 * math.pi / self.NUM_BARS) * index + (math.pi / 2)
            x1 = self.cx + radius * math.cos(angle)
            y1 = self.cy + radius * math.sin(angle)
            x2 = self.cx + (radius + bar_length) * math.cos(angle)
            y2 = self.cy + (radius + bar_length) * math.sin(angle)
            return x1, y1, x2, y2
        elif mode == 4:
            spacing = self.horiz_length / self.NUM_BARS
            x1 = self.horiz_start_x + index * spacing
            y1 = self.TOP_MARGIN
            return x1, y1, x1, y1 + bar_length
        return 0, 0, 0, 0

    def get_side_bar_coords(self, index, left_bar_len, right_bar_len):
        spacing = self.screen_h / self.NUM_SIDE_BARS
        y = index * spacing + (spacing / 2)
        lx1, ly1 = 0, y
        lx2, ly2 = left_bar_len, y
        rx1, ry1 = self.screen_w, y
        rx2, ry2 = self.screen_w - right_bar_len, y
        return (lx1, ly1, lx2, ly2), (rx1, ry1, rx2, ry2)

    def init_ui_elements(self):
        cx, cy = self.cx, self.cy
        self.drag_area_circle = self.canvas.create_oval(cx - 100, cy - 100, cx + 100, cy + 100, fill="#111111", outline="", width=0)
        self.album_image_id = self.canvas.create_image(cx, cy, state="hidden")
        
        # 修正：將字型改為 "Microsoft JhengHei" 以防粉圓字型在系統找不到而失效，並賦予預設文字確保能正常顯示
        self.title_text_id = self.canvas.create_text(cx, cy + 33, text="播放器準備就緒...", fill="#ffffff", font=("Microsoft JhengHei", 10, "bold"), state="hidden")

        self.btn_prev_text   = self.canvas.create_text(cx - 33, cy + 55, text="⏮", fill="#aaaaaa", font=("Arial", 12), state="normal")
        self.btn_toggle_text = self.canvas.create_text(cx + 2,  cy + 55, text="⏸", fill="#ffffff", font=("Arial", 14), state="normal")
        self.btn_next_text   = self.canvas.create_text(cx + 37, cy + 55, text="⏭", fill="#aaaaaa", font=("Arial", 12), state="normal")

        self.tooltip_bg = self.canvas.create_rectangle(0, 0, 0, 0, fill="#222222", outline="#555555", state="hidden")
        # 提示框文字也一併更換為安全字型
        self.tooltip_text = self.canvas.create_text(0, 0, text="", fill="#ffffff", font=("Microsoft JhengHei", 9), state="hidden")

        self.horiz_btn_offset_x = 18
        self.horiz_btn_y = 17

        self.horiz_drag_bg = self.canvas.create_oval(0, 0, 0, 0, fill="#1a1a1a", outline="", width=0, state="hidden")
        self.horiz_arrow_up = self.canvas.create_line(0, 0, 0, 0, fill=self.get_theme_hex(), width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
        self.horiz_arrow_down = self.canvas.create_line(0, 0, 0, 0, fill=self.get_theme_hex(), width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
        self.horiz_arrow_left = self.canvas.create_line(0, 0, 0, 0, fill=self.get_theme_hex(), width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")
        self.horiz_arrow_right = self.canvas.create_line(0, 0, 0, 0, fill=self.get_theme_hex(), width=1.5, arrow=tk.LAST, arrowshape=(4, 5, 3), state="hidden")

        self.rectangles = [self.canvas.create_line(0, 0, 0, 0, width=self.BAR_WIDTH, fill=self.get_theme_hex(), capstyle="round") for _ in range(self.NUM_BARS)]
        
        self.left_side_rectangles = [
            self.canvas.create_line(0, 0, 0, 0, width=self.BAR_WIDTH, fill=self.get_theme_hex(), capstyle="round", state="hidden") 
            for _ in range(self.NUM_SIDE_BARS)
        ]
        self.right_side_rectangles = [
            self.canvas.create_line(0, 0, 0, 0, width=self.BAR_WIDTH, fill=self.get_theme_hex(), capstyle="round", state="hidden") 
            for _ in range(self.NUM_SIDE_BARS)
        ]
        
        # 根據啟動時的模式調整介面可見性
        if self.current_mode in [4, 5]:
            self.canvas.itemconfigure(self.drag_area_circle, state="hidden")
            self.canvas.itemconfigure(self.album_image_id, state="hidden")
            self.canvas.itemconfigure(self.title_text_id, state="hidden")
            self.canvas.itemconfigure(self.btn_prev_text, state="hidden")
            self.canvas.itemconfigure(self.btn_toggle_text, state="hidden")
            self.canvas.itemconfigure(self.btn_next_text, state="hidden")
            if self.current_mode == 4:
                self.update_horiz_drag_btn_coords()
                self.canvas.itemconfigure(self.horiz_drag_bg, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_up, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_down, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_left, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_right, state="normal")
            elif self.current_mode == 5:
                for rid in self.left_side_rectangles:
                    self.canvas.itemconfigure(rid, state="normal")
                for rid in self.right_side_rectangles:
                    self.canvas.itemconfigure(rid, state="normal")
                for rid in self.rectangles:
                    self.canvas.itemconfigure(rid, state="hidden")

    def get_opacity(self):
        try:
            return float(self.root.attributes('-alpha'))
        except Exception:
            return 1.0

    def change_opacity(self, alpha_value):
        try:
            self.root.attributes('-alpha', float(alpha_value))
            self.save_current_settings()
            self.notify_tray()
        except Exception:
            pass

    def init_context_menu(self):
        self.context_menu = tk.Menu(self.root, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
        
        def refresh_menu():
            self.context_menu.delete(0, tk.END)
            
            # 1. 顯示模式
            mode_menu = tk.Menu(self.context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
            modes = [("圓形互動模式", 0), ("橫向頂部模式", 4), ("左右側邊雙聲道模式", 5)]
            for name, val in modes:
                label_text = f"{name}    ✓" if self.current_mode == val else name
                mode_menu.add_command(label=label_text, command=lambda v=val: self.set_mode(v))
            self.context_menu.add_cascade(label="顯示模式", menu=mode_menu)

            # 2. 視窗透明度
            opacity_menu = tk.Menu(self.context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
            opacities = [("100% (不透明)", 1.0), ("80%", 0.8), ("60%", 0.6)]
            for name, val in opacities:
                label_text = f"{name}    ✓" if abs(self.get_opacity() - val) < 0.01 else name
                opacity_menu.add_command(label=label_text, command=lambda v=val: self.change_opacity(v))
            self.context_menu.add_cascade(label="視窗透明度", menu=opacity_menu)

            # 3. 靈敏度設定
            sens_menu = tk.Menu(self.context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
            sens_list = [("低 (8.0)", 8.0), ("中 (14.0)", 14.0), ("高 (22.0)", 22.0), ("極高 (32.0)", 32.0)]
            for name, val in sens_list:
                label_text = f"{name}    ✓" if self.sensitivity_factor == val else name
                sens_menu.add_command(label=label_text, command=lambda v=val: self.set_sensitivity(v))
            self.context_menu.add_cascade(label="靈敏度設定", menu=sens_menu)

            # 4. 主題風格
            theme_menu = tk.Menu(self.context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
            themes = [("霓虹綠 (Classic)", "green"), ("電競藍 (Cyber)", "cyan"), ("日落橘 (Sunset)", "orange"), ("自訂色調 (Custom)...", "custom")]
            for name, val in themes:
                label_text = f"{name}    ✓" if self.current_theme == val else name
                theme_menu.add_command(label=label_text, command=lambda v=val: self.set_theme(v))
            self.context_menu.add_cascade(label="主題風格", menu=theme_menu)

            # 5. 音源選擇
            source_menu = tk.Menu(self.context_menu, tearoff=0, bg="#222222", fg="#ffffff", activebackground="#00FF7F", activeforeground="#000000")
            sources = [("僅系統聲音 (System)", "system"), ("僅麥克風 (Mic)", "mic"), ("混合模式 (Mic & System)", "both")]
            current_src = audio_core.get_audio_source()
            for name, val in sources:
                label_text = f"{name}    ✓" if current_src == val else name
                source_menu.add_command(label=label_text, command=lambda v=val: self.set_audio_source(v))
            self.context_menu.add_cascade(label="音源選擇", menu=source_menu)

            self.context_menu.add_separator()
            self.context_menu.add_command(label="結束程式", command=self.on_closing_cb)

        refresh_menu()
        self.refresh_context_menu = refresh_menu
        
    def show_context_menu(self, event):
        try:
            self.refresh_context_menu()
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def bind_events(self):
        self.canvas.bind("<Button-3>", self.show_context_menu)
        self.canvas.bind("<Button-2>", self.show_context_menu)
        self.canvas.bind("<Button-1>", self.start_move)
        self.canvas.bind("<B1-Motion>", self.do_move)
        self.canvas.bind("<ButtonRelease-1>", self.stop_move)
        self.canvas.bind("<Motion>", self.on_mouse_motion)

    def lerp(self, a, b, t):
        return a + (b - a) * t

    def update_horiz_drag_btn_coords(self):
        hx = self.horiz_start_x - self.horiz_btn_offset_x
        hy = self.horiz_btn_y
        r = 12
        self.canvas.coords(self.horiz_drag_bg, hx - r, hy - r, hx + r, hy + r)
        self.canvas.coords(self.horiz_arrow_up, hx, hy, hx, hy - 7)
        self.canvas.coords(self.horiz_arrow_down, hx, hy, hx, hy + 7)
        self.canvas.coords(self.horiz_arrow_left, hx, hy, hx - 7, hy)
        self.canvas.coords(self.horiz_arrow_right, hx, hy, hx + 7, hy)

    def set_mode(self, mode):
        if self.is_animating or self.current_mode == mode: 
            return
        
        # 立即更新當前模式狀態，確保系統匣與右鍵選單能同步抓到正確打勾狀態
        self.prev_mode = self.current_mode
        self.current_mode = mode  # <--- 將這一行移到這裡，點擊後立即生效
        self.target_mode = mode

        self.anim_progress = 0.0
        self.is_animating = True
        
        self.anim_start_cx = self.cx
        self.anim_start_cy = self.cy
        
        if self.target_mode in [4, 5]:
            self.canvas.itemconfigure(self.drag_area_circle, state="hidden")
            self.canvas.itemconfigure(self.album_image_id, state="hidden")
            self.canvas.itemconfigure(self.title_text_id, state="hidden")
            self.canvas.itemconfigure(self.btn_prev_text, state="hidden")
            self.canvas.itemconfigure(self.btn_toggle_text, state="hidden")
            self.canvas.itemconfigure(self.btn_next_text, state="hidden")
            self.canvas.itemconfigure(self.tooltip_bg, state="hidden")
            self.canvas.itemconfigure(self.tooltip_text, state="hidden")
            
            if self.target_mode == 4:
                self.update_horiz_drag_btn_coords()
                self.canvas.itemconfigure(self.horiz_drag_bg, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_up, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_down, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_left, state="normal")
                self.canvas.itemconfigure(self.horiz_arrow_right, state="normal")
            else:
                self.canvas.itemconfigure(self.horiz_drag_bg, state="hidden")
                self.canvas.itemconfigure(self.horiz_arrow_up, state="hidden")
                self.canvas.itemconfigure(self.horiz_arrow_down, state="hidden")
                self.canvas.itemconfigure(self.horiz_arrow_left, state="hidden")
                self.canvas.itemconfigure(self.horiz_arrow_right, state="hidden")
        else:
            self.canvas.itemconfigure(self.horiz_drag_bg, state="hidden")
            self.canvas.itemconfigure(self.horiz_arrow_up, state="hidden")
            self.canvas.itemconfigure(self.horiz_arrow_down, state="hidden")
            self.canvas.itemconfigure(self.horiz_arrow_left, state="hidden")
            self.canvas.itemconfigure(self.horiz_arrow_right, state="hidden")
            for rid in self.left_side_rectangles:
                self.canvas.itemconfigure(rid, state="hidden")
            for rid in self.right_side_rectangles:
                self.canvas.itemconfigure(rid, state="hidden")

        if self.target_mode == 5:
            for rid in self.left_side_rectangles:
                self.canvas.itemconfigure(rid, state="normal")
            for rid in self.right_side_rectangles:
                self.canvas.itemconfigure(rid, state="normal")
            for rid in self.rectangles:
                self.canvas.itemconfigure(rid, state="hidden")
        else:
            for rid in self.rectangles:
                self.canvas.itemconfigure(rid, state="normal")

        self.animate_step()
        self.save_current_settings()
        self.notify_tray()

    def get_mode(self):
        return self.current_mode

    def animate_step(self):
        if self.anim_progress < 1.0:
            self.anim_progress = min(1.0, self.anim_progress + 0.06)
            if self.target_mode == 0:
                self.cx = self.lerp(self.anim_start_cx, self.screen_w // 2, self.anim_progress)
                self.cy = self.lerp(self.anim_start_cy, self.screen_h // 2, self.anim_progress)
                self.canvas.coords(self.drag_area_circle, self.cx - 100, self.cy - 100, self.cx + 100, self.cy + 100)
                self.canvas.coords(self.album_image_id, self.cx, self.cy)
                self.canvas.coords(self.title_text_id, self.cx, self.cy + 33)
                self.canvas.coords(self.btn_prev_text, self.cx - 33, self.cy + 55)
                self.canvas.coords(self.btn_toggle_text, self.cx + 2, self.cy + 55)
                self.canvas.coords(self.btn_next_text, self.cx + 37, self.cy + 55)
            self.root.after(16, self.animate_step)
        else:
            self.current_mode = self.target_mode
            if self.target_mode == 0:
                self.cx = self.screen_w // 2
                self.cy = self.screen_h // 2
                self.canvas.coords(self.drag_area_circle, self.cx - 100, self.cy - 100, self.cx + 100, self.cy + 100)
                self.canvas.coords(self.album_image_id, self.cx, self.cy)
                self.canvas.coords(self.title_text_id, self.cx, self.cy + 33)
                self.canvas.coords(self.btn_prev_text, self.cx - 33, self.cy + 55)
                self.canvas.coords(self.btn_toggle_text, self.cx + 2, self.cy + 55)
                self.canvas.coords(self.btn_next_text, self.cx + 37, self.cy + 55)
                
                self.canvas.itemconfigure(self.drag_area_circle, state="normal")
                if getattr(self, 'pad_img', None) is not None:
                    self.canvas.itemconfigure(self.album_image_id, state="normal")
                if self.full_title:
                    self.canvas.itemconfigure(self.title_text_id, state="normal")
                self.canvas.itemconfigure(self.btn_prev_text, state="normal")
                self.canvas.itemconfigure(self.btn_toggle_text, state="normal")
                self.canvas.itemconfigure(self.btn_next_text, state="normal")
            self.is_animating = False

    def set_sensitivity(self, value):
        self.sensitivity_factor = value
        self.save_current_settings()
        self.notify_tray()

    def get_sensitivity(self):
        return self.sensitivity_factor

    def set_theme(self, theme_name):
        if theme_name == "custom":
            color_result = colorchooser.askcolor(title="選擇自訂頻譜顏色", initialcolor=self.get_theme_hex())
            if color_result[0]:
                self.custom_theme_color = tuple(int(c) for c in color_result[0])
                self.current_theme = "custom"
        else:
            self.current_theme = theme_name

        theme_color = self.get_theme_hex()
        self.canvas.itemconfig(self.horiz_arrow_up, fill=theme_color)
        self.canvas.itemconfig(self.horiz_arrow_down, fill=theme_color)
        self.canvas.itemconfig(self.horiz_arrow_left, fill=theme_color)
        self.canvas.itemconfig(self.horiz_arrow_right, fill=theme_color)
        
        self.save_current_settings()
        self.notify_tray()

    def get_theme(self):
        return self.current_theme

    def set_audio_source(self, source_type):
        audio_core.set_audio_source(source_type)
        self.save_current_settings()
        self.notify_tray()

    def get_audio_source(self):
        return audio_core.get_audio_source()

    def start_move(self, event):
        self.x_offset, self.y_offset = event.x, event.y
        self.click_start_x, self.click_start_y = event.x, event.y
        self.is_dragging = False
        if self.current_mode == 0:
            dist = math.hypot(event.x - self.cx, event.y - self.cy)
            if dist <= 100:
                self.is_dragging = False
        elif self.current_mode == 4:
            hx = self.horiz_start_x - self.horiz_btn_offset_x
            hy = self.horiz_btn_y
            if abs(event.x - hx) <= 12 and abs(event.y - hy) <= 12:
                self.is_dragging = True

    def do_move(self, event):
        if math.hypot(event.x - self.click_start_x, event.y - self.click_start_y) > 4:
            self.is_dragging = True

        if self.is_dragging:
            dx, dy = event.x - self.x_offset, event.y - self.y_offset
            if self.current_mode == 0:
                self.cx += dx
                self.cy += dy
                max_r = 230
                self.cx = max(max_r, min(self.screen_w - max_r, self.cx))
                self.cy = max(max_r, min(self.screen_h - max_r, self.cy))
                self.canvas.coords(self.drag_area_circle, self.cx - 100, self.cy - 100, self.cx + 100, self.cy + 100)
                self.canvas.coords(self.album_image_id, self.cx, self.cy)
                self.canvas.coords(self.title_text_id, self.cx, self.cy + 33)
                self.canvas.coords(self.btn_prev_text, self.cx - 33, self.cy + 55)
                self.canvas.coords(self.btn_toggle_text, self.cx + 2, self.cy + 55)
                self.canvas.coords(self.btn_next_text, self.cx + 37, self.cy + 55)
            elif self.current_mode == 4:
                self.horiz_start_x += dx
                self.horiz_start_x = max(20, min(self.screen_w - self.horiz_length, self.horiz_start_x))
                self.update_horiz_drag_btn_coords()
            self.x_offset = event.x
            self.y_offset = event.y

    def trigger_quick_poll(self):
        def fetch():
            data = media_info_core.get_media_info()
            self.root.after(0, lambda: self.apply_media_info(data))

        self.root.after(300, lambda: threading.Thread(target=fetch, daemon=True).start())
        self.root.after(800, lambda: threading.Thread(target=fetch, daemon=True).start())

    def stop_move(self, event):
        if not self.is_dragging and self.current_mode == 0:
            dist = math.hypot(event.x - self.cx, event.y - self.cy)
            if dist <= 100:
                rel_x = event.x - self.cx
                rel_y = event.y - self.cy
                if rel_y > 35:
                    if rel_x < -18:
                        media_core.control_media("prev")
                        self.trigger_quick_poll()
                    elif rel_x > 18:
                        media_core.control_media("next")
                        self.trigger_quick_poll()
                    else:
                        if self.is_playing and not self.is_audio_active():
                            self.is_dragging = False
                            return
                        media_core.control_media("toggle")
                        self.is_playing = not self.is_playing
                        icon_str = "⏸" if self.is_playing else "▶"
                        self.canvas.itemconfig(self.btn_toggle_text, text=icon_str)
        self.is_dragging = False

    def on_mouse_motion(self, event):
        if self.current_mode != 0:
            return
        rel_x = event.x - self.cx
        rel_y = event.y - self.cy
        dist = math.hypot(rel_x, rel_y)
        theme_color = self.get_theme_hex()

        if dist <= 100:
            if rel_y > 35:
                if rel_x < -18:
                    self.show_tooltip(event.x, event.y, "上一首")
                    self.canvas.itemconfig(self.btn_prev_text, fill=theme_color)
                    self.canvas.itemconfig(self.btn_toggle_text, fill="#ffffff")
                    self.canvas.itemconfig(self.btn_next_text, fill="#aaaaaa")
                    return
                elif rel_x > 18:
                    self.show_tooltip(event.x, event.y, "下一首")
                    self.canvas.itemconfig(self.btn_next_text, fill=theme_color)
                    self.canvas.itemconfig(self.btn_prev_text, fill="#aaaaaa")
                    self.canvas.itemconfig(self.btn_toggle_text, fill="#ffffff")
                    return
                else:
                    if self.is_playing and not self.is_audio_active():
                        self.show_tooltip(event.x, event.y, "目前無音樂")
                    else:
                        tip = "暫停" if self.is_playing else "播放"
                        self.show_tooltip(event.x, event.y, tip)
                    self.canvas.itemconfig(self.btn_toggle_text, fill=theme_color)
                    self.canvas.itemconfig(self.btn_prev_text, fill="#aaaaaa")
                    self.canvas.itemconfig(self.btn_next_text, fill="#aaaaaa")
                    return

        self.hide_tooltip()
        self.reset_button_colors()

    def reset_button_colors(self):
        self.canvas.itemconfig(self.btn_prev_text, fill="#aaaaaa")
        self.canvas.itemconfig(self.btn_toggle_text, fill="#ffffff")
        self.canvas.itemconfig(self.btn_next_text, fill="#aaaaaa")

    def show_tooltip(self, x, y, text):
        tx, ty = x + 15, y + 15
        self.canvas.coords(self.tooltip_text, tx + 25, ty + 12)
        self.canvas.itemconfig(self.tooltip_text, text=text, state="normal")
        bbox = self.canvas.bbox(self.tooltip_text)
        if bbox:
            self.canvas.coords(self.tooltip_bg, bbox[0]-4, bbox[1]-2, bbox[2]+4, bbox[3]+2)
            self.canvas.itemconfig(self.tooltip_bg, state="normal")

    def hide_tooltip(self):
        self.canvas.itemconfig(self.tooltip_bg, state="hidden")
        self.canvas.itemconfig(self.tooltip_text, state="hidden")

    def poll_media_info(self):
        def fetch():
            data = media_info_core.get_media_info()
            self.root.after(0, lambda: self.apply_media_info(data))

        threading.Thread(target=fetch, daemon=True).start()
        self.root.after(2500, self.poll_media_info)

    def apply_media_info(self, data):
        if not data:
            if self.current_mode == 0:
                self.canvas.itemconfigure(self.album_image_id, state="hidden")
                self.canvas.itemconfigure(self.title_text_id, state="hidden")
            self.current_image_tk = None
            self.pad_img = None
            self.full_title = ""
            self.is_playing = False
            return

        self.is_playing = data.get("is_playing", True)
        
        if self.current_mode == 0:
            icon_str = "⏸" if self.is_playing else "▶"
            self.canvas.itemconfig(self.btn_toggle_text, text=icon_str)

        title = data.get("title", "")
        is_new_track = (title != self.last_title)
        
        if is_new_track:
            self.last_title = title
            self.full_title = title if title else ""
            self.marquee_offset = 0

        pil_img = data.get("image")
        
        if pil_img and (is_new_track or not hasattr(self, 'pad_img') or self.pad_img is None):
            pil_img = pil_img.convert("RGBA")
            w, h = pil_img.size
            
            if w > h:
                left = (w - h) // 2
                top = 0
                right = left + h
                bottom = h
                pil_img = pil_img.crop((left, top, right, bottom))
            elif h > w:
                left = 0
                top = 0
                right = w
                bottom = w
                pil_img = pil_img.crop((left, top, right, bottom))
            
            pil_img = pil_img.resize((190, 190), Image.Resampling.LANCZOS)
            pil_img = ImageEnhance.Color(pil_img).enhance(0.25)
            pil_img = ImageEnhance.Brightness(pil_img).enhance(0.55)
            
            canvas_size = 300
            self.paste_x = (canvas_size - 190) // 2
            self.paste_y = (canvas_size - 190) // 2
            
            self.pad_img = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
            self.pad_img.paste(pil_img, (self.paste_x, self.paste_y))
            
            self.mask = Image.new("L", (190, 190), 0)
            draw = ImageDraw.Draw(self.mask)
            draw.ellipse((0, 0, 190, 190), fill=255)
            
            self.image_rotation_angle = 0.0
            
            rotated = self.pad_img.rotate(self.image_rotation_angle, resample=Image.Resampling.BICUBIC, fillcolor=(0, 0, 0, 0))
            cropped = rotated.crop((self.paste_x, self.paste_y, self.paste_x + 190, self.paste_y + 190))
            final_img = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
            final_img.paste(cropped, (0, 0), self.mask)
            
            self.current_image_tk = ImageTk.PhotoImage(final_img)
            self.canvas.itemconfig(self.album_image_id, image=self.current_image_tk)
            if self.current_mode == 0:
                self.canvas.itemconfigure(self.album_image_id, state="normal")
        elif not pil_img:
            if self.current_mode == 0:
                self.canvas.itemconfigure(self.album_image_id, state="hidden")
            self.current_image_tk = None
            self.pad_img = None

        if self.current_mode == 0 and self.full_title:
            self.canvas.itemconfigure(self.title_text_id, state="normal")
        elif self.current_mode == 0:
            self.canvas.itemconfigure(self.title_text_id, state="hidden")

    def update_marquee(self):
        is_playing = getattr(self, 'is_playing', True)
        
        if self.current_mode == 0 and self.full_title:
            max_chars = 10
            if len(self.full_title) <= max_chars:
                self.canvas.itemconfig(self.title_text_id, text=self.full_title)
            else:
                padded = self.full_title + "     "
                display_text = padded[self.marquee_offset:] + padded[:self.marquee_offset]
                
                if is_playing:
                    self.marquee_offset = (self.marquee_offset + 1) % len(padded)
                    
                self.canvas.itemconfig(self.title_text_id, text=display_text[:max_chars])
                
            self.canvas.itemconfigure(self.title_text_id, state="normal")
        elif self.current_mode == 0 and not self.full_title:
            # 當還沒抓到歌名時，顯示預設提示
            self.canvas.itemconfig(self.title_text_id, text="等待播放音樂...")
            self.canvas.itemconfigure(self.title_text_id, state="normal")
        else:
            self.canvas.itemconfig(self.title_text_id, text="")
            self.canvas.itemconfigure(self.title_text_id, state="hidden")
            
        self.root.after(220, self.update_marquee)

    def update_ui(self):
        if self.current_mode == 0 and not self.is_animating and getattr(self, 'is_playing', True) and hasattr(self, 'pad_img') and self.pad_img is not None:
            self.image_rotation_angle -= 0.6  
            
            rotated = self.pad_img.rotate(
                self.image_rotation_angle, 
                resample=Image.Resampling.BICUBIC, 
                fillcolor=(0, 0, 0, 0)
            )
            
            cropped = rotated.crop((self.paste_x, self.paste_y, self.paste_x + 190, self.paste_y + 190))
            final_img = Image.new("RGBA", (190, 190), (0, 0, 0, 0))
            final_img.paste(cropped, (0, 0), self.mask)
            
            self.current_image_tk = ImageTk.PhotoImage(final_img)
            self.canvas.itemconfig(self.album_image_id, image=self.current_image_tk)

        def get_dynamic_rgb(val, index, total_count):
            if self.current_theme == "green":
                r = int(min(255, val * 10 + (index / total_count) * 180))
                g = int(max(0, 255 - val * 10 - (index / total_count) * 120))
                b = int(min(255, 120 + (index / total_count) * 135))
            elif self.current_theme == "cyan":
                r = int(max(0, 50 - val * 5))
                g = int(min(255, 150 + val * 8 + (index / total_count) * 100))
                b = int(min(255, 200 + val * 5))
            elif self.current_theme == "orange":
                r = int(min(255, 200 + val * 10))
                g = int(min(255, 100 + val * 5 + (index / total_count) * 100))
                b = int(max(0, 50 - val * 5))
            elif self.current_theme == "custom":
                cr, cg, cb = self.custom_theme_color
                r = int(min(255, cr * 0.5 + val * 8 + (index / total_count) * 60))
                g = int(min(255, cg * 0.5 + val * 8 + (index / total_count) * 60))
                b = int(min(255, cb * 0.5 + val * 8 + (index / total_count) * 60))
            else:
                r, g, b = 0, 255, 127
            return r, g, b

        if self.current_mode == 5:
            def compute_side_spectrum(buffer):
                windowed = buffer * np.hanning(len(buffer))
                fft_data = np.abs(np.fft.rfft(windowed))
                freqs = np.fft.rfftfreq(len(buffer), 1.0 / audio_core.SAMPLE_RATE)
                freq_points = np.logspace(np.log10(20.0), np.log10(15000.0), self.NUM_SIDE_BARS + 1)

                raw_bars = np.zeros(self.NUM_SIDE_BARS)
                for i in range(self.NUM_SIDE_BARS):
                    idx_s = np.searchsorted(freqs, freq_points[i])
                    idx_e = max(idx_s + 1, np.searchsorted(freqs, freq_points[i + 1]))
                    bin_val = np.max(fft_data[idx_s:idx_e])
                    t_val = i / (self.NUM_SIDE_BARS - 1)
                    comp = (0.4 + (t_val / 0.3) * 0.6) if t_val < 0.3 else (1.0 + ((t_val - 0.3) / 0.7) ** 1.8 * 8.0)
                    raw_bars[i] = bin_val * comp
                return gaussian_filter1d(raw_bars, sigma=1.1)

            left_raw = compute_side_spectrum(audio_core.left_audio_buffer)
            right_raw = compute_side_spectrum(audio_core.right_audio_buffer)

            self.left_fft_smooth = self.left_fft_smooth * 0.7 + left_raw * 0.3
            self.right_fft_smooth = self.right_fft_smooth * 0.7 + right_raw * 0.3

            for index in range(self.NUM_SIDE_BARS):
                l_val = self.left_fft_smooth[index]
                r_val = self.right_fft_smooth[index]
                
                l_bar_len = min(220, np.cbrt(l_val) * self.sensitivity_factor)
                r_bar_len = min(220, np.cbrt(r_val) * self.sensitivity_factor)
                if l_bar_len < 3: l_bar_len = 3
                if r_bar_len < 3: r_bar_len = 3

                l_coords, r_coords = self.get_side_bar_coords(index, l_bar_len, r_bar_len)

                lr, lg, lb = get_dynamic_rgb(l_val, index, self.NUM_SIDE_BARS)
                rr, rg, rb = get_dynamic_rgb(r_val, index, self.NUM_SIDE_BARS)

                self.canvas.coords(self.left_side_rectangles[index], *l_coords)
                self.canvas.itemconfig(self.left_side_rectangles[index], fill=f"#{lr:02x}{lg:02x}{lb:02x}")

                self.canvas.coords(self.right_side_rectangles[index], *r_coords)
                self.canvas.itemconfig(self.right_side_rectangles[index], fill=f"#{rr:02x}{rg:02x}{rb:02x}")
        else:
            windowed = audio_core.audio_buffer * np.hanning(len(audio_core.audio_buffer))
            fft_data = np.abs(np.fft.rfft(windowed))
            freqs = np.fft.rfftfreq(len(audio_core.audio_buffer), 1.0 / audio_core.SAMPLE_RATE)
            freq_points = np.logspace(np.log10(20.0), np.log10(15000.0), self.NUM_BARS + 1)

            raw_bars = np.zeros(self.NUM_BARS)
            for i in range(self.NUM_BARS):
                idx_s = np.searchsorted(freqs, freq_points[i])
                idx_e = max(idx_s + 1, np.searchsorted(freqs, freq_points[i + 1]))
                bin_val = np.max(fft_data[idx_s:idx_e])
                t_val = i / (self.NUM_BARS - 1)
                comp = (0.4 + (t_val / 0.3) * 0.6) if t_val < 0.3 else (1.0 + ((t_val - 0.3) / 0.7) ** 1.8 * 8.0)
                raw_bars[i] = bin_val * comp

            smoothed = gaussian_filter1d(raw_bars, sigma=1.1)
            self.fft_smooth = self.fft_smooth * 0.7 + smoothed * 0.3

            for index, rect_id in enumerate(self.rectangles):
                val = self.fft_smooth[index]
                bar_len = min(130, np.cbrt(val) * self.sensitivity_factor)

                r, g, b = get_dynamic_rgb(val, index, self.NUM_BARS)

                x1_old, y1_old, x2_old, y2_old = self.get_bar_coords(self.prev_mode, index, bar_len)
                x1_new, y1_new, x2_new, y2_new = self.get_bar_coords(self.target_mode, index, bar_len)

                x1 = self.lerp(x1_old, x1_new, self.anim_progress)
                y1 = self.lerp(y1_old, y1_new, self.anim_progress)
                x2 = self.lerp(x2_old, x2_new, self.anim_progress)
                y2 = self.lerp(y2_old, y2_new, self.anim_progress)

                self.canvas.coords(rect_id, x1, y1, x2, y2)
                self.canvas.itemconfig(rect_id, fill=f"#{r:02x}{g:02x}{b:02x}")

        if self.current_mode == 4:
            self.update_horiz_drag_btn_coords()

        self.root.after(20, self.update_ui)