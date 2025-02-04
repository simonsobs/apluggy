from collections.abc import Callable
from itertools import count
from typing import NewType

CtxId = NewType('CtxId', int)


def ContextIdGenerator() -> Callable[[], CtxId]:
    '''Return a function that returns a new `_CtxId` each time it is called.

    >>> gen = _ContextIdGenerator()
    >>> id1 = gen()
    >>> id2 = gen()
    >>> id1 is id2
    False
    '''
    _count = count(1).__next__

    def _gen() -> CtxId:
        return CtxId(_count())

    return _gen
