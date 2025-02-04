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
from .exc import GeneratorDidNotYield, MockException
from .handle import ExceptionHandler


class MockContext:
    _ActionName = Literal['yield', 'raise', 'break']
    _ActionItem: TypeAlias = Union[
        tuple[Literal['yield'], str],
        tuple[Literal['raise'], Exception],
        tuple[Literal['break'], None],
    ]
    _ActionMap: TypeAlias = Mapping[CtxId, _ActionItem]
    _ACTIONS: tuple[_ActionName, ...] = ('yield', 'raise', 'break')

    def __init__(self, data: st.DataObject) -> None:
        self._data = data
        self._draw = data.draw
        self._generate_ctx_id = ContextIdGenerator()
        self._ctxs_map: dict[CtxId, GenCtxMngr] = {}
        self._created_ctx_ids: list[CtxId] = []
        self._entered_ctx_ids: list[CtxId] = []
        self._exiting_ctx_ids: list[CtxId] = []
        self._exception_handler: Union[ExceptionHandler, None] = None
        self._clear()

    def _clear(self) -> None:
        self._action_map: Union[MockContext._ActionMap, None] = None

    def __call__(self) -> GenCtxMngr[str]:
        id = self._generate_ctx_id()
        self._created_ctx_ids.append(id)

        @contextmanager
        def _ctx() -> Iterator[str]:
            self._entered_ctx_ids.append(id)
            try:
                for _ in range(1):
                    assert self._action_map is not None
                    action_item = self._action_map[id]
                    if action_item[0] == 'raise':
                        raise action_item[1]
                    if action_item[0] == 'break':
                        break
                    try:
                        assert action_item[0] == 'yield'
                        yield action_item[1]
                    except Exception as e:
                        note(f'ctx {id=} except: {e=}')
                        assert self._exception_handler is not None
                        self._exception_handler.handle(id, e)
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
        self._action_map = self._draw_actions(self._created_ctx_ids)
        note(f'{self.__class__.__name__}: {self._action_map=}')

        self._exception_handler = self._draw_exception_handler()

    def _draw_exception_handler(self) -> Union[ExceptionHandler, None]:
        if not self._action_map:
            return None

        id, last_action_item = list(self._action_map.items())[-1]
        ids = self._created_ctx_ids[: self._created_ctx_ids.index(id)]
        if last_action_item[0] == 'raise':
            exc = last_action_item[1]
            return ExceptionHandler(
                self._data, exc=exc, ids=reversed(ids), before_enter=True
            )
        elif last_action_item[0] == 'break':
            return ExceptionHandler(
                self._data,
                exc=GeneratorDidNotYield,
                ids=reversed(ids),
                before_enter=True,
            )
        return None

    def on_entered(self, yields: Iterable[str]) -> None:
        assert self._entered_ctx_ids == self._created_ctx_ids
        assert self._action_map is not None
        assert list(yields) == [self._action_map[id][1] for id in self._entered_ctx_ids]

    def on_exited(self, exc: Union[BaseException, None]) -> None:
        assert self._exiting_ctx_ids == list(reversed(self._entered_ctx_ids))
        if self._exception_handler is None:
            assert exc is None
        else:
            self._exception_handler.assert_exited(exc)

    def before_raise(self, exc: Exception) -> None:
        self._exception_handler = ExceptionHandler(
            self._data, exc=exc, ids=reversed(self._entered_ctx_ids)
        )

    def _draw_actions(self, ids: Iterable[CtxId]) -> _ActionMap:
        ids = list(ids)
        st_actions = st.sampled_from(self._ACTIONS)
        actions: list[MockContext._ActionName] = self._draw(
            st_list_until(st_actions, last={'raise', 'break'}, max_size=len(ids)),
            label=f'{self.__class__.__name__}: actions',
        )
        return {id: self._create_action_item(id, a) for id, a in zip(ids, actions)}

    def _create_action_item(self, id: CtxId, action: _ActionName) -> _ActionItem:
        if action == 'raise':
            return (action, MockException(f'{id}'))
        if action == 'yield':
            return (action, f'{id}')
        return (action, None)
