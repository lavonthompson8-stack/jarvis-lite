"""Speech in: record one utterance from the mic, then transcribe it locally with faster-whisper.

The speech detector adapts to the room. A fixed loudness trigger failed on my own mic: my voice
measured 0.004-0.013 while the trigger was 0.015, so it never fired. Now the trigger is 3x the
background noise (kept between 0.0025 and 0.015), learned while nobody is talking.
"""
import queue

import numpy as np

RATE = 16000
BLOCK = 480                 # 30 ms
END_SILENCE_S = 0.8         # this much quiet ends the utterance
MIN_SPEECH_S = 0.3
MIN_T, MAX_T = 0.0025, 0.015
HALLUCINATIONS = {"", "you", "thank you", "thanks for watching", "bye"}


def threshold(noise_floor):
    return min(MAX_T, max(MIN_T, 3.0 * noise_floor))


class Listener:
    def __init__(self, model_name="base.en", device=None):
        from faster_whisper import WhisperModel
        self.model = WhisperModel(model_name, device="cpu", compute_type="int8")
        self.device = device
        self.floor = 0.0

    def listen(self):
        """Block until one utterance is finished; return its audio (float32, 16 kHz) or None if too short."""
        import sounddevice as sd
        q = queue.Queue()
        audio, speaking, quiet, voiced = [], False, 0.0, 0.0
        with sd.InputStream(samplerate=RATE, channels=1, dtype="float32", blocksize=BLOCK,
                            device=self.device, callback=lambda d, *_: q.put(d.copy())):
            while True:
                block = q.get()[:, 0]
                rms = float(np.sqrt(np.mean(block ** 2)))
                if not speaking:
                    self.floor = rms if self.floor == 0.0 else 0.97 * self.floor + 0.03 * rms
                if rms > threshold(self.floor):
                    speaking, quiet = True, 0.0
                    voiced += BLOCK / RATE
                    audio.append(block)
                elif speaking:
                    audio.append(block)
                    quiet += BLOCK / RATE
                    if quiet >= END_SILENCE_S:
                        return np.concatenate(audio) if voiced >= MIN_SPEECH_S else None

    def transcribe(self, audio):
        segments, _ = self.model.transcribe(audio, language="en", beam_size=1,
                                            condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments).strip()
        return "" if text.lower().strip(" .!?") in HALLUCINATIONS else text
