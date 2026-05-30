import app


def test_double_quotes_become_single():
    assert app._applescript_safe('say "hi"') == "say 'hi'"


def test_control_characters_stripped():
    # \x00 and \x07 are below space and not tab/newline → removed
    assert app._applescript_safe("a\x00b\x07c") == "abc"


def test_tab_and_newline_preserved():
    assert app._applescript_safe("a\tb\nc") == "a\tb\nc"


def test_plain_text_unchanged():
    assert app._applescript_safe("เพลงไทย 123") == "เพลงไทย 123"
