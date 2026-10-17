from fiyatbot.http import looks_blocked


def test_block_detection():
    assert looks_blocked(403, "")
    assert looks_blocked(429, "")
    assert looks_blocked(200, "<title>Just a moment...</title><div id='cf-chl-widget'>")
    assert looks_blocked(200, "<h4>Robot Check</h4> Enter the characters you see below")
    # Akamai Bot Manager ara sayfası (Amazon'da görüldü)
    assert looks_blocked(200, '<meta http-equiv="refresh" content="5; URL=\'/s?k=x&bm-verify=AAQ\'">'
                              'xhr.open("POST", "/_sec/verify?provider=interstitial", false);')
    assert not looks_blocked(200, "<html>normal sayfa</html>")
    # Büyük gerçek sayfada "captcha" kelimesi geçmesi engel sayılmaz
    assert not looks_blocked(200, "x" * 70_000 + "captcha")
