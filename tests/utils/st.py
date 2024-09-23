import inspect
import sys
from collections import deque
from collections.abc import Callable
from typing import Generic, Optional, TypeVar

from hypothesis import strategies as st

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

P = ParamSpec('P')
T = TypeVar('T')


def st_none_or(st_: st.SearchStrategy[T]) -> st.SearchStrategy[Optional[T]]:
    '''A strategy for `None` or values from another strategy.

    >>> v = st_none_or(st.integers()).example()
    >>> v is None or isinstance(v, int)
    True
    '''
    return st.one_of(st.none(), st_)


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
