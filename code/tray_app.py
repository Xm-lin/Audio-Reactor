import pystray
from PIL import Image, ImageDraw

def setup_tray(set_mode_cb, get_mode_cb, set_sens_cb, get_sens_cb, set_theme_cb, get_theme_cb, set_source_cb, get_source_cb, set_opacity_cb, get_opacity_cb, exit_cb):
    image = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([16, 16, 48, 48], fill="#00FF7F")
    
    icon = None

    def make_action(cb, value):
        def action(item):
            cb(value)
            if icon:
                icon.update_menu()
        return action

    # 移除所有選單項目的 checked 參數，只保留點擊觸發的動作
    menu = pystray.Menu(
        pystray.MenuItem("顯示模式", pystray.Menu(
            pystray.MenuItem("圓形互動模式", make_action(set_mode_cb, 0)),
            pystray.MenuItem("橫向頂部模式", make_action(set_mode_cb, 4)),
            pystray.MenuItem("左右側邊雙聲道模式", make_action(set_mode_cb, 5)),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("視窗透明度", pystray.Menu(
            pystray.MenuItem("100% (不透明)", make_action(set_opacity_cb, 1.0)),
            pystray.MenuItem("80%", make_action(set_opacity_cb, 0.8)),
            pystray.MenuItem("60%", make_action(set_opacity_cb, 0.6)),
        )),
        pystray.MenuItem("靈敏度設定", pystray.Menu(
            pystray.MenuItem("低 (8.0)", make_action(set_sens_cb, 8.0)),
            pystray.MenuItem("中 (14.0)", make_action(set_sens_cb, 14.0)),
            pystray.MenuItem("高 (22.0)", make_action(set_sens_cb, 22.0)),
            pystray.MenuItem("極高 (32.0)", make_action(set_sens_cb, 32.0)),
        )),
        pystray.MenuItem("主題風格", pystray.Menu(
            pystray.MenuItem("霓虹綠 (Classic)", make_action(set_theme_cb, "green")),
            pystray.MenuItem("電競藍 (Cyber)", make_action(set_theme_cb, "cyan")),
            pystray.MenuItem("日落橘 (Sunset)", make_action(set_theme_cb, "orange")),
            pystray.MenuItem("自訂色調 (Custom)...", make_action(set_theme_cb, "custom")),
        )),
        pystray.MenuItem("音源選擇", pystray.Menu(
            pystray.MenuItem("僅系統聲音 (System)", make_action(set_source_cb, "system")),
            pystray.MenuItem("僅麥克風 (Mic)", make_action(set_source_cb, "mic")),
            pystray.MenuItem("混合模式 (Mic & System)", make_action(set_source_cb, "both")),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("結束程式", lambda icon, item: exit_cb())
    )

    icon = pystray.Icon("FFT_Equalizer", image, "系統音訊等化器", menu=menu)
    
    def update_menu():
        try:
            icon.update_menu()
        except Exception:
            pass
            
    icon.update_tray_menu = update_menu
    return icon