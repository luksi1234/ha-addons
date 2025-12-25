import logging
import os

from const import LOG_LEVEL, HOST, PORT, ADDON_SLUG, TTS_LANG

from flask import Flask, request, jsonify
from flask_cors import CORS
from audio import play_local_file, AudioPlaybackError, play_stream
from controller import audio_controller
from pico2wave import PicoTTS
from beepnoise import BeepNoise
import wave
import socket
from io import BytesIO



#logging.basicConfig(level=logging.INFO)
logging.basicConfig(level=LOG_LEVEL)

_LOGGER = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

@app.route("/tts", methods=["POST"])
def tts():
    try:
        data = request.get_json(force=True)
        if data is None:
            _LOGGER.debug("Invalid content type or empty payload")
            return jsonify({"error": "Invalid content type or empty payload"}), 400
        if not data or "message" not in data:
            _LOGGER.debug("Missing parameter 'message'")
            return jsonify({"error": "Missing 'message'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    message = data["message"]
    volume = data.get("volume", 100)
    number = 1
    loop = False

    picotts = PicoTTS()
    picotts.voice = "de-DE"
    picotts.voice = TTS_LANG
    wavs = picotts.synth_wav(message)
    wav = wave.open(BytesIO(wavs))
    _LOGGER.debug("tts voices: %s",picotts.voices)
    _LOGGER.debug("tts channels: %s", wav.getnchannels())
    _LOGGER.debug("tts framerate: %s", wav.getframerate())
    _LOGGER.debug("tts frames: %s", wav.getnframes())

    try:
        play_stream(wavs, volume, False, 1)
        return jsonify({"status": "playing", "message": message})
    except AudioPlaybackError as e:
    #except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/beep", methods=["POST"])
def beep():
    try:
        data = request.get_json(force=True)
        if data is None:
            _LOGGER.debug("Invalid content type or empty payload")
            return jsonify({"error": "Invalid content type or empty payload"}), 400
        if not data or "number" not in data:
            _LOGGER.debug("Missing parameter 'number'")
            return jsonify({"error": "Missing 'number'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    _LOGGER.debug("beep data: %s", data)

    number = data.get("number",1)
    volume = data.get("volume", 100)

    beepwav = BeepNoise()
    wav = beepwav.beep()

    if wav == None:
        _LOGGER.debug("beep wav is empty!!!")

    #_LOGGER.debug("beep channels: %s", wav.getnchannels())
    #_LOGGER.debug("beep framerate: %s", wav.getframerate())
    #_LOGGER.debug("beep frames: %s", wav.getnframes())

    try:
        play_stream(wav, volume, False, number)
        return jsonify({"status": "playing", "number": number})
    except AudioPlaybackError as e:
    #except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/loop", methods=["POST"])
def loop():
    try:
        data = request.get_json(force=True)
        if data is None:
            _LOGGER.debug("Invalid content type or empty payload")
            return jsonify({"error": "Invalid content type or empty payload"}), 400
        if not data or "filename" not in data:
            _LOGGER.debug("Missing parameter 'filename'")
            return jsonify({"error": "Missing 'filename'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    filename = data["filename"]
    volume = data.get("volume", 100)

    _LOGGER.debug("loop filename %s", filename)
    _LOGGER.debug("loop volume %s", volume)

    try:
        play_local_file(filename, volume, True, 1)
        return jsonify({"status": "playing", "filename": filename})
    except AudioPlaybackError as e:
    #except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route("/play", methods=["POST"])
def play():
    try:
        data = request.get_json(force=True)
        if data is None:
            _LOGGER.debug("Invalid content type or empty payload")
            return jsonify({"error": "Invalid content type or empty payload"}), 400
        if not data or "filename" not in data:
            _LOGGER.debug("Missing parameter 'filename'")
            return jsonify({"error": "Missing 'filename'"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    filename = data["filename"]
    volume = data.get("volume", 100)
    _LOGGER.debug("play filename %s", filename)
    _LOGGER.debug("play volume %s", volume)

    try:
        play_local_file(filename, volume, False, 1)
        return jsonify({"status": "playing", "filename": filename})
    except AudioPlaybackError as e:
    #except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/stop", methods=["GET"])
def stop():
    audio_controller.stop()
    return jsonify({"status": "stopped"})


@app.route("/status", methods=["GET"])
def status():
    is_running = audio_controller.status()
    if is_running:
        return jsonify({"status": "running"})
    else:
        return jsonify({"status": "stopped"})
    #return jsonify({"status": "playing"})


@app.route("/info", methods=["GET"])
def info():
    ipaddr = request.environ.get("SERVER_NAME")
    hostname = socket.gethostname()
    port = request.environ.get("SERVER_PORT")
    return jsonify({"info": {"name": ADDON_SLUG,"host": hostname, "ip": ipaddr, "port": port}})
    #return jsonify({"status": "playing"})


if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
