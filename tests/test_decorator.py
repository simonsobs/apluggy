from pluggy._hooks import varnames

from apluggy import asynccontextmanager, contextmanager


@asynccontextmanager
async def acontext(arg1, arg2):
    yield arg1 + arg2


@contextmanager
def context(arg1, arg2):
    yield arg1 + arg2


async def test_acontext():
    expected = (('arg1', 'arg2'), ())
    assert varnames(acontext) == expected
    async with acontext(1, 2) as result:
        assert result == 3


async def test_context():
    expected = (('arg1', 'arg2'), ())
    assert varnames(context) == expected
    with context(1, 2) as result:
        assert result == 3
