from collections.abc import Iterable, MutableMapping, Sequence
from typing import Literal, Optional, TypeAlias, Union

from hypothesis import strategies as st

from tests.utils import st_list_until

from .ctx_id import CtxId
from .exc import MockException

CtxActionName = Literal['yield', 'raise', 'exit']
CTX_ACTIONS: Sequence[CtxActionName] = ('yield', 'raise', 'exit')


_ActionItem: TypeAlias = Union[
    tuple[Literal['yield'], str],
    tuple[Literal['raise'], Exception],
    tuple[Literal['exit'], None],
]
_ActionMap: TypeAlias = MutableMapping[CtxId, _ActionItem]


class ContextActionStrategy:
    def __init__(
        self,
        data: st.DataObject,
        enabled_actions_on_enter: Sequence[CtxActionName],
        enabled_actions_on_sent: Sequence[CtxActionName],
    ) -> None:
        self._data = data
        self._draw = data.draw
        self._enabled_actions_on_enter = enabled_actions_on_enter
        self._enabled_actions_on_sent = enabled_actions_on_sent
        self.clear()

    def clear(self) -> None:
        self._map: Optional[_ActionMap] = None

    def __len__(self) -> int:
        if self._map is None:
            return 0
        return len(self._map)

    def before_enter(self, ctx_ids: Iterable[CtxId]) -> None:
        self._map = self._draw(
            _st_action_map(ctx_ids, enabled_actions=self._enabled_actions_on_enter)
        )

    def before_send(self, ctx_ids: Iterable[CtxId]) -> None:
        self._map = self._draw(
            _st_action_map(ctx_ids, enabled_actions=self._enabled_actions_on_sent)
        )

    def before_raise(self, exc: Exception) -> None:
        self._map = {}  # Let pop() return ('exit', None)

    def before_exit(self) -> None:
        self._map = {}  # Let pop() return ('exit', None)

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        if self._map is None:  # pragma: no cover
            raise KeyError(ctx_id)
        return self._map.pop(ctx_id, ('exit', None))

    @property
    def last_ctx_id(self) -> CtxId:
        assert self._map is not None
        return list(self._map.keys())[-1]

    @property
    def last_action_item(self) -> _ActionItem:
        assert self._map is not None
        return list(self._map.values())[-1]

    @property
    def yields(self) -> tuple[str, ...]:
        assert self._map is not None
        return tuple(e[1] for e in self._map.values() if e[0] == 'yield')

    @property
    def ctx_ids(self) -> list[CtxId]:
        assert self._map is not None
        return list(self._map.keys())


@st.composite
def _st_action_map(
    draw: st.DrawFn, ctx_ids: Iterable[CtxId], enabled_actions: Sequence[CtxActionName]
) -> _ActionMap:
    ctx_ids = list(ctx_ids)
    st_actions = st.sampled_from(enabled_actions)
    actions: list[CtxActionName] = draw(
        st_list_until(st_actions, last={'raise', 'exit'}, max_size=len(ctx_ids))
    )

    def _action_item(id: CtxId, action: CtxActionName) -> _ActionItem:
        if action == 'raise':
            return ('raise', MockException(f'{id}'))
        if action == 'yield':
            return ('yield', f'yield-{id}')
        if action == 'exit':
            return ('exit', None)
        raise ValueError(f'Unknown action: {action!r}')  # pragma: no cover

    return {id: _action_item(id, a) for id, a in zip(ctx_ids, actions)}
