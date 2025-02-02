from hypothesis import given
from hypothesis import strategies as st

from tests.utils import st_none_or

from .st import st_list_until


@given(data=st.data())
def test_st_iter_until(data: st.DataObject) -> None:
    samples = data.draw(st.lists(st.text(), min_size=1))
    st_ = st.sampled_from(samples)
    last = data.draw(st_)
    max_size = data.draw(st_none_or(st.integers(min_value=0, max_value=10)))

    res = data.draw(st_list_until(st_, last=last, max_size=max_size))

    assert last not in res[:-1]

    if max_size is None:
        assert last == res[-1]
    else:
        assert len(res) == max_size or (last == res[-1] and len(res) < max_size)
