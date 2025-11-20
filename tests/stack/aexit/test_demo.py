import contextlib
import sys

import pytest


async def test_demo_aexit_problem() -> None:
    '''Show an async context manager doesn't raise the same exception at the exit.

    In contrast, a context manager does raise the same exception at the exit.
    '''

    #
    # A context manager re-rases at the exit
    #

    exc = Exception('exc')

    @contextlib.contextmanager
    def ctx():
        '''Raise the exception after the first `yield`.'''
        s = yield 'foo'
        assert s == 'sent'
        raise exc

    with pytest.raises(Exception) as excinfo:
        with (c := ctx()) as x:
            assert x == 'foo'
            try:
                c.gen.send('sent')
            except Exception as e:
                assert e is exc
                raise  # Let the exit handle the exception

    assert excinfo.value is exc  # The exit re-raised the same exception

    #
    # An async context manager raises a different exception at the exit
    #

    @contextlib.asynccontextmanager
    async def actx():
        '''Raise the exception after the first `yield`.'''
        s = yield 'foo'
        assert s == 'sent'
        raise exc

    with pytest.raises(Exception) as excinfo:
        async with (ac := actx()) as x:
            assert x == 'foo'
            try:
                await ac.gen.asend('sent')
            except Exception as e:
                assert e is exc
                raise  # Let the exit handle the exception

    assert excinfo.value is not exc  # The exit raised a different exception

    # It raised `RuntimeError("generator didn't stop after athrow()")`
    assert isinstance(excinfo.value, RuntimeError)
    assert str(excinfo.value) == "generator didn't stop after athrow()"

    # An equivalent code with manual `__aenter__` and `__aexit__` calls
    with pytest.raises(Exception) as excinfo:
        ac = actx()
        x = await ac.__aenter__()
        assert x == 'foo'
        try:
            try:
                await ac.gen.asend('sent')
            except Exception as e:
                assert e is exc
                raise
        except Exception:
            if not await ac.__aexit__(*sys.exc_info()):
                raise
        else:
            await ac.__aexit__(None, None, None)

    assert excinfo.value is not exc
    assert isinstance(excinfo.value, RuntimeError)
    assert str(excinfo.value) == "generator didn't stop after athrow()"

    # The __aexit__ doesn't re-raise an exception occurred at `asend()` because
    # `athrow()` doesn't re-raise if the generator is exhausted, which is shown below.


async def test_demo_athrow_problem() -> None:
    '''Show `athrow` doesn't re-raise after the async generator is exhausted.

    In contrast, `throw` re-raises even after the generator is exhausted.
    '''

    #
    # Show a generator re-raise when `throw` is called after it's exhausted.
    #

    def gen():
        '''An example generator.'''

        yield 'foo'
        yield 'bar'

    g = gen()
    l = list(g)
    assert l == ['foo', 'bar']

    # Now `g` is exhausted.
    with pytest.raises(StopIteration):
        next(g)

    # `throw` re-raise
    with pytest.raises(Exception) as excinfo:
        thrown = Exception('gen')
        g.throw(thrown)

    assert excinfo.value is thrown

    #
    # Show an async generator doesn't re-raise when `athrow` is called after it's exhausted.
    #

    async def agen():
        '''An example async generator.'''

        yield 'foo'
        yield 'bar'

    g = agen()
    l = [x async for x in g]
    assert l == ['foo', 'bar']

    # Now `g` is exhausted.
    with pytest.raises(StopAsyncIteration):
        await anext(g)

    # `athrow` doesn't re-raise, i.e. this test passes.
    thrown = Exception('gen')
    await g.athrow(thrown)
