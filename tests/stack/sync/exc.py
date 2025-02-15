from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import ClassVar, Literal, Union


class MockException(Exception):
    pass


@dataclass
class ExceptionExpectation:
    '''A comparison of exceptions in a specified way.

    Examples
    --------

    1. Compare if the exception is the same object.

    >>> exc1 = ValueError('1')
    >>> exp = ExceptionExpectation(exc1, method='is')

    >>> exp == exc1
    True

    >>> exp == ValueError('1')
    False

    Comparisons can be made in the other order as well.

    >>> exc1 == exp
    True

    >>> ValueError('1') == exp
    False


    2. Compare if the class and message are as expected.

    >>> exp = ExceptionExpectation(exc1, method='type-msg')

    >>> exp == exc1
    True

    >>> exp == ValueError('1')
    True

    >>> exp == ValueError('2')
    False

    A class can be a subclass of the expected class.

    >>> class MyValueError(ValueError):
    ...     pass

    >>> exp == MyValueError('1')
    True


    3. Compare if the class is as expected.

    >>> exp = ExceptionExpectation(exc1, method='type')

    >>> exp == ValueError('2')
    True

    >>> exp == MyValueError('2')
    True

    >>> exp == TypeError('2')
    False
    '''

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


def wrap_exc(exc: Union[Exception, None]) -> ExceptionExpectation:
    method: ExceptionExpectation.Method
    method = 'is' if isinstance(exc, MockException) else 'type-msg'
    return ExceptionExpectation(exc, method=method)


def _generator_did_not_yield() -> RuntimeError:
    '''Return the exception raised on entering a context manager.

    It returns `RuntimeError("generator didn't yield")` on Python 3.10.
    '''

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
