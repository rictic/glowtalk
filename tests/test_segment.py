from glowtalk.segment import segment

def test_segment_basic():
    text = "This is a sentence. This is another sentence!"
    result = segment(text)
    assert result == ["This is a sentence.", "This is another sentence!"]

def test_segment_empty():
    assert segment("") == []

def test_segment_single():
    text = "Just one sentence."
    result = segment(text)
    assert result == ["Just one sentence."]

def test_segment_complex():
    text = "Hello, Mr. Smith! How are you? I'm doing well... Thanks for asking."
    result = segment(text)
    assert result == [
      "Hello, Mr. Smith!",
      "How are you?",
      "I'm doing well...",
      "Thanks for asking."
    ]

def test_tricky():
  text = """The dove, whose name she remembers perfectly well, perched on the desk to her right. An angel, formerly wielding a note pad and pen but now looking attentively at the judge. A great wheel of gears and eyes, gleaming with fire or gemstones depending on the light. Each advocate has a human-size desk, regardless of whether using it means "perched on" or "leaning at." And, studiously ignoring everyone else, a devil."""
  result = segment(text)
  assert result == [
    "The dove, whose name she remembers perfectly well, perched on the desk to her right.",
    "An angel, formerly wielding a note pad and pen but now looking attentively at the judge.",
    "A great wheel of gears and eyes, gleaming with fire or gemstones depending on the light.",
    "Each advocate has a human-size desk, regardless of whether using it means \"perched on\" or \"leaning at.\"",
    "And, studiously ignoring everyone else, a devil."
  ]
