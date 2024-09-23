import contextlib
import sys
from collections.abc import AsyncGenerator, Generator

from hypothesis import given
from hypothesis import strategies as st

from apluggy.stack import patch_aexit
from tests.utils import RecordReturns, ReplayReturns, st_none_or


@given(st.data())
async def test_patch_aexit(data: st.DataObject) -> None:
    '''`patch_aexit()` makes an async context manager propagate the exception
    in the same way as a context manager does.

    This test first develop the expectation by running a context manager and
    then compares the expectation with the actual result of an async context
    manager with `patch_aexit()`.
    '''
    exc = Exception('exc')

    st_with_action = st_none_or(st.sampled_from(['send', 'throw', 'close']))
    st_ctx_action = st_none_or(st.sampled_from(['raise', 'yield']))

    # Develop the expectation with a context manager
    @contextlib.contextmanager
    def ctx(draw: st.DrawFn) -> Generator[str, None, None]:
        yield 'foo'
        # TODO: When Python 3.9 support is dropped
        # match draw(st_ctx_action):
        #     case 'raise':
        #         raise exc
        #     case 'yield':
        #         yield 'bar'
        action = draw(st_ctx_action)
        if action == 'raise':
            raise exc
        elif action == 'yield':
            yield 'bar'

    draw = RecordReturns(data.draw)
    try:
        with (c := ctx(draw)) as x:
            assert x == 'foo'
            # TODO: When Python 3.9 support is dropped
            # match draw(st_with_action):
            #     case 'send':
            #         c.gen.send('sent')
            #     case 'throw':
            #         c.gen.throw(exc)
            #     case 'close':
            #         c.gen.close()
            action = draw(st_with_action)
            if action == 'send':
                c.gen.send('sent')
            elif action == 'throw':
                c.gen.throw(exc)
            elif action == 'close':
                c.gen.close()
    except Exception:
        exc_expected = sys.exc_info()
    else:
        exc_expected = sys.exc_info()

    # Run `patch_aexit()` on an async context manager
    @contextlib.asynccontextmanager
    async def actx(draw: st.DrawFn) -> AsyncGenerator[str, None]:
        yield 'foo'
        # TODO: When Python 3.9 support is dropped
        # match draw(st_ctx_action):
        #     case 'raise':
        #         raise exc
        #     case 'yield':
        #         yield 'bar'
        action = draw(st_ctx_action)
        if action == 'raise':
            raise exc
        elif action == 'yield':
            yield 'bar'

    draw = ReplayReturns(draw)

    # As `async with` doesn't work with `patch_aexit()`, `__aenter__()` and
    # `__aexit__()` are called explicitly.
    ac = actx(draw)
    try:
        with patch_aexit(ac):
            x = await ac.__aenter__()
            try:
                assert x == 'foo'
                # TODO: When Python 3.9 support is dropped
                # match draw(st_with_action):
                #     case 'send':
                #         await ac.gen.asend('sent')
                #     case 'throw':
                #         await ac.gen.athrow(exc)
                #     case 'close':
                #         await ac.gen.aclose()
                action = draw(st_with_action)
                if action == 'send':
                    await ac.gen.asend('sent')
                elif action == 'throw':
                    await ac.gen.athrow(exc)
                elif action == 'close':
                    await ac.gen.aclose()
            except Exception:
                if not await ac.__aexit__(*sys.exc_info()):
                    raise
            else:
                await ac.__aexit__(None, None, None)

    except Exception:
        exc_actual = sys.exc_info()
    else:
        exc_actual = sys.exc_info()

    # Assert the expectation and the actual result are the same
    if exc_expected == (None, None, None):
        assert exc_actual == (None, None, None)
    elif exc_expected[1] is exc:
        assert exc_actual[1] is exc
    elif isinstance(exc_expected[1], StopIteration):
        assert isinstance(exc_actual[1], StopAsyncIteration)
    elif isinstance(exc_expected[1], RuntimeError):
        assert isinstance(exc_actual[1], RuntimeError)
    else:
        assert False
