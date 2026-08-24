import pystray
from PIL import Image, ImageDraw

def setup_tray(toggle_mode_cb, set_sens_cb, get_sens_cb, set_theme_cb, get_theme_cb, set_source_cb, get_source_cb, set_opacity_cb, get_opacity_cb, exit_cb):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([16, 16, 48, 48], fill="#00FF7F")
    
    menu = pystray.Menu(
        pystray.MenuItem("切換顯示模式 (圓形 / 橫向)", lambda icon, item: toggle_mode_cb()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("視窗透明度", pystray.Menu(
            pystray.MenuItem("100% (不透明)", lambda: set_opacity_cb(1.0), checked=lambda item: get_opacity_cb() == 1.0),
            pystray.MenuItem("80%", lambda: set_opacity_cb(0.8), checked=lambda item: get_opacity_cb() == 0.8),
            pystray.MenuItem("60%", lambda: set_opacity_cb(0.6), checked=lambda item: get_opacity_cb() == 0.6),
        )),
        pystray.MenuItem("靈敏度設定", pystray.Menu(
            pystray.MenuItem("低 (8.0)", lambda: set_sens_cb(8.0), checked=lambda item: get_sens_cb() == 8.0),
            pystray.MenuItem("中 (14.0)", lambda: set_sens_cb(14.0), checked=lambda item: get_sens_cb() == 14.0),
            pystray.MenuItem("高 (22.0)", lambda: set_sens_cb(22.0), checked=lambda item: get_sens_cb() == 22.0),
            pystray.MenuItem("極高 (32.0)", lambda: set_sens_cb(32.0), checked=lambda item: get_sens_cb() == 32.0),
        )),
        pystray.MenuItem("主題風格", pystray.Menu(
            pystray.MenuItem("霓虹綠 (Classic)", lambda: set_theme_cb("green"), checked=lambda item: get_theme_cb() == "green"),
            pystray.MenuItem("電競藍 (Cyber)", lambda: set_theme_cb("cyan"), checked=lambda item: get_theme_cb() == "cyan"),
            pystray.MenuItem("日落橘 (Sunset)", lambda: set_theme_cb("orange"), checked=lambda item: get_theme_cb() == "orange"),
        )),
        pystray.MenuItem("音源選擇", pystray.Menu(
            pystray.MenuItem("僅系統聲音 (System)", lambda: set_source_cb("system"), checked=lambda item: get_source_cb() == "system"),
            pystray.MenuItem("僅麥克風 (Mic)", lambda: set_source_cb("mic"), checked=lambda item: get_source_cb() == "mic"),
            pystray.MenuItem("混合模式 (Mic & System)", lambda: set_source_cb("both"), checked=lambda item: get_source_cb() == "both"),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("結束程式", lambda icon, item: exit_cb())
    )
    
    return pystray.Icon("FFT_Equalizer", image, "系統音訊等化器", menu)