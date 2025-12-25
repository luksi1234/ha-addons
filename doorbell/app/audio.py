import os
import logging
from pydub import AudioSegment
from const import AUDIO_DIR, ALLOWED_EXTENSIONS
from controller import audio_controller
from io import BytesIO


_LOGGER = logging.getLogger(__name__)


class AudioPlaybackError(Exception):
    pass


def play_local_file(filename: str, volume: int, loop: bool, number: int):
    # Validate filename
    if any(x in filename for x in ["..", "/", "\\"]):
        raise AudioPlaybackError("Illegal filename")

    _, ext = os.path.splitext(filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise AudioPlaybackError("Unsupported file extension")

    path = os.path.join(AUDIO_DIR, filename)

    _LOGGER.debug("AUDIO_DIR: %s", path)

    if not os.path.isfile(path):
        raise AudioPlaybackError("File not found")

    # Load audio
    try:
        audio = AudioSegment.from_file(path)
    except Exception as e:
        raise AudioPlaybackError(f"Error decoding audio: {e}")

    # Volume adjustment
    audio += (volume - 100)

    # Start playback
    audio_controller.play(audio,loop,number)

def play_stream(stream: bytes, volume: int, loop: bool, number: int):
    # Validate filename

    # Load audio
    try:
        audio = AudioSegment.from_file(BytesIO(stream))
    except Exception as e:
        raise AudioPlaybackError(f"Error decoding audio: {e}")

    # Volume adjustment
    audio += (volume - 100)

    # Start playback
    audio_controller.play(audio,loop,number)
