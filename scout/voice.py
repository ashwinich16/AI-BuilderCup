"""Voice I/O with a text fallback.

Tries to use a real microphone (SpeechRecognition) and speaker (pyttsx3) for
a true voice-first experience. If either isn't available -- no mic/speakers,
missing optional dependency, or a headless/sandboxed environment -- falls
back to the terminal so the same conversational pipeline still runs, and
main.py announces the fallback out loud so the user knows why.

pyttsx3's SAPI5 driver on Windows has a well-known quirk: reusing one engine
instance across repeated say()/runAndWait() calls often produces audio only
for the first call and silently no-ops afterwards. To avoid that, a fresh
engine is created for every utterance.
"""

from __future__ import annotations

import os

_recognizer = None
_microphone = None
_voice_input_ready: bool | None = None
_voice_output_ready: bool | None = None


def _text_only() -> bool:
    return os.environ.get("SCOUT_TEXT_ONLY", "").lower() in ("1", "true", "yes")


def output_ready() -> bool:
    if _text_only():
        return False
    if _voice_output_ready is None:
        _probe_output()
    return bool(_voice_output_ready)


def input_ready() -> bool:
    if _text_only():
        return False
    if _voice_input_ready is None:
        _probe_input()
    return bool(_voice_input_ready)


def _probe_output() -> None:
    global _voice_output_ready
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.stop()
        _voice_output_ready = True
    except Exception as exc:
        _voice_output_ready = False
        print(f"(text-to-speech unavailable: {exc})")


def _probe_input() -> None:
    global _recognizer, _microphone, _voice_input_ready
    try:
        import speech_recognition as sr

        _recognizer = sr.Recognizer()
        _microphone = sr.Microphone()
        _voice_input_ready = True
    except Exception as exc:
        _voice_input_ready = False
        print(f"(microphone unavailable: {exc})")


def speak(text: str) -> None:
    """Say `text` aloud if TTS is available; always also print it, since a
    blind/low-vision user's screen reader or terminal is the reliable channel
    during development and the printed line doubles as a transcript.
    """
    print(f"\nScout: {text}")
    if not output_ready():
        return
    try:
        import pyttsx3

        engine = pyttsx3.init()
        engine.say(text)
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        print(f"(speech playback failed: {exc})")


_MAX_LISTEN_ATTEMPTS = 3


def listen(prompt: str) -> str:
    """Ask `prompt` and return the user's spoken reply.

    Since the audience is blind or low-vision, typing is a last resort, not
    a first response to a single misheard phrase: a missed or garbled
    attempt gets retried by voice (with a short spoken nudge) before ever
    dropping to the keyboard.
    """
    speak(prompt)
    if not input_ready():
        return input("You (type): ").strip()

    import speech_recognition as sr

    for attempt in range(1, _MAX_LISTEN_ATTEMPTS + 1):
        try:
            with _microphone as source:
                _recognizer.adjust_for_ambient_noise(source, duration=0.5)
                print("(listening...)")
                audio = _recognizer.listen(source, timeout=8, phrase_time_limit=15)
            text = _recognizer.recognize_google(audio)
            print(f"You (heard): {text}")
            return text
        except sr.WaitTimeoutError:
            reason = "I didn't hear anything"
        except sr.UnknownValueError:
            reason = "I didn't quite catch that"
        except sr.RequestError as exc:
            print(f"(speech recognition service error: {exc})")
            break

        if attempt < _MAX_LISTEN_ATTEMPTS:
            speak(f"{reason}, could you say that again?")
        else:
            speak(f"{reason} a few times in a row. Go ahead and type it instead, just this once.")

    return input("You (type): ").strip()
