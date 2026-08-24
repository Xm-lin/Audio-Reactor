import asyncio
from io import BytesIO
from PIL import Image
from winrt.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
)
from winrt.windows.storage.streams import (
    DataReader,
    Buffer,
    InputStreamOptions
)

async def get_media_info_async():
    try:
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        
        if not current_session:
            return None

        info = await current_session.try_get_media_properties_async()
        
        # --- 新增：讀取系統真實的播放/暫停狀態 ---
        playback_info = current_session.get_playback_info()
        # 狀態碼 4 代表正在播放中 (Playing)
        is_playing = (playback_info.playback_status == 4) if playback_info else False
        
        # 讀取封面照片（若有的話）
        image_obj = None
        thumb_stream_ref = info.thumbnail
        if thumb_stream_ref is not None:
            try:
                readable_stream = await thumb_stream_ref.open_read_async()
                size = readable_stream.size
                
                buffer = Buffer(size)
                await readable_stream.read_async(
                    buffer, size, InputStreamOptions.READ_AHEAD
                )
                
                reader = DataReader.from_buffer(buffer)
                image_bytes = bytearray(size)
                reader.read_bytes(image_bytes)
                
                # 轉換為 Pillow 圖片物件
                image_obj = Image.open(BytesIO(image_bytes))
            except Exception:
                image_obj = None

        return {
            "title": info.title,
            "artist": info.artist,
            "image": image_obj,
            "is_playing": is_playing  # 將真實狀態回傳給 UI
        }
    except Exception:
        return None

def get_media_info():
    """同步包裝函式，讓主執行緒或背景執行緒可以輕鬆呼叫"""
    try:
        return asyncio.run(get_media_info_async())
    except Exception:
        return None

if __name__ == '__main__':
    media_data = get_media_info()
    if media_data:
        print(f"🎵 歌名: {media_data['title']}")
        print(f"🎤 演出者: {media_data['artist']}")
        print("🖼️ 照片:", "有" if media_data['image'] else "無")
        print("▶️ 狀態:", "播放中" if media_data.get('is_playing') else "已暫停")
    else:
        print("目前沒有偵測到任何正在播放的媒體！")