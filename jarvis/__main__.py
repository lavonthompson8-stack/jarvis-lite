"""python -m jarvis            talk to it (mic in, voice out)
   python -m jarvis --text     type instead of talking
   python -m jarvis --no-voice print replies instead of speaking
   python -m jarvis --wake     only answer when the sentence contains "Jarvis"
   python -m jarvis --dry-run  tools say what they would do instead of doing it"""
import argparse
import re

from . import config
from .llm import Brain
from .tts import SentenceSplitter

WAKE = re.compile(r"\bjar[\w']{2,5}\b", re.I)   # Whisper hears "Jarvis" as jarvis/jarvas/jervis...


def main():
    ap = argparse.ArgumentParser(prog="jarvis")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--no-voice", action="store_true")
    ap.add_argument("--wake", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if a.dry_run:
        config.DRY_RUN = True

    brain = Brain()
    speaker = None
    if not a.no_voice:
        from .tts import Speaker
        speaker = Speaker(config.VOICE)
    listener = None
    if not a.text:
        from .stt import Listener
        print("loading speech model...")
        listener = Listener(config.WHISPER_MODEL)

    print("Jarvis is listening. Ctrl+C to quit.")
    while True:
        try:
            if listener:
                audio = listener.listen()
                said = listener.transcribe(audio) if audio is not None else ""
                if not said:
                    continue
                print(f"you: {said}")
            else:
                said = input("you: ").strip()
                if not said:
                    continue
        except (KeyboardInterrupt, EOFError):
            print("\nbye")
            return

        if a.wake:
            if not WAKE.search(said):
                continue
            said = WAKE.sub("", said, count=1).strip(" ,.") or "yes?"

        splitter = SentenceSplitter()

        def out(sentence):
            if speaker:
                speaker.say(sentence)
            print(f"jarvis: {sentence}")

        def on_text(piece):
            for sentence in splitter.feed(piece):
                out(sentence)

        try:
            brain.ask(said, on_text=on_text)
        except RuntimeError as e:
            print(f"  [error] {e}")
            continue
        for sentence in splitter.flush():
            out(sentence)
        if speaker:
            speaker.wait()


if __name__ == "__main__":
    main()
