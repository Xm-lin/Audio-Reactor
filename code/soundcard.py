import numpy as np
import soundcard as sc
import threading
import time

SAMPLE_RATE = 44100
BLOCK_SIZE = 2048
audio_buffer = np.zeros(BLOCK_SIZE)

def capture_audio_thread(get_is_running):
    global audio_buffer
    while get_is_running():
        try:
            speaker = sc.default_speaker()
            m_mic = sc.get_microphone(id=speaker.id, include_loopback=True)
            with m_mic.recorder(samplerate=SAMPLE_RATE, channels=1) as temp_recorder:
                while get_is_running():
                    current_speaker = sc.default_speaker()
                    if current_speaker.id != speaker.id:
                        break
                    data = temp_recorder.record(numframes=BLOCK_SIZE)
                    audio_buffer = data[:, 0]
        except Exception:
            time.sleep(1.0)