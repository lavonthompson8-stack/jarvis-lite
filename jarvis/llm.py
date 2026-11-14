"""The brain: an LLM with tool calling, streamed, with automatic fallback between providers.

Works with any OpenAI-compatible chat API. Each round streams the reply; text goes straight
to `on_text` (so speech can start on the first sentence), tool calls are assembled from the
stream, checked by the guard, run, and fed back for the next round.
"""
import json
import os
import time

import requests

from . import config, tools

RETRYABLE = {408, 409, 429, 500, 502, 503, 504}
MAX_ROUNDS = 4          # tool round-trips per question
HISTORY_TURNS = 6       # earlier question/answer pairs kept for context


class ProviderError(Exception):
    """This provider can't answer right now; try the next one."""


def http_stream(provider, payload, timeout=(5, 30)):
    """POST a streaming chat request; yield the raw SSE data strings."""
    key = os.environ.get(provider.get("key_env", ""), "")
    try:
        r = requests.post(f"{provider['base_url']}/chat/completions", json=payload, stream=True, timeout=timeout,
                          headers={"Authorization": f"Bearer {key}"})
    except requests.RequestException as e:
        raise ProviderError(f"{provider['name']}: {type(e).__name__}") from e
    with r:
        if r.status_code != 200:
            raise ProviderError(f"{provider['name']}: HTTP {r.status_code} {r.text[:120]}")
        for line in r.iter_lines():
            if line.startswith(b"data: "):
                yield line[6:].decode("utf-8", "replace")


class Brain:
    def __init__(self, providers=None, transport=http_stream, log=print):
        self.providers = providers or config.providers()
        self.transport = transport
        self.log = log
        self.history = []

    # ------------------------------------------------------------ public

    def ask(self, user_text, on_text=None):
        """Answer one utterance. Returns the final spoken text."""
        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}, *self.history,
                    {"role": "user", "content": user_text}]
        text = ""
        for _ in range(MAX_ROUNDS):
            text, calls = self._round(messages, on_text)
            if not calls:
                break
            messages.append({"role": "assistant", "content": text or None, "tool_calls": calls})
            for call in calls:
                name = call["function"]["name"]
                try:
                    args = json.loads(call["function"].get("arguments") or "{}")
                except ValueError:
                    args = {}
                allowed, why = tools.guard(name, user_text)
                result = tools.run(name, args) if allowed else why
                self.log(f"  [tool] {name}({args}) -> {'ran' if allowed else 'BLOCKED'}: {result}")
                messages.append({"role": "tool", "tool_call_id": call["id"], "content": result})
        self.history = (self.history + [{"role": "user", "content": user_text},
                                        {"role": "assistant", "content": text}])[-2 * HISTORY_TURNS:]
        return text

    # ------------------------------------------------------------ internals

    def _round(self, messages, on_text):
        """One streamed completion. Falls back to the next provider only if nothing was said yet."""
        errors = []
        for provider in self.providers:
            payload = {"model": provider["model"], "messages": messages, "tools": tools.SPECS,
                       "stream": True, "temperature": 0.3, **provider.get("extra", {})}
            said = []
            try:
                t0 = time.time()
                text, calls = self._consume(self.transport(provider, payload), on_text, said)
                self.log(f"  [llm] {provider['name']} answered in {time.time() - t0:.2f}s")
                return text, calls
            except ProviderError as e:
                if said:            # already spoke part of an answer: don't start over on another model
                    self.log(f"  [llm] {provider['name']} broke mid-answer: {e}")
                    return "".join(said), []
                errors.append(str(e))
                self.log(f"  [llm] {e} -> trying the next provider")
        raise RuntimeError("all providers failed: " + " | ".join(errors))

    @staticmethod
    def _consume(events, on_text, said):
        """Turn SSE chunks into (text, tool_calls). Tool calls arrive in pieces; join them by index."""
        calls = {}
        for data in events:
            if data == "[DONE]":
                break
            choice = (json.loads(data).get("choices") or [{}])[0]
            delta = choice.get("delta") or {}
            piece = delta.get("content")
            if piece:
                said.append(piece)
                if on_text:
                    on_text(piece)
            for tc in delta.get("tool_calls") or []:
                slot = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function",
                                                             "function": {"name": "", "arguments": ""}})
                slot["id"] = tc.get("id") or slot["id"]
                fn = tc.get("function") or {}
                slot["function"]["name"] += fn.get("name") or ""
                slot["function"]["arguments"] += fn.get("arguments") or ""
        return "".join(said), [calls[i] for i in sorted(calls)]
