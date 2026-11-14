from jarvis.tts import SentenceSplitter


def test_sentences_come_out_as_soon_as_they_end():
    s = SentenceSplitter()
    assert s.feed("It's 4:12 PM") == []
    assert s.feed(". You have two") == ["It's 4:12 PM."]
    assert s.feed(" tasks left! Want") == ["You have two tasks left!"]
    assert s.flush() == ["Want"]


def test_decimals_and_abbreviations_do_not_split():
    s = SentenceSplitter()
    assert s.feed("Version 1.5 is out, e.g. faster replies. Done ") == ["Version 1.5 is out, e.g. faster replies."]
    assert s.flush() == ["Done"]


def test_flush_empty():
    assert SentenceSplitter().flush() == []
