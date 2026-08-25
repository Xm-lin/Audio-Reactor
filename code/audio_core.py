import soundcard as sc
import numpy as np
import time

SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
audio_buffer = np.zeros(BLOCK_SIZE)
left_audio_buffer = np.zeros(BLOCK_SIZE)
right_audio_buffer = np.zeros(BLOCK_SIZE)

current_audio_source = "system"

def set_audio_source(source_type):
    global current_audio_source
    current_audio_source = source_type

def get_audio_source():
    return current_audio_source

def capture_audio_thread(is_running_cb):
    global audio_buffer, left_audio_buffer, right_audio_buffer
    
    active_source = None
    mic_stream = None
    sys_stream = None
    
    while is_running_cb():
        try:
            source = current_audio_source
            data = np.zeros(BLOCK_SIZE)
            l_data = np.zeros(BLOCK_SIZE)
            r_data = np.zeros(BLOCK_SIZE)
            
            # 如果音源改變了，安全關閉舊的串流
            if active_source != source:
                active_source = source
                if mic_stream:
                    try: mic_stream.__exit__(None, None, None)
                    except: pass
                    mic_stream = None
                if sys_stream:
                    try: sys_stream.__exit__(None, None, None)
                    except: pass
                    sys_stream = None

            # 1. 處理系統聲音串流
            if source in ["system", "both"]:
                try:
                    if sys_stream is None:
                        mic_sys = sc.get_microphone(sc.default_speaker().name, include_loopback=True)
                        sys_stream = mic_sys.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
                        sys_stream.__enter__()
                    
                    sys_data = sys_stream.record(numframes=BLOCK_SIZE)
                    if len(sys_data.shape) > 1 and sys_data.shape[1] >= 2:
                        l_data += sys_data[:, 0]
                        r_data += sys_data[:, 1]
                        sys_mono = np.mean(sys_data, axis=1)
                    else:
                        flat = sys_data.flatten()
                        l_data += flat
                        r_data += flat
                        sys_mono = flat
                    if len(sys_mono) == BLOCK_SIZE:
                        data += sys_mono
                except Exception:
                    sys_stream = None

            # 2. 處理麥克風聲音串流
            if source in ["mic", "both"]:
                try:
                    if mic_stream is None:
                        mic_mic = sc.default_microphone()
                        if mic_mic:
                            mic_stream = mic_mic.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
                            mic_stream.__enter__()
                    
                    if mic_stream:
                        mic_data = mic_stream.record(numframes=BLOCK_SIZE)
                        #print("目前麥克風最大音量數值：", np.max(np.abs(mic_data)))
                        if len(mic_data.shape) > 1 and mic_data.shape[1] >= 2:
                            l_data += mic_data[:, 0] * 25.0
                            r_data += mic_data[:, 1] * 25.0
                            mic_mono = np.mean(mic_data, axis=1) * 25.0
                        elif len(mic_data) > 0:
                            flat = mic_data.flatten() * 25.0
                            l_data += flat
                            r_data += flat
                            mic_mono = flat
                        if len(mic_mono) == BLOCK_SIZE:
                            data += mic_mono
                except Exception:
                    mic_stream = None

            audio_buffer = data
            left_audio_buffer = l_data
            right_audio_buffer = r_data
        except Exception:
            time.sleep(0.1)