"""Speech out: split the streamed reply into sentences and speak each one as soon as it is complete.

Two threads: one turns sentences into audio (edge-tts) while the other plays the previous
sentence, so there is no gap between sentences and the first one starts right away.
"""
import asyncio
import io
import queue
import re
import threading

_END = re.compile(r"[.!?](?=\s)")
_ABBREV = ("e.g.", "i.e.", "mr.", "mrs.", "dr.", "vs.", "etc.", "a.m.", "p.m.")


class SentenceSplitter:
    """feed() streamed text pieces, get back finished sentences; flush() returns the rest."""

    def __init__(self):
        self.buf = ""

    def feed(self, piece):
        self.buf += piece
        out = []
        start = 0
        for m in _END.finditer(self.buf):
            candidate = self.buf[start:m.end()].strip()
            if candidate.lower().endswith(_ABBREV):
                continue
            if candidate:
                out.append(candidate)
            start = m.end()
        self.buf = self.buf[start:]
        return out

    def flush(self):
        rest, self.buf = self.buf.strip(), ""
        return [rest] if rest else []


class Speaker:
    def __init__(self, voice):
        import pygame
        self.voice = voice
        self.pg = pygame
        pygame.mixer.init()
        self.text_q = queue.Queue()
        self.audio_q = queue.Queue()
        threading.Thread(target=self._synth_loop, daemon=True).start()
        threading.Thread(target=self._play_loop, daemon=True).start()

    def say(self, sentence):
        self.text_q.put(sentence)

    def wait(self):
        self.text_q.join()
        self.audio_q.join()

    def _synth_loop(self):
        import edge_tts

        async def synth(text):
            data = b""
            async for chunk in edge_tts.Communicate(text, self.voice).stream():
                if chunk["type"] == "audio":
                    data += chunk["data"]
            return data

        loop = asyncio.new_event_loop()
        while True:
            text = self.text_q.get()
            try:
                self.audio_q.put(loop.run_until_complete(synth(text)))
            except Exception as e:               # no network etc.: print instead of speaking
                print(f"  [tts] {type(e).__name__}: {text}")
            finally:
                self.text_q.task_done()

    def _play_loop(self):
        music = self.pg.mixer.music
        while True:
            audio = self.audio_q.get()
            try:
                music.load(io.BytesIO(audio), "mp3")
                music.play()
                while music.get_busy():
                    self.pg.time.wait(20)
            finally:
                self.audio_q.task_done()
