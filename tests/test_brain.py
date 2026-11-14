"""The brain with a fake transport: fallback, streamed tool calls, and the guard inside the loop."""
import json

from jarvis.llm import Brain, ProviderError

P1 = {"name": "primary", "model": "m1"}
P2 = {"name": "backup", "model": "m2"}


def sse(*deltas):
    return [json.dumps({"choices": [{"delta": d}]}) for d in deltas] + ["[DONE]"]


def text_reply(text):
    return sse(*({"content": c} for c in [text[: len(text) // 2], text[len(text) // 2:]]))


def tool_reply(name, call_id="call_1", args="{}"):
    # tool calls stream in pieces: id+name first, then the arguments
    return sse({"tool_calls": [{"index": 0, "id": call_id, "type": "function", "function": {"name": name, "arguments": ""}}]},
               {"tool_calls": [{"index": 0, "function": {"arguments": args}}]})


class Script:
    """Plays back canned responses per provider; records what each request contained."""

    def __init__(self, plan):
        self.plan = plan
        self.requests = []

    def __call__(self, provider, payload):
        self.requests.append((provider["name"], payload))
        step = self.plan[provider["name"]].pop(0)
        if isinstance(step, Exception):
            raise step
        return iter(step)


def make(plan):
    script = Script(plan)
    logs = []
    return Brain(providers=[P1, P2], transport=script, log=logs.append), script, logs


def test_falls_back_when_primary_is_rate_limited():
    brain, script, logs = make({"primary": [ProviderError("primary: HTTP 429")], "backup": [text_reply("Hi there.")]})
    pieces = []
    assert brain.ask("hello", on_text=pieces.append) == "Hi there."
    assert [name for name, _ in script.requests] == ["primary", "backup"]
    assert "".join(pieces) == "Hi there."
    assert any("trying the next provider" in line for line in logs)


def test_streamed_tool_call_runs_then_answers():
    brain, script, logs = make({"primary": [tool_reply("get_time"), text_reply("It's late.")], "backup": []})
    assert brain.ask("what time is it") == "It's late."
    second = script.requests[1][1]["messages"]
    assert second[-2]["tool_calls"][0]["function"]["name"] == "get_time"
    assert second[-1]["role"] == "tool" and second[-1]["tool_call_id"] == "call_1"


def test_guard_blocks_lock_on_slang_even_if_model_calls_it(monkeypatch):
    ran = []
    monkeypatch.setattr("jarvis.tools.run", lambda name, args: ran.append(name) or "done")
    brain, script, logs = make({"primary": [tool_reply("lock_pc"), text_reply("Let's focus.")], "backup": []})
    brain.ask("ok let's lock in")
    assert ran == []                                          # the model asked; the guard said no
    tool_msg = script.requests[1][1]["messages"][-1]
    assert tool_msg["role"] == "tool" and "blocked" in tool_msg["content"]


def test_no_restart_on_another_model_after_speaking():
    def half_then_fail():
        yield json.dumps({"choices": [{"delta": {"content": "Sure, "}}]})
        raise ProviderError("primary: connection reset")

    brain, script, logs = make({"primary": [half_then_fail()], "backup": [text_reply("never used")]})
    assert brain.ask("hey") == "Sure, "
    assert [name for name, _ in script.requests] == ["primary"]


def test_history_is_kept_short():
    replies = [text_reply(f"answer {i}.") for i in range(10)]
    brain, script, logs = make({"primary": replies, "backup": []})
    for i in range(10):
        brain.ask(f"question {i}")
    assert len(brain.history) == 12
