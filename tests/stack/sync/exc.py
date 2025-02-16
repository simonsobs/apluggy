import asyncio
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
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


def _gen_send_without_yield() -> Exception:
    @contextmanager
    def ctx() -> Iterator[None]:
        yield

    exc: Exception
    try:
        with (c := ctx()):
            c.gen.send(None)
    except Exception as e:
        exc = e
    return exc


async def _async_gen_asend_without_yield() -> Exception:
    @asynccontextmanager
    async def ctx() -> AsyncIterator[None]:
        yield

    exc: Exception
    try:
        async with (c := ctx()):
            await c.gen.asend(None)
    except Exception as e:
        exc = e
    return exc


async def _async_gen_raise_on_asend() -> Exception:
    raised = Exception()

    @asynccontextmanager
    async def ctx() -> AsyncIterator[None]:
        yield
        raise raised

    exc: Exception
    try:
        async with (c := ctx()):
            try:
                await c.gen.asend(None)
            except Exception as e:
                assert e is raised  # Still the same exception
                raise
    except Exception as e:
        assert e is not raised  # No longer the same exception
        exc = e
    return exc


GenSendWithoutYield = _gen_send_without_yield()
AsyncGenAsendWithoutYield = asyncio.run(_async_gen_asend_without_yield())
AsyncGenRaiseOnASend = asyncio.run(_async_gen_raise_on_asend())
