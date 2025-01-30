from hypothesis import given

from .iteration import take_until


@given(...)
def test_take_until(items: list[int], last: int) -> None:
    actual = list(take_until(lambda x: x == last, iter(items)))
    expected = items[: items.index(last) + 1] if last in items else items
    assert actual == expected
