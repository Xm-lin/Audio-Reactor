import threading
import warnings
import tkinter as tk

import audio_core
from equalizer_window import EqualizerWindow
from tray_app import setup_tray

# 濾除 soundcard 的資料斷訊警告
try:
    import soundcard
    warnings.filterwarnings("ignore", category=soundcard.SoundcardRuntimeWarning)
except ImportError:
    pass

# --- 初始化 Tkinter 視窗 ---
root = tk.Tk()
root.title("雙模式系統音訊 FFT 等化器")

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()

root.geometry(f"{screen_w}x{screen_h}+0+0")
root.overrideredirect(True)

TRANS_COLOR = "#000001"
root.configure(bg=TRANS_COLOR)
root.wm_attributes("-transparentcolor", TRANS_COLOR)
root.wm_attributes("-topmost", True)

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

# 建立等化器 UI 核心物件
eq_win = EqualizerWindow(root, screen_w, screen_h, on_closing)

# 建立系統匣物件
tray_icon = setup_tray(
    toggle_mode_cb=eq_win.toggle_mode,
    set_sens_cb=eq_win.set_sensitivity,
    get_sens_cb=eq_win.get_sensitivity,
    set_theme_cb=eq_win.set_theme,
    get_theme_cb=eq_win.get_theme,
    set_source_cb=eq_win.set_audio_source,
    get_source_cb=eq_win.get_audio_source,
    set_opacity_cb=eq_win.change_opacity,  # 新增這一行
    get_opacity_cb=eq_win.get_opacity,    # 新增這一行
    exit_cb=lambda: root.after(0, on_closing)
)

# 啟動音訊與系統匣背景執行緒
threading.Thread(target=audio_core.capture_audio_thread, args=(get_is_running,), daemon=True).start()
threading.Thread(target=tray_icon.run, daemon=True).start()

root.bind("<Escape>", on_closing)
root.mainloop()