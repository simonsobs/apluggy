from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar, Literal, Union


class Thrown(Exception):
    '''To be thrown to the context manager.

    An argument of `contextmanager.gen.throw()`.
    '''

    pass


class Raised(Exception):
    pass


class MockException(Exception):
    pass


@dataclass
class ExceptionExpectation:
    Method = Literal['is', 'type-msg', 'type']
    METHODS: ClassVar[tuple[Method, ...]] = ('is', 'type-msg', 'type')

    expected: Union[BaseException, None]
    method: Method = 'is'

    def __eq__(self, other: object) -> bool:
        if self.method == 'is':
            return self.expected is other
        if self.method == 'type-msg':
            if not isinstance(other, type(self.expected)):
                return False
            return str(other) == str(self.expected)
        if self.method == 'type':
            return isinstance(other, type(self.expected))
        raise ValueError(self.method)  # pragma: no cover

def _generator_did_not_yield() -> RuntimeError:
    '''Return the exception raised on entering a context manager.'''

    @contextmanager
    def ctx() -> Iterator[None]:
        if False:  # pragma: no cover
            yield

    exc: RuntimeError
    try:
        with ctx():  # pragma: no cover
            assert False
    except RuntimeError as e:
        exc = e
    assert isinstance(exc, RuntimeError)
    return exc


GeneratorDidNotYield = _generator_did_not_yield()
