from clip import parse_selection


def test_parse_single():
    assert parse_selection("2", max_id=3) == [2]


def test_parse_multiple():
    assert parse_selection("1,3", max_id=3) == [1, 3]


def test_parse_all():
    assert parse_selection("all", max_id=3) == [1, 2, 3]


def test_parse_out_of_range_ignored():
    assert parse_selection("1,99", max_id=3) == [1]


def test_parse_invalid_token_ignored():
    assert parse_selection("1,abc,2", max_id=5) == [1, 2]
