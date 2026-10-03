import ctypes

# Windows 虛擬鍵碼 (Virtual Key Codes) 用於模擬媒體與音量控制鍵
VK_MEDIA_NEXT_TRACK = 0xB0
VK_MEDIA_PREV_TRACK = 0xB1
VK_MEDIA_PLAY_PAUSE = 0xB3
VK_VOLUME_MUTE = 0xAD
VK_VOLUME_DOWN = 0xAE
VK_VOLUME_UP = 0xAF

# 預設估計音量（當無法直接向 OS 查詢時作為基準）
_estimated_volume = 50

def _simulate_media_key(vk_code):
    """模擬按下並放開鍵盤上的媒體控制鍵"""
    ctypes.windll.user32.keybd_event(vk_code, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk_code, 0, 2, 0)

def control_media(action):
    """透過系統媒體鍵控制播放與音量"""
    global _estimated_volume
    if action in ["play", "pause", "toggle"]:
        _simulate_media_key(VK_MEDIA_PLAY_PAUSE)
    elif action == "next":
        _simulate_media_key(VK_MEDIA_NEXT_TRACK)
    elif action == "prev":
        _simulate_media_key(VK_MEDIA_PREV_TRACK)
    elif action == "volume_up":
        _simulate_media_key(VK_VOLUME_UP)
        _estimated_volume = min(100, _estimated_volume + 2)
    elif action == "volume_down":
        _simulate_media_key(VK_VOLUME_DOWN)
        _estimated_volume = max(0, _estimated_volume - 2)

def get_system_volume():
    """取得當前系統預估音量 (0~100)"""
    return _estimated_volume

def get_album_art(size=(120, 120)):
    """無 winsdk 環境下返回 None"""
    return None