import sounddevice as sd
import soundfile as sf
import numpy as np
import threading
import time
import io
import logging
import queue
from scipy import signal


#TODO mac duration of loop should be configurable
MAX_LOOP_MS = 60000


from const import LOG_LEVEL, DOORBELL_OUTPUT

logging.basicConfig(level=LOG_LEVEL)

_LOGGER = logging.getLogger(__name__)





import sounddevice as sd
import numpy as np
import threading
import time
from scipy.signal import resample


class AudioPlayer2:

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
        self.loop = False
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

                outdata[:] = self.audio_data[self.position:end_pos]
                self.position = end_pos

            else:
                # End of audio reached
                remaining = len(self.audio_data) - self.position

                if remaining > 0:
                    outdata[:remaining] = self.audio_data[self.position:]
                else:
                    remaining = 0

                if self.loop:
                    if self.max_loop_time is not None:
                        if time.time() - self.play_start_time >= self.max_loop_time:
                            self.audio_data = None
                            outdata[remaining:] = 0
                            return

                    # restart from beginning
                    restart_len = frames - remaining
                    outdata[remaining:] = self.audio_data[:restart_len]
                    self.position = restart_len
                else:
                    # stop playback
                    outdata[remaining:] = 0
                    self.audio_data = None

    def _apply_start_ramp(self, audio, ramp_samples=128):
        ramp_samples = min(ramp_samples, len(audio))
        ramp = np.linspace(0.0, 1.0, ramp_samples)
        audio[:ramp_samples] *= ramp[:, None]
        return audio

    # =====================================================
    # Public API
    # =====================================================

    def play(self, audio_data, input_samplerate, loop=False, num_loops=1, max_loop_time=None):

        audio_data = audio_data.astype(np.float32)
        audio_data = self._resample_if_needed(audio_data, input_samplerate)
        audio_data = self._adapt_channels(audio_data)

        with self.lock:
            self.audio_data = audio_data
            self.position = 0
            self.loop = loop
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










########################################################
#########################################################
######################################################

class AudioPlayer:
    def __init__(self, source, loops=1, volume=1.0, samplerate=None):

        #get supported samplerate
        device_info = sd.query_devices(DOORBELL_OUTPUT, 'output')
        _LOGGER.debug("device info: \n%s", device_info)
        default_samplerate=device_info['default_samplerate']


        # ------------------------------------
        # Source handling
        # ------------------------------------
        if isinstance(source, np.ndarray):
            _LOGGER.debug("handling bytearray")
            if samplerate is None:
                raise ValueError("samplerate required for numpy source")

            self.data = source.astype(np.float32)
            self.samplerate = samplerate

        else:
            _LOGGER.debug("handling bytearfile")
            if isinstance(source, (bytes, bytearray)):
                source = io.BytesIO(source)

            self.data, self.samplerate = sf.read(source, dtype="float32")

            if self.data.ndim == 1:
                self.data = self.data[:, np.newaxis]

        _LOGGER.debug("input samplerate: %s", self.samplerate)


        if(self.samplerate != default_samplerate):
            _LOGGER.debug("doing resample ...")
            number_of_samples = int(len(self.data) * default_samplerate / self.samplerate)
            resampled = signal.resample(self.data, number_of_samples)
            self.data = resampled
            self.samplerate = default_samplerate


        self.audio_queue = queue.Queue()
        # ------------------------------------
        self.channels = self.data.shape[1]
        self.total_frames = len(self.data)

        self.volume = float(volume)
        self.loops = loops

        self.position = 0
        self.current_loop = 0
        self.start_time = None

        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._should_stop_after_block = False

        _LOGGER.debug("output samplerate: %s", self.samplerate)
        _LOGGER.debug("output channels: %s", self.channels)

        self.stream = sd.OutputStream(
            device=DOORBELL_OUTPUT,
            samplerate=self.samplerate,
            channels=self.channels,
            dtype="float32",
            callback=self._callback,
            #callback=self._callback2,
            #callback=self._callback3,
            blocksize=2048,
            latency="high"
        )

    # --------------------------------------------------
    # PortAudio-safe callback (NO premature stop)
    # --------------------------------------------------
    def _callback(self, outdata, frames, time_info, status):

        #time.sleep(0.05)  # Avoid busy waiting

        outdata.fill(0)

        if self._stop_event.is_set():
            raise sd.CallbackStop()

        # Stop AFTER last buffer was fully sent
        if self._should_stop_after_block:
            raise sd.CallbackStop()

        # Hard loop time cap
        if self.start_time and (time.time() - self.start_time) * 1000 >= MAX_LOOP_MS:
            print("Max loop duration reached, stopping after this block")
            self._should_stop_after_block = True
            return

        filled = 0



        while filled < frames:
            remaining_data = self.total_frames - self.position
            remaining_out = frames - filled

            if remaining_data >= remaining_out:
                outdata[filled:filled + remaining_out] = \
                    self.data[self.position:self.position + remaining_out]
                self.position += remaining_out
                filled += remaining_out
            else:
                # End of audio
                outdata[filled:filled + remaining_data] = \
                    self.data[self.position:]
                filled += remaining_data

                self.current_loop += 1
                if self.loops == -1 or self.current_loop < self.loops:
                    self.position = 0
                else:
                    # IMPORTANT: do NOT stop yet
                    print("Audio finished, stopping after this block")
                    self._should_stop_after_block = True
                    break

        outdata *= self.volume


    # --------------------------------------------------
    # Controls
    # --------------------------------------------------
    def play(self):
        self.position = 0
        self.current_loop = 0
        self.start_time = time.time()
        self._should_stop_after_block = False
        self._stop_event.clear()
        self.stream.start()

    def stop(self):
        self._stop_event.set()
        if self.stream.active:
            self.stream.stop()

    def close(self):
        self.stop()
        self.stream.close()

    def set_volume(self, volume):
        self.volume = max(0.0, min(1.0, float(volume)))
