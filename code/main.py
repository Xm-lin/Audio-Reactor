import threading
import warnings
import tkinter as tk

import audio_core
from equalizer_window import EqualizerWindow
from tray_app import setup_tray

try:
    import soundcard
    warnings.filterwarnings("ignore", category=soundcard.SoundcardRuntimeWarning)
except ImportError:
    pass

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

def update_tray_menu():
    if tray_icon:
        try:
            tray_icon.update_menu()
        except Exception:
            pass

eq_win = EqualizerWindow(
    root, screen_w, screen_h, on_closing, 
    update_tray_cb=update_tray_menu
)

tray_icon = setup_tray(
    set_mode_cb=eq_win.set_mode,
    get_mode_cb=eq_win.get_mode,
    set_sens_cb=eq_win.set_sensitivity,
    get_sens_cb=eq_win.get_sensitivity,
    set_theme_cb=eq_win.set_theme,
    get_theme_cb=eq_win.get_theme,
    set_source_cb=eq_win.set_audio_source,
    get_source_cb=eq_win.get_audio_source,
    set_opacity_cb=eq_win.change_opacity,
    get_opacity_cb=eq_win.get_opacity,
    exit_cb=lambda: root.after(0, on_closing)
)

threading.Thread(target=audio_core.capture_audio_thread, args=(get_is_running,), daemon=True).start()
threading.Thread(target=tray_icon.run, daemon=True).start()

root.bind("<Escape>", on_closing)
root.mainloop()