import inspect
import sys
from typing import Any, TypeVar

if sys.version_info >= (3, 10):
    from typing import ParamSpec
else:
    from typing_extensions import ParamSpec

P = ParamSpec('P')
T = TypeVar('T')


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
