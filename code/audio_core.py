import soundcard as sc
import numpy as np
import time

SAMPLE_RATE = 44100
BLOCK_SIZE = 1024
audio_buffer = np.zeros(BLOCK_SIZE)

current_audio_source = "system"

def set_audio_source(source_type):
    global current_audio_source
    current_audio_source = source_type

def get_audio_source():
    return current_audio_source

def capture_audio_thread(is_running_cb):
    global audio_buffer
    
    active_source = None
    mic_stream = None
    sys_stream = None
    
    while is_running_cb():
        try:
            source = current_audio_source
            data = np.zeros(BLOCK_SIZE)
            
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
                    if len(sys_data.shape) > 1:
                        sys_data = np.mean(sys_data, axis=1)
                    if len(sys_data) == BLOCK_SIZE:
                        data += sys_data
                except Exception:
                    sys_stream = None

            # 2. 處理麥克風聲音串流
            if source in ["mic", "both"]:
                try:
                    if mic_stream is None:
                        mics = sc.all_microphones()
                        if len(mics) > 0:
                            mic_mic = mics[0]
                            mic_stream = mic_mic.recorder(samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE)
                            mic_stream.__enter__()
                    
                    if mic_stream:
                        mic_data = mic_stream.record(numframes=BLOCK_SIZE)
                        if len(mic_data.shape) > 1:
                            mic_data = np.mean(mic_data, axis=1)
                            
                        if len(mic_data) == BLOCK_SIZE:
                            data += mic_data * 25.0
                except Exception:
                    mic_stream = None

            audio_buffer = data
        except Exception:
            time.sleep(0.1)