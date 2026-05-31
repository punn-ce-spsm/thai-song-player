import app


def test_double_quotes_are_escaped():
    # Quotes are escaped (not deleted) so they stay inert inside the literal.
    assert app._applescript_safe('say "hi"') == 'say \\"hi\\"'


def test_backslash_is_escaped_before_quotes():
    # A trailing backslash must be doubled so it can't escape the closing quote.
    assert app._applescript_safe("hello\\") == "hello\\\\"
    assert app._applescript_safe('a\\"b') == 'a\\\\\\"b'


def test_control_characters_stripped():
    # \x00 and \x07 are below space → removed
    assert app._applescript_safe("a\x00b\x07c") == "abc"


def test_tab_and_newline_now_stripped():
    # Newlines/tabs are control chars and are removed (no longer allowed),
    # preventing multi-line AppleScript injection.
    assert app._applescript_safe("a\tb\nc") == "abc"


def test_plain_text_unchanged():
    assert app._applescript_safe("เพลงไทย 123") == "เพลงไทย 123"
