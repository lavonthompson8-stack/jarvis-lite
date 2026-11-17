"""Tools the LLM can call, plus the guard that decides whether a risky call may run.

Why the guard exists: in my own assistant, the model once locked my PC because I said
"lock in" (slang for "focus"). The model guessed; the guess triggered a real action.
So risky tools now run only when the user's actual words ask for them, no matter what
the model decides. The model can suggest; the guard decides.
"""
import ctypes
import datetime
import json
import os
import re
import subprocess
import sys

from . import config

# ---------------------------------------------------------------- tool definitions (sent to the LLM)

SPECS = [
    {"type": "function", "function": {
        "name": "get_time", "description": "Current local date and time.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "read_tasks", "description": "Read the user's to-do list.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "open_app", "description": "Open an app on the PC.",
        "parameters": {"type": "object", "required": ["app"], "properties": {
            "app": {"type": "string", "enum": ["notepad", "calculator", "browser", "explorer"]}}}}},
    {"type": "function", "function": {
        "name": "media", "description": "Control music/video playback and volume.",
        "parameters": {"type": "object", "required": ["action"], "properties": {
            "action": {"type": "string",
                       "enum": ["play_pause", "next", "previous", "volume_up", "volume_down", "mute"]}}}}},
    {"type": "function", "function": {
        "name": "lock_pc", "description": "Lock the computer screen.",
        "parameters": {"type": "object", "properties": {}}}},
]

# ---------------------------------------------------------------- guard

# Risky tool -> a test the user's own words must pass.
_LOCK_WORD = re.compile(r"\block\b")
_DEVICE_WORD = re.compile(r"\b(pc|computer|screen|laptop|workstation|desktop|machine)\b")
_OPEN_WORD = re.compile(r"\b(open|launch|start|run|pull up|bring up|fire up)\b")
_APP_WORD = re.compile(r"\b(notepad|calculator|calc|browser|chrome|edge|google|explorer|files?)\b")
RISKY = {
    "lock_pc": lambda words: bool(_LOCK_WORD.search(words) and _DEVICE_WORD.search(words)),
    # "let's lock in and study" once made the model open Notepad on its own; an app opens only when asked for.
    "open_app": lambda words: bool(_OPEN_WORD.search(words) and _APP_WORD.search(words)),
}


def guard(tool_name, user_text):
    """Return (allowed, reason). Safe tools always pass; risky ones need explicit words."""
    check = RISKY.get(tool_name)
    if check is None:
        return True, "safe tool"
    if check(user_text.lower()):
        return True, "user asked explicitly"
    return False, f"blocked: '{tool_name}' needs an explicit request, and the user said: {user_text!r}"


# ---------------------------------------------------------------- implementations

_APPS = {"notepad": "notepad.exe", "calculator": "calc.exe", "browser": "https://www.google.com", "explorer": "explorer.exe"}
_MEDIA_KEYS = {"play_pause": 0xB3, "next": 0xB0, "previous": 0xB1, "volume_up": 0xAF, "volume_down": 0xAE, "mute": 0xAD}


def _press(vk):
    user32 = ctypes.windll.user32
    user32.keybd_event(vk, 0, 0, 0)
    user32.keybd_event(vk, 0, 2, 0)


def run(tool_name, args):
    """Run one tool and return a short text result for the LLM."""
    if tool_name == "get_time":
        return datetime.datetime.now().strftime("%A, %B %d %Y, %I:%M %p")
    if tool_name == "read_tasks":
        try:
            with open(config.TASKS_FILE, encoding="utf-8") as f:
                tasks = json.load(f)
        except (OSError, ValueError):
            return "No task list found."
        open_tasks = [t["text"] for t in tasks if not t.get("done")]
        return "Open tasks: " + "; ".join(open_tasks) if open_tasks else "No open tasks."
    if config.DRY_RUN or sys.platform != "win32":
        return f"(dry run) would run {tool_name} {json.dumps(args)}"
    if tool_name == "open_app":
        target = _APPS.get(args.get("app", ""))
        if not target:
            return "Unknown app."
        os.startfile(target) if target.startswith("http") else subprocess.Popen([target])
        return f"Opened {args['app']}."
    if tool_name == "media":
        vk = _MEDIA_KEYS.get(args.get("action", ""))
        if vk is None:
            return "Unknown media action."
        _press(vk)
        return f"Done: {args['action']}."
    if tool_name == "lock_pc":
        ctypes.windll.user32.LockWorkStation()
        return "Locked."
    return f"Unknown tool {tool_name}."
