import builtins
from typing import Union

from hypothesis import given, note
from hypothesis import strategies as st

from .exc import ExceptionExpectation, MockException


@given(data=st.data())
def test_eq(data: st.DataObject) -> None:
    exc1 = data.draw(_st_exc(None))
    exc2 = data.draw(_st_exc(exc1))

    method = data.draw(st.sampled_from(ExceptionExpectation.METHODS))
    exp = ExceptionExpectation(exc1, method=method)
    note(exp)

    if method == 'is':
        assert (exp == exc2) is (exc1 is exc2)
    elif method == 'type':
        assert (exp == exc2) is isinstance(exc2, type(exc1))
    elif method == 'type-msg':
        res = isinstance(exc2, type(exc1)) and str(exc2) == str(exc1)
        assert (exp == exc2) is res
    else:  # pragma: no cover
        raise ValueError(method)


@st.composite
def _st_exc(
    draw: st.DrawFn,
    exc: Union[BaseException, None],
) -> Union[BaseException, None]:
    OPTIONS = ('none', 'as-is', 'type', 'type-msg', 'else')
    option = draw(st.sampled_from(OPTIONS))
    if option == 'none':
        return None
    if option == 'as-is':
        return exc
    if option == 'type':
        if exc is None:
            return None
        msg = draw(st.text())
        return exc.__class__(msg)
    if option == 'type-msg':
        if exc is None:
            return None
        return exc.__class__(str(exc))
    cls = draw(st.one_of(st.just(MockException), st.sampled_from(BUILTIN_EXCEPTIONS)))
    msg = draw(st.text())
    return cls(msg)


def _collect_builtin_exceptions():
    '''Return all built-in exceptions `Exc` in which `msg = str(Exc(msg))`.

    E.g.:
    (<class 'BaseException'>, <class 'Exception'>, <class 'TypeError'>, ...)
    '''

    def _validate(cls):
        if not isinstance(cls, type):
            return False
        if not issubclass(cls, BaseException):
            return False
        try:
            msg = 'error-message'
            return msg == str(cls(msg))
        except Exception:
            return False

    return tuple(cls for _, cls in vars(builtins).items() if _validate(cls))


BUILTIN_EXCEPTIONS = _collect_builtin_exceptions()
