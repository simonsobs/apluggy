import inspect
from collections import deque
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, TypeVar

P = ParamSpec('P')
T = TypeVar('T')


class RecordReturns(Generic[P, T]):
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
    def __init__(self, record: RecordReturns[P, T]):
        self.returns = deque(record.returns)

    # To conform st.DrawFn
    __signature__ = inspect.Signature(parameters=[])

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> T:
        del args, kwargs
        return self.returns.popleft()


class Probe:
    '''Record where calls are made.'''

    def __init__(self) -> None:
        self.calls = list[str]()

    def __call__(self, *tags: Any) -> None:
        frame = inspect.stack()[1]
        location = f'{frame.filename}:{frame.lineno}'
        fmt_tags = '{' + ','.join(self._fmt_tag(t) for t in tags) + '}'
        record = ':'.join([location, fmt_tags])
        self.calls.append(record)

    def _fmt_tag(self, tag: Any) -> str:
        match tag:
            case Exception():
                return tag.__class__.__name__
            case _:
                return f'{tag}'
