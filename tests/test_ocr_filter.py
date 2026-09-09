from types import SimpleNamespace

from module.ocr.base_ocr import BaseCor


def boxed_text(text: str):
    return SimpleNamespace(ocr_text=text)


def test_exact_filter_does_not_match_a_partial_nickname():
    target = object.__new__(BaseCor)
    results = [boxed_text('赈早见琥珀主'), boxed_text('龙鸣蚀心')]

    assert target.filter(results, '你的心', exact=True) is None


def test_exact_filter_matches_the_complete_nickname():
    target = object.__new__(BaseCor)
    results = [boxed_text('轻芋'), boxed_text('你的心')]

    assert target.filter(results, '你的心', exact=True) == [1]
