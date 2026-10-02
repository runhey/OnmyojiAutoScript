"""
Tests for the script.misc.op package surface.
"""
import script.misc.op as op


EXPECTED = {
    'Area',
    'Point',
    'RGB',
    'Slist',
    'random_friendly_id',
    'random_id',
    'random_normal_distribution_int',
    'random_rectangle_point',
}


def test_all_matches_the_exported_names():
    assert set(op.__all__) == EXPECTED


def test_every_name_is_importable_from_the_package():
    for name in EXPECTED:
        assert hasattr(op, name), name


def test_slist_is_exported():
    # OAS has no caller yet, but the module stays for Alasio parity
    assert op.Slist([1, 2, 3]).count == 3
