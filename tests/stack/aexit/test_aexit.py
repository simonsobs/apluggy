import contextlib
import sys
from collections.abc import AsyncGenerator, Generator

import pytest
from hypothesis import given
from hypothesis import strategies as st

from apluggy.stack import patch_aexit
from apluggy.test import RecordReturns, ReplayReturns, st_none_or


@given(st.data())
async def test_patch_aexit(data: st.DataObject) -> None:
    exc = Exception('exc')

    st_with_action = st_none_or(st.sampled_from(['send', 'throw', 'close']))
    st_ctx_action = st_none_or(st.sampled_from(['raise', 'yield']))

    @contextlib.contextmanager
    def ctx(draw: st.DrawFn) -> Generator[str, None, None]:
        yield 'foo'
        match draw(st_ctx_action):
            case 'raise':
                raise exc
            case 'yield':
                yield 'bar'

    draw = RecordReturns(data.draw)
    try:
        with (c := ctx(draw)) as x:
            assert x == 'foo'
            match draw(st_with_action):
                case 'send':
                    c.gen.send('sent')
                case 'throw':
                    c.gen.throw(exc)
                case 'close':
                    c.gen.close()
    except Exception:
        exc_expected = sys.exc_info()
    else:
        exc_expected = sys.exc_info()

    @contextlib.asynccontextmanager
    async def actx(draw: st.DrawFn) -> AsyncGenerator[str, None]:
        yield 'foo'
        match draw(st_ctx_action):
            case 'raise':
                raise exc
            case 'yield':
                yield 'bar'

    draw = ReplayReturns(draw)
    ac = actx(draw)
    try:
        x = await ac.__aenter__()
        try:
            assert x == 'foo'
            match draw(st_with_action):
                case 'send':
                    await ac.gen.asend('sent')
                case 'throw':
                    await ac.gen.athrow(exc)
                case 'close':
                    await ac.gen.aclose()
        except Exception:
            with patch_aexit(ac):
                if not await ac.__aexit__(*sys.exc_info()):
                    raise
        else:
            with patch_aexit(ac):
                await ac.__aexit__(None, None, None)

    except Exception:
        exc_actual = sys.exc_info()
    else:
        exc_actual = sys.exc_info()

    if exc_expected == (None, None, None):
        assert exc_actual == (None, None, None)
    elif isinstance(exc_expected[1], StopIteration):
        assert isinstance(exc_actual[1], StopAsyncIteration)
    elif isinstance(exc_expected[1], RuntimeError):
        assert isinstance(exc_actual[1], RuntimeError)
    elif exc_expected[1] is exc:
        assert exc_actual[1] is exc
    else:
        assert False


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
