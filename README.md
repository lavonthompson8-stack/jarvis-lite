# Jarvis Lite

A voice assistant that listens, thinks with an LLM, takes real actions on your PC through tool calls, and talks back, with a guard layer so the model can't run risky actions on a guess.

It's a standalone, open-source version of the voice assistant I built for myself and use every day.

## How it works

```
mic -> speech detector (adapts to room noise) -> faster-whisper (local speech-to-text)
                                                       |
                                                       v
                 LLM with tool calling (any OpenAI-compatible API, streamed)
                 provider 1 --(rate limit / server error / timeout)--> provider 2
                                                       |
                  tool call? -> guard -> run tool -> result goes back to the LLM
                                                       |
                                                       v
      sentence splitter -> edge-tts -> speaker (the next sentence is synthesized while this one plays)
```

## Features

- **Local speech-to-text** with faster-whisper. Transcription runs on your machine.
- **Adaptive speech detection.** The trigger level is 3x the background noise, learned while nobody is talking (kept between 0.0025 and 0.015 RMS). A fixed trigger failed on my own mic: my voice measured 0.004-0.013 and the trigger was 0.015, so it never fired.
- **Tool calling:** current time, to-do list, open apps, media keys, lock the screen.
- **Provider fallback.** If a provider rate-limits, errors or times out, the next one answers. It never switches models halfway through a spoken answer.
- **Guardrails for risky tools** (below).
- **Streaming voice.** Speech starts as soon as the first sentence is complete, not when the whole reply is done.

## The guardrail, and why it exists

My own assistant once locked my computer because I said "lock in" (slang for "let's focus"). The model guessed I meant the lock tool, and that guess triggered a real action. In AI security terms that's *excessive agency*: the model had the power to act without enough checks.

The fix is a second check that doesn't trust the model. Every risky tool has a rule that looks at what the user actually said ("lock" plus a device word like "pc" or "screen"). The model can ask for the tool; the guard decides whether it runs. If it's blocked, the model gets told why and answers normally. `tests/test_guard.py` covers both sides, including the case where the model does call the tool on slang.

## Demo

A real run in safe mode (`JARVIS_DRY_RUN=1`, tools describe what they'd do instead of doing it):

```
you: what time is it?
  [tool] get_time({}) -> ran: Saturday, November 14 2026, 12:22 PM
  jarvis: It's 12:22 PM on Saturday, November 14, 2026.

you: ok jarvis let's lock in and study
  jarvis: Got it, I'll stay quiet while you focus on studying.
  jarvis: Let me know if you need anything.

you: jarvis lock my pc
  [tool] lock_pc({}) -> ran: (dry run) would run lock_pc {}
  jarvis: Your PC is now locked.

you: what's on my to-do list?
  [tool] read_tasks({}) -> ran: Open tasks: Finish the history worksheet; Post today's video
  [llm] groq-gpt-oss-120b: HTTP 429 (rate limit) -> trying the next provider
  [llm] groq-gpt-oss-20b answered in 0.70s
  jarvis: You have two tasks: finish the history worksheet and post today's video.
```

The last one shows the fallback live: the first model hit its rate limit and the backup answered.

## Setup

```
git clone <this repo>
cd jarvis-lite
pip install -r requirements.txt
set GROQ_API_KEY=your-key        (free key at console.groq.com; on macOS/Linux: export GROQ_API_KEY=...)
python -m jarvis --text --dry-run   type instead of talking, tools in safe mode
python -m jarvis                    talk to it
```

Options: `--text` (type), `--no-voice` (print replies), `--wake` (only answer when you say "Jarvis"), `--dry-run` (safe tools).

Settings come from environment variables (see `.env.example`). `JARVIS_PROVIDERS` takes a JSON list of any OpenAI-compatible endpoints, so it also runs against OpenAI or a local model server.

## Tests

```
python -m pytest
```

18 tests: the guard (slang vs. explicit requests, and a model that calls the lock tool anyway), sentence splitting on streamed text, provider fallback, tool calls arriving in pieces over the stream, no model switch after speech has started, and short conversation history.

## Layout

```
jarvis/
  stt.py      mic capture + adaptive speech detection + faster-whisper
  llm.py      streamed chat, tool-call assembly, provider fallback, tool loop
  tools.py    tool definitions, implementations, and the guard
  tts.py      sentence splitter + edge-tts synthesis + playback
  config.py   providers, voice, model, system prompt
  __main__.py the listen -> think -> speak loop
tests/        pytest suite
examples/     sample to-do list
```

PC actions (open apps, media keys, lock) are Windows-only; on other systems those tools run in dry-run mode.

I designed and tested this and built it with AI coding assistants.

## License

MIT
