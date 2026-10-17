from fiyatbot.text import fold, tr_lower


def test_turkish_i():
    assert tr_lower("İSTANBUL") == "istanbul"
    assert tr_lower("ISPARTA") == "ısparta"
    assert fold("KILIF") == fold("kılıf") == fold("Kılıf") == "kilif"
    assert fold("İkinci El") == "ikinci el"


def test_turkish_letters_folded():
    assert fold("Şarj Ğüöç Yenilenmiş") == "sarj guoc yenilenmis"


def test_units_and_spacing():
    assert fold("128 GB") == fold("128GB") == fold("128gb") == fold("128-GB") == "128 gb"
    assert fold("iPhone15") == "iphone 15"


def test_punctuation():
    assert fold("Apple iPhone 15 (128 GB) - Siyah, MTP03TU/A") == "apple iphone 15 128 gb siyah mtp 03 tu a"
    assert fold("") == ""
