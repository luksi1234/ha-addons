import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import time
import io
import logging
import queue
from scipy import signal
from scipy.signal import resample


#TODO mac duration of loop should be configurable
MAX_LOOP_MS = 60000


from const import LOG_LEVEL, DOORBELL_OUTPUT

logging.basicConfig(level=LOG_LEVEL)

_LOGGER = logging.getLogger(__name__)




class AudioPlayer:

    def __init__(self, device=None, channels=2, blocksize=2048):

        device_info = sd.query_devices(device, 'output')

        self.device = device
        self.samplerate = int(device_info['default_samplerate'])
        self.channels = channels
        self.blocksize = blocksize

        self.lock = threading.Lock()

        # Playback state
        self.audio_data = None
        self.position = 0
        self._loop = False
        self.num_loops = 0
        self.max_loop_time = None
        self.play_start_time = None

        sd.default.latency = 'high'

        self.stream = sd.OutputStream(
            device=self.device,
            samplerate=self.samplerate,
            channels=self.channels,
            blocksize=self.blocksize,
            dtype='float32',
            callback=self._callback
        )

        self.stream.start()

    # =====================================================
    # Format helpers
    # =====================================================

    def _adapt_channels(self, audio):
        if audio.ndim == 1:
            audio = audio[:, np.newaxis]

        if audio.shape[1] == self.channels:
            return audio

        if audio.shape[1] == 1 and self.channels == 2:
            return np.repeat(audio, 2, axis=1)

        if audio.shape[1] == 2 and self.channels == 1:
            return audio.mean(axis=1, keepdims=True)

        raise ValueError("Unsupported channel format")

    def _resample_if_needed(self, audio, input_sr):
        if input_sr == self.samplerate:
            return audio

        new_len = int(len(audio) * self.samplerate / input_sr)
        return resample(audio, new_len, axis=0)

    # =====================================================
    # Callback
    # =====================================================

    def _callback(self, outdata, frames, time_info, status):

        if status:
            print(status)

        with self.lock:

            if self.audio_data is None:
                outdata[:] = np.zeros((frames, self.channels), dtype=np.float32)
                return

            end_pos = self.position + frames

            if end_pos <= len(self.audio_data):
                _LOGGER.debug("playing block: pos %s - %s", self.position, end_pos)
                outdata[:] = self.audio_data[self.position:end_pos]
                self.position = end_pos

            else:
                # End of audio reached
                remaining = len(self.audio_data) - self.position

                if remaining > 0:
                    outdata[:remaining] = self.audio_data[self.position:]
                    _LOGGER.debug("end playing block: pos %s - %s (end)", self.position, len(self.audio_data))
                    self.num_loops -= 1
                else:
                    remaining = 0

                if self._loop:
                    _LOGGER.debug("looping enabled, restarting audio")
                    if self.max_loop_time is not None:
                        if time.time() - self.play_start_time >= self.max_loop_time:
                            self.audio_data = None
                            outdata[remaining:] = 0
                            return

                    # restart from beginning
                    restart_len = frames - remaining
                    outdata[remaining:] = self.audio_data[:restart_len]
                    self.position = restart_len
                elif self.num_loops > 0:
                    _LOGGER.debug("looping enabled, %s loops remaining", self.num_loops)

                    # restart from beginning
                    restart_len = frames - remaining
                    outdata[remaining:] = self.audio_data[:restart_len]
                    self.position = restart_len
                else:
                    # stop playback
                    outdata[remaining:] = 0
                    self.audio_data = None

            outdata *= self.volume

    def _apply_start_ramp(self, audio, ramp_samples=128):
        ramp_samples = min(ramp_samples, len(audio))
        ramp = np.linspace(0.0, 1.0, ramp_samples)
        audio[:ramp_samples] *= ramp[:, None]
        return audio

    # =====================================================
    # Public API
    # =====================================================

    def play_bytearray(self, audio_data, input_samplerate, volume=1.0, loop=False, num_loops=1, max_loop_time=None):

        if isinstance(audio_data, (bytes, bytearray)):
            audio_data = io.BytesIO(audio_data)
            data, samplerate = sf.read(audio_data, dtype="float32")
            _LOGGER.debug("handling bytearray, input samplerate: %s", samplerate)

        else:
            raise ValueError("wrong audio format, expected numpy array")

        audio_data = data.astype(np.float32)
        audio_data = self._resample_if_needed(audio_data, samplerate)
        audio_data = self._adapt_channels(audio_data)
        #audio_data = self._apply_start_ramp(audio_data)

        with self.lock:
            self.audio_data = audio_data
            self.position = 0
            self.volume = volume
            self.loop = loop
            self.num_loops = num_loops
            self.max_loop_time = max_loop_time
            self.play_start_time = time.time()

    def play_numpy(self, audio_data, input_samplerate, volume=1.0, loop=False, num_loops=1, max_loop_time=None):

        if isinstance(audio_data, np.ndarray):
            _LOGGER.debug("handling numpy array")
            if input_samplerate is None:
                raise ValueError("input_samplerate required for numpy source")

            audio_data = audio_data.astype(np.float32)
            samplerate = input_samplerate

        else:
            raise ValueError("wrong audio format, expected numpy array")

        audio_data = audio_data.astype(np.float32)
        audio_data = self._resample_if_needed(audio_data, input_samplerate)
        audio_data = self._adapt_channels(audio_data)
        #audio_data = self._apply_start_ramp(audio_data)

        with self.lock:
            self.audio_data = audio_data
            self.position = 0
            self.volume = volume
            self.loop = loop
            self.num_loops = num_loops
            self.max_loop_time = max_loop_time
            self.play_start_time = time.time()

    def loop(self, audio_source, volume=1.0, max_loop_time=None):

        _LOGGER.debug("starting loop playback with max_loop_time=%s ms", max_loop_time)

        loop = True
        num_loops = 1

        audio_data, samplerate = sf.read(audio_source, dtype="float32")
        audio_data = audio_data.astype(np.float32)
        audio_data = self._resample_if_needed(audio_data, samplerate)
        audio_data = self._adapt_channels(audio_data)

        _LOGGER.debug("audio data shape after resampling/adapting: %s", audio_data.shape)

        with self.lock:
            self.audio_data = audio_data
            self.position = 0
            self._loop = loop
            self.volume = volume
            self.num_loops = num_loops
            self.max_loop_time = max_loop_time
            self.play_start_time = time.time()

        _LOGGER.debug("loop playback started")


    def play(self, audio_source, volume=1.0):

        loop = False
        num_loops = 1
        max_loop_time = None

        audio_data, samplerate = sf.read(audio_source, dtype="float32")
        audio_data = audio_data.astype(np.float32)
        audio_data = self._resample_if_needed(audio_data, samplerate)
        audio_data = self._adapt_channels(audio_data)

        with self.lock:
            self.audio_data = audio_data
            self.position = 0
            self.loop = loop
            self.volume = volume
            self.num_loops = num_loops
            self.max_loop_time = max_loop_time
            self.play_start_time = time.time()

    def stop(self):
        with self.lock:
            self.audio_data = None
            self.position = 0

    def close(self):
        self.stop()
        self.stream.stop()
        self.stream.close()






