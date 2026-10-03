import asyncio
import threading
from io import BytesIO
from PIL import Image

# 使用驗證成功的 winsdk 模組
from winsdk.windows.media.control import (# type: ignore
    GlobalSystemMediaTransportControlsSessionManager as MediaManager
)
from winsdk.windows.storage.streams import ( # type: ignore
    DataReader,
    Buffer,
    InputStreamOptions
)

# 建立獨立專用 Event Loop 避免背景 API 鎖死
_loop = asyncio.new_event_loop()

def _start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

_thread = threading.Thread(target=_start_async_loop, args=(_loop,), daemon=True)
_thread.start()

async def _get_media_info_internal():
    try:
        sessions = await MediaManager.request_async()
        current_session = sessions.get_current_session()
        
        if not current_session:
            return None

        info = await current_session.try_get_media_properties_async()
        
        # 讀取系統播放狀態 (4 代表 Playing)
        playback_info = current_session.get_playback_info()
        is_playing = (playback_info.playback_status == 4) if playback_info else False
        
        # 讀取專輯封面
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
                
                image_obj = Image.open(BytesIO(image_bytes))
            except Exception:
                image_obj = None

        return {
            "title": info.title,
            "artist": info.artist,
            "image": image_obj,
            "is_playing": is_playing
        }
    except Exception:
        return None

def get_media_info():
    """提供同步 call 介面給 UI 使用"""
    try:
        future = asyncio.run_coroutine_threadsafe(_get_media_info_internal(), _loop)
        return future.result(timeout=2.0)
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