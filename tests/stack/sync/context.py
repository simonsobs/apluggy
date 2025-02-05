import sys
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from typing import Literal, Union

from hypothesis import note
from hypothesis import strategies as st

from apluggy.stack import GenCtxMngr
from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


from .ctx_id import ContextIdGenerator, CtxId
from .exc import ExceptionExpectation, GeneratorDidNotYield, MockException, wrap_exc
from .handle import (
    ExceptionHandler,
    ExceptionHandlerNull,
    st_exception_handler_before_enter,
    st_exception_handler_before_raise,
)

_ActionName = Literal['yield', 'raise', 'break']
_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['break'], None],
]
_ActionMap: TypeAlias = Mapping[CtxId, _ActionItem]
_ACTIONS: tuple[_ActionName, ...] = ('yield', 'raise', 'break')


class MockContext:
    def __init__(self, data: st.DataObject) -> None:
        self._draw = data.draw
        self._generate_ctx_id = ContextIdGenerator()
        self._ctxs_map: dict[CtxId, GenCtxMngr] = {}
        self._created_ctx_ids: list[CtxId] = []
        self._entered_ctx_ids: list[CtxId] = []
        self._exiting_ctx_ids: list[CtxId] = []
        self._clear()

    def _clear(self) -> None:
        self._exc_handler: ExceptionHandler = ExceptionHandlerNull()
        self._action_map: Union[_ActionMap, None] = None
        self._exc_expected = ExceptionExpectation(None)

    def __call__(self) -> GenCtxMngr[str]:
        id = self._generate_ctx_id()
        self._created_ctx_ids.append(id)

        @contextmanager
        def _ctx() -> Iterator[str]:
            self._entered_ctx_ids.append(id)
            try:
                while True:
                    assert self._action_map is not None
                    action_item = self._action_map[id]
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    elif action_item[0] == 'break':
                        break
                    elif action_item[0] == 'yield':
                        try:
                            sent = yield action_item[1]
                        except Exception as e:
                            note(f'ctx {id=} except: {e=}')
                            assert self._exc_handler is not None
                            self._exc_handler.handle(id, e)
                    else:  # pragma: no cover
                        raise ValueError(f'Unknown action: {action_item[0]!r}')
                    break
            finally:
                self._exiting_ctx_ids.append(id)

        ctx = _ctx()
        self._ctxs_map[id] = ctx
        return ctx

    @contextmanager
    def context(self) -> Iterator[None]:
        # TODO: Delete this method if it's not used.
        # self._clear()
        yield

    def assert_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == [self._ctxs_map[id] for id in self._created_ctx_ids]

    def before_enter(self) -> None:
        self._clear()
        self._action_map = self._draw(_draw_actions(self._created_ctx_ids))
        note(f'{self.__class__.__name__}: {self._action_map=}')

        exp, ids = _expect_exc_and_entered_ctx_ids(self._action_map)
        if exp != None:  # noqa: E711
            self._exc_handler = self._draw(
                st_exception_handler_before_enter(exp=exp, ids=reversed(ids))
            )
        note(f'{self.__class__.__name__}: {self._exc_handler=}')

        exp_on_handle = wrap_exc(GeneratorDidNotYield)
        self._exc_expected = self._exc_handler.expect_outermost_exc(
            exp_on_handle=exp_on_handle
        )
        note(f'{self.__class__.__name__}: {self._exc_expected=}')

    def on_entered(self, yields: Iterable[str]) -> None:
        assert self._entered_ctx_ids == self._created_ctx_ids
        assert self._action_map is not None
        assert list(yields) == [self._action_map[id][1] for id in self._entered_ctx_ids]

    def before_send(self, sent: str) -> None:
        note(f'{MockContext.__name__}: {sent=}')
        self._clear()
        self._exc_expected = wrap_exc(StopIteration())
        note(f'{self.__class__.__name__}: {self._exc_expected=}')

    def on_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._exiting_ctx_ids == list(reversed(self._entered_ctx_ids))
        if self._exc_handler is None:
            assert exc is None
        else:
            self._exc_handler.assert_on_exited(exc)
        assert self._exc_expected == exc

    def before_raise(self, exc: Exception) -> None:
        self._clear()
        exp = wrap_exc(exc)
        self._exc_handler = self._draw(
            st_exception_handler_before_raise(
                exp=exp, ids=reversed(self._entered_ctx_ids)
            )
        )

        if self._exc_handler is not None:
            self._exc_expected = self._exc_handler.expect_outermost_exc()
        note(f'{self.__class__.__name__}: {self._exc_expected=}')


@st.composite
def _draw_actions(draw: st.DrawFn, ids: Iterable[CtxId]) -> _ActionMap:
    ids = list(ids)
    st_actions = st.sampled_from(_ACTIONS)
    actions: list[_ActionName] = draw(
        st_list_until(st_actions, last={'raise', 'break'}, max_size=len(ids))
    )
    note(f'{MockContext.__name__}: {actions=}')
    return {id: _create_action_item(id, a) for id, a in zip(ids, actions)}


def _create_action_item(id: CtxId, action: _ActionName) -> _ActionItem:
    if action == 'raise':
        return (action, MockException(f'{id}'))
    if action == 'yield':
        return (action, f'{id}')
    return (action, None)


def _expect_exc_and_entered_ctx_ids(
    action_map: _ActionMap,
) -> tuple[ExceptionExpectation, list[CtxId]]:
    if not action_map:
        return ExceptionExpectation(None), []

    last_action_item = list(action_map.values())[-1]

    if last_action_item[0] == 'raise':
        ids = list(action_map.keys())[:-1]
        exc = last_action_item[1]
        exp = wrap_exc(exc)
        return exp, ids
    elif last_action_item[0] == 'break':
        ids = list(action_map.keys())[:-1]
        exc = GeneratorDidNotYield
        exp = wrap_exc(exc)
        return exp, ids
    elif last_action_item[0] == 'yield':
        ids = list(action_map.keys())
        return wrap_exc(None), ids
    else:  # pragma: no cover
        raise ValueError(f'Unknown action: {last_action_item[0]!r}')
