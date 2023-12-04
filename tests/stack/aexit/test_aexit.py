import contextlib
import sys
from collections.abc import AsyncGenerator, Generator

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
