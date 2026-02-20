import uvicorn
import logging
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, field_validator
import threading
from pico2wave import PicoTTS, VOICES
import beepnoise2
import wave
import soundfile as sf
import numpy as np
from io import BytesIO
from time import sleep


# import your AudioPlayer class here
from audio_player import AudioPlayer

from const import LOG_LEVEL, HOST, PORT, ADDON_SLUG, TTS_LANG
from const import AUDIO_DIR, ALLOWED_EXTENSIONS, DOORBELL_OUTPUT





app = FastAPI(title="Doorbell API")

logging.basicConfig(level=LOG_LEVEL)

_LOGGER = logging.getLogger(__name__)

player_lock = threading.Lock()
player = None



#HOST = "0.0.0.0"
#PORT = 5000
#TTS_LANG = "de-DE"

favicon_path = 'favicon.ico'  # Adjust path to file


class PlayRequest(BaseModel):
    filename: str            # file path
    volume: int = 100

    @field_validator('volume')
    def validate_volume(cls, v):
        if v > 100 or v < 0:
            raise ValueError('Volume must between 0 and 100')
        return v

class LoopRequest(BaseModel):
    filename: str            # file path
    volume: int = 100

    @field_validator('volume')
    def validate_volume(cls, v):
        if v > 100 or v < 0:
            raise ValueError('Volume must between 0 and 100')
        return v

class BeepRequest(BaseModel):
    number: int = 1 # file path
    volume: int = 100

    @field_validator('volume')
    def validate_volume(cls, v):
        if v > 100 or v < 0:
            raise ValueError('Volume must between 0 and 100')
        return v

    @field_validator('number')
    def validate_number(cls, v):
        if v > 10 or v < 1:
            raise ValueError('Number must between 1 and 10')
        return v

class TtsRequest(BaseModel):
    message: str            # file path
    lang: str = TTS_LANG
    volume: int = 100

    @field_validator('volume')
    def validate_volume(cls, v):
        if v > 100 or v < 0:
            raise ValueError('Volume must between 0 and 100')
        return v

    @field_validator('lang')
    def validate_lang(cls, v):
        if v not in VOICES:
            #raise ValueError("Unknown voice, supported voices:{voices}".format(voices=VOICES))
            raise ValueError(f"Unknown voice, supported voices:{VOICES}")
        return v





@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
):
    # Build a short, human-readable message
    errors = exc.errors()

    if errors:
        first = errors[0]
        loc = first.get("loc", [])
        msg = first.get("msg", "Invalid request")

        # Extract field name (e.g. body -> field)
        field = loc[-1] if len(loc) > 1 else "request"
        #message = f"{msg.capitalize()}: {field}"
        message = f"{msg}: {field}"
    else:
        message = "Invalid request"

    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_request",
            "message": message,
        },
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail.get("error", "unknown_error")
                     if isinstance(exc.detail, dict)
                     else "unknown_error",
            "message": exc.detail.get("message", str(exc.detail))
                     if isinstance(exc.detail, dict)
                     else str(exc.detail),
        },
    )


@app.get('/favicon.ico', include_in_schema=False)
async def favicon():
    return FileResponse(favicon_path)



@app.post("/tts")
def tts_audio(req: TtsRequest):
    global player

    with player_lock:
        if player:
            player.stop()
            player.close()

        try:
            picotts = PicoTTS()
            #picotts.voice = "de-DE"
            #picotts.voice = TTS_LANG
            picotts.voice = req.lang
            wavs = picotts.synth_wav(req.message)

            player = AudioPlayer(
                device=DOORBELL_OUTPUT,
                channels=1
            )
            player.play_bytearray(
                audio_data=wavs,
                volume=req.volume/100
            )

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {"status": "playing", "message": req.message, "lang": req.lang}


@app.post("/beep")
def beep_audio(req: BeepRequest):
    global player

    with player_lock:
        if player:
            player.stop()
            player.close()

        try:
            #beepwav = BeepNoise()
            #wav = beepwav.beep()

            signal, sr = beepnoise2.generate_sine_with_silence(
                frequency=880,
                tone_ms=250,
                silence_ms=250,
                samplerate=16000
                #samplerate=48000
            )

            player = AudioPlayer(
                device=DOORBELL_OUTPUT,
                channels=1
            )
            player.play_numpy(
                audio_data=signal,
                input_samplerate=sr,
                num_loops=req.number,
                volume=req.volume/100
            )

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {"status": "playing", "number": req.number}

@app.post("/play")
def play_audio(req: PlayRequest):
    global player

    with player_lock:
        if player:
            print("stopping existing player")
            player.stop()
            player.close()
        else:
            print("no player to stop, starting new one")


        try:
            path = os.path.join(AUDIO_DIR, req.filename)

            player = AudioPlayer(
                device=DOORBELL_OUTPUT,
                channels=1
            )

            player.play(
                audio_source=path,
                #loop=False,
                volume=req.volume/100,
            )
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    return {"status": "playing", "filename": req.filename}


@app.post("/loop")
def loop_audio(req: LoopRequest):
    global player

    with player_lock:
        if player:
            player.stop()
            player.close()

        try:
            path = os.path.join(AUDIO_DIR, req.filename)
            _LOGGER.debug(f"Looping audio file: {path} with volume: {req.volume}")
            player = AudioPlayer(
                device=DOORBELL_OUTPUT,
                channels=1
            )
            _LOGGER.debug("Starting loop")
            player.loop(
                audio_source=path,
                volume=req.volume/100
            )
            _LOGGER.debug("Loop started")

        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
    #TODO max duration should be configurable
    return {"status": "looping", "filename": req.filename, "max_duration_ms": 60000}



@app.get("/stop")
def stop_audio():
    global player

    with player_lock:
        if not player:
            return {"status": "idle"}

        player.stop()
        player.close()
        player = None

    return {"status": "stopped"}


@app.get("/status")
def status_audio():
    global player

    with player_lock:
        if not player:
            return {"status": "idle"}

    return {"status": "playing"}


@app.get("/info")
def info_audio():
    #TODO: try to get actual hostname, port and ip address
    return {"info": {"name": "doorbell","host": "doorbell", "ip": HOST, "port": PORT}}


if __name__ == "__main__":


    uvicorn.run("doorbell_api:app", host=HOST, port=PORT, reload=True, log_level=LOG_LEVEL.lower())
