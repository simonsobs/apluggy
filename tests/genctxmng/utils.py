import inspect
from collections import deque
from collections.abc import Callable
from typing import Any, Generic, ParamSpec, TypeVar

P = ParamSpec('P')
T = TypeVar('T')


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


class Probe:
    '''Record where calls are made.

    This class is used to assert that expected lines of code are executed in a test.

    >>> def f(probe: Probe):
    ...     probe()
    ...     probe('tag')
    ...
    ...     try:
    ...         raise Exception('msg')
    ...     except Exception as e:
    ...         probe(e)
    ...
    ...     try:
    ...         raise KeyboardInterrupt()
    ...     except BaseException as e:
    ...         probe(e)


    >>> probe1 = Probe()
    >>> probe2 = Probe()
    >>> f(probe1)
    >>> f(probe2)
    >>> probe1.calls == probe2.calls
    True

    '''

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
                return repr(tag)
            case BaseException():
                return tag.__class__.__name__
            case _:
                return f'{tag}'
