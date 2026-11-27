from app.backend.services.reply_polish import ReplyPolisher


def test_strips_emoji_when_not_requested():
    assert ReplyPolisher(max_emoji=0).feed("좋다 🌊 진짜") == "좋다 진짜"


def test_keeps_only_first_emoji_across_chunks():
    p = ReplyPolisher(max_emoji=1)
    assert p.feed("와 🌊") == "와 🌊"
    assert p.feed(" 대박 🐋☘️") == " 대박 "


def test_comma_cleanup_including_chunk_boundary():
    p = ReplyPolisher()
    assert p.feed("응 ,, 그래") == "응, 그래"
    assert p.feed("근데,") == "근데,"
    assert p.feed(", 있잖아") == " 있잖아"


def test_plain_text_untouched():
    assert ReplyPolisher().feed("그랬구나. 언제부터 그랬어?") == "그랬구나. 언제부터 그랬어?"
