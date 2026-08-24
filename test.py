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

async def check_media_and_thumbnail():
    sessions = await MediaManager.request_async()
    current_session = sessions.get_current_session()
    
    if not current_session:
        print("目前沒有偵測到任何正在播放的媒體！")
        return

    info = await current_session.try_get_media_properties_async()
    
    print(f"🎵 歌名 (Title): {info.title}")
    print(f"🎤 演出者 (Artist): {info.artist}")
    
    # 檢查是否有縮圖串流參考
    thumb_stream_ref = info.thumbnail
    if thumb_stream_ref is not None:
        print("是否有照片: yes")
        
        # 開啟串流並在記憶體中讀取
        readable_stream = await thumb_stream_ref.open_read_async()
        size = readable_stream.size
        
        # 建立緩衝區並讀取資料
        buffer = Buffer(size)
        await readable_stream.read_async(
            buffer, size, InputStreamOptions.READ_AHEAD
        )
        
        # 用 DataReader 轉換
        reader = DataReader.from_buffer(buffer)
        
        # 建立指定大小的 bytearray 接收資料
        image_bytes = bytearray(size)
        reader.read_bytes(image_bytes)
        
        # 用 Pillow 載入記憶體中的 bytes
        image = Image.open(BytesIO(image_bytes))
        print(f"🖼️ 照片已成功讀取到記憶體！圖片格式: {image.format}, 尺寸: {image.size}")
        
        # 直接在畫面上彈出打開照片
        image.show()
        
    else:
        print("是否有照片: no")

if __name__ == '__main__':
    asyncio.run(check_media_and_thumbnail())