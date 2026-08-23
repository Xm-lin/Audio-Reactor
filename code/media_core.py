import ctypes

# Windows 虛擬鍵碼 (Virtual Key Codes) 用於模擬媒體按鍵
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3

def _simulate_media_key(vk_code):
    """模擬按下並放開鍵盤上的媒體控制鍵"""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)

def control_media(action):
    """透過系統媒體鍵控制播放：play, pause, toggle, next, prev"""
    if action in ["play", "pause", "toggle"]:
        _simulate_media_key(VK_MEDIA_PLAY_PAUSE)
    elif action == "next":
        _simulate_media_key(VK_MEDIA_NEXT_TRACK)
    elif action == "prev":
        _simulate_media_key(VK_MEDIA_PREV_TRACK)

def get_album_art(size=(120, 120)):
    """無 winsdk 環境下返回 None"""
    return None