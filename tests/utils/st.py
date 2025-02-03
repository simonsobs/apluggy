import inspect
import sys
from collections import deque
from collections.abc import Callable
from itertools import count
from typing import Generic, Optional, TypeVar, Union

from hypothesis import strategies as st

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

from .iteration import take_until

P = ParamSpec('P')
T = TypeVar('T')


def st_none_or(st_: st.SearchStrategy[T]) -> st.SearchStrategy[Optional[T]]:
    '''A strategy for `None` or values from another strategy.

    >>> v = st_none_or(st.integers()).example()
    >>> v is None or isinstance(v, int)
    True
    '''
    return st.one_of(st.none(), st_)


@st.composite
def st_list_until(
    draw: st.DrawFn,
    st_: st.SearchStrategy[T],
    /,
    *,
    last: Union[T, set[T]],
    max_size: Optional[int] = None,
) -> list[T]:
    '''A strategy for lists from `st_` that ends with `last` or an item in `last`.'''
    counts = range(max_size) if max_size is not None else count()
    gen = (draw(st_) for _ in counts)

    def _cond(x: T) -> bool:
        if x == last:
            return True
        if isinstance(last, set):
            return x in last
        return False

    return list(take_until(_cond, gen))


class RecordReturns(Generic[P, T]):
    '''Store the return values of a function so that they can be repeated by ReplayReturns.

    This class is primarily used to wrap the draw function from Hypothesis.
    '''

    def __init__(self, f: Callable[P, T]):
        self.f = f
        self.returns = list[T]()

    # To conform st.DrawFn
    __signature__ = inspect.Signature(parameters=[])

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        ret = self.f(*args, **kwargs)
        self.returns.append(ret)
        return ret


class ReplayReturns(Generic[P, T]):
    '''Repeat the return values of a function that were recorded by RecordReturns.'''

    def __init__(self, record: RecordReturns[P, T]):
        self.returns = deque(record.returns)

    # To conform st.DrawFn
    __signature__ = inspect.Signature(parameters=[])

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        del args, kwargs
        return self.returns.popleft()
