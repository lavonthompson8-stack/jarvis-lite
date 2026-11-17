import pytest

from jarvis import tools


@pytest.mark.parametrize("said", [
    "lock in",
    "ok jarvis let's lock in and study",
    "I need to lock in for this test",
    "block that website",
])
def test_slang_never_locks_the_pc(said):
    allowed, why = tools.guard("lock_pc", said)
    assert not allowed
    assert "blocked" in why


@pytest.mark.parametrize("said", [
    "lock my pc",
    "Jarvis, lock the screen",
    "can you lock my computer please",
])
def test_explicit_request_locks(said):
    assert tools.guard("lock_pc", said) == (True, "user asked explicitly")


@pytest.mark.parametrize("said", [
    "ok jarvis let's lock in and study",
    "I need to take notes later",
])
def test_apps_never_open_on_a_guess(said):
    assert not tools.guard("open_app", said)[0]


@pytest.mark.parametrize("said", [
    "open notepad",
    "jarvis, can you launch the calculator",
])
def test_explicit_request_opens_app(said):
    assert tools.guard("open_app", said) == (True, "user asked explicitly")


def test_safe_tools_always_pass():
    assert tools.guard("get_time", "anything")[0]
    assert tools.guard("media", "lock in")[0]


def test_dry_run_does_not_act(monkeypatch):
    monkeypatch.setattr(tools.config, "DRY_RUN", True)
    assert tools.run("lock_pc", {}).startswith("(dry run)")


def test_read_tasks_lists_only_open_ones():
    out = tools.run("read_tasks", {})
    assert "history worksheet" in out and "bench day" not in out
