import simpleaudio as sa
import threading
import time
import logging

_LOGGER = logging.getLogger(__name__)

class AudioController:
    def __init__(self):
        self.lock = threading.Lock()
        self.play_obj = None
        self.max_duration = 60000 # milliseconds 60000=10min
        self.thread = None
        self.audio = None
        self.running = False

    def play_thread(self,loop,number):

        loop_cnt = 0
        start_time = time.time()
        elapsed = 0

        while self.running:
            play_obj = sa.play_buffer(
                self.audio.raw_data,
                num_channels=self.audio.channels,
                bytes_per_sample=self.audio.sample_width,
                sample_rate=self.audio.frame_rate
            )

            loop_cnt +=1
            _LOGGER.debug("play elapsed %s", elapsed)

            # Wait until playback finishes or force stop
            while play_obj.is_playing() and self.running:
                elapsed = (time.time() - start_time) * 1000
                if elapsed > self.max_duration:
                    _LOGGER.debug("max runtime reached")
                    self.running = False
                time.sleep(0.01)

            if not loop and number > 1 and loop_cnt >= number:
                play_obj.stop()
                self.running = False
                break

            if not self.running:
                play_obj.stop()
                _LOGGER.debug("stop triggered")
                break

            if not loop and number == 1:
                # Played once, then exit
                _LOGGER.debug("normal end")
                break

        _LOGGER.debug("end play thread")

    def play(self, audio_segment,loop,number):

        if self.running:
            self.running = False
            self.thread.join()


        self.audio = audio_segment

        self.running = True
        self.thread = threading.Thread(
            target=self.play_thread,
            args=(loop,number,),
            daemon=True
        )
        self.thread.start()

    def stop(self):
        self.running = False

    def status(self):
        if self.running:
            return True
        else:
            return False

audio_controller = AudioController()
