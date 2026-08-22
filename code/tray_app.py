import pystray
from PIL import Image, ImageDraw

def setup_tray(toggle_mode_cb, set_sens_cb, get_sens_cb, exit_cb):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([16, 16, 48, 48], fill="#00FF7F")
    
    menu = pystray.Menu(
        pystray.MenuItem("切換顯示模式 (圓形 / 橫向)", lambda icon, item: toggle_mode_cb()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("靈敏度設定", pystray.Menu(
            pystray.MenuItem("低 (8.0)", lambda: set_sens_cb(8.0), checked=lambda item: get_sens_cb() == 8.0),
            pystray.MenuItem("中 (14.0)", lambda: set_sens_cb(14.0), checked=lambda item: get_sens_cb() == 14.0),
            pystray.MenuItem("高 (22.0)", lambda: set_sens_cb(22.0), checked=lambda item: get_sens_cb() == 22.0),
            pystray.MenuItem("極高 (32.0)", lambda: set_sens_cb(32.0), checked=lambda item: get_sens_cb() == 32.0),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("結束程式", lambda icon, item: exit_cb())
    )
    
    return pystray.Icon("FFT_Equalizer", image, "系統音訊等化器", menu)