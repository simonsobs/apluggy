import sys
from abc import ABC, abstractmethod
from collections.abc import Iterable, MutableMapping, Sequence
from typing import Literal, Union

from hypothesis import strategies as st

from tests.utils import st_list_until

if sys.version_info >= (3, 10):
    from typing import TypeAlias
else:
    from typing_extensions import TypeAlias


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
        self._map: ActionMap = ActionMapNull()

    def __len__(self) -> int:
        return len(self._map)

    def before_enter(self, ctx_ids: Iterable[CtxId]) -> None:
        self._map = self._draw(
            st_action_map(ctx_ids, enabled_actions=self._enabled_actions_on_enter)
        )

    def before_send(self, ctx_ids: Iterable[CtxId]) -> None:
        self._map = self._draw(
            st_action_map(ctx_ids, enabled_actions=self._enabled_actions_on_sent)
        )

    def before_raise(self, exc: Exception) -> None:
        self._map = ActionMapExit()

    def before_exit(self) -> None:
        self._map = ActionMapExit()

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        return self._map.pop(ctx_id)

    @property
    def last_ctx_id(self) -> CtxId:
        assert isinstance(self._map, ActionMapMap)
        return self._map.last_ctx_id

    @property
    def last_action_item(self) -> _ActionItem:
        assert isinstance(self._map, ActionMapMap)
        return self._map.last_action_item

    @property
    def yields(self) -> tuple[str, ...]:
        assert isinstance(self._map, ActionMapMap)
        return self._map.yields

    @property
    def ctx_ids(self) -> list[CtxId]:
        assert isinstance(self._map, ActionMapMap)
        return self._map.ctx_ids


class ActionMap(ABC):
    @abstractmethod
    def __len__(self) -> int:
        pass

    @abstractmethod
    def pop(self, ctx_id: CtxId) -> _ActionItem:
        pass


class ActionMapNull(ActionMap):
    def __init__(self) -> None:
        pass

    def __len__(self) -> int:
        return 0

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        assert False


class ActionMapExit(ActionMap):
    def __init__(self) -> None:
        pass

    def __len__(self) -> int:
        return 0

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        return ('exit', None)


@st.composite
def st_action_map(
    draw: st.DrawFn, ctx_ids: Iterable[CtxId], enabled_actions: Sequence[CtxActionName]
) -> 'ActionMapMap':
    ctx_ids = list(ctx_ids)

    map_ = draw(_st_map(ctx_ids, enabled_actions))
    return ActionMapMap(map_)


@st.composite
def _st_map(
    draw: st.DrawFn,
    ctx_ids: Iterable[CtxId],
    enabled_actions: Sequence[CtxActionName],
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


class ActionMapMap(ActionMap):
    def __init__(self, action_map: _ActionMap) -> None:
        self._map = action_map

    def __len__(self) -> int:
        return len(self._map)

    def pop(self, ctx_id: CtxId) -> _ActionItem:
        return self._map.pop(ctx_id, ('exit', None))

    @property
    def last_ctx_id(self) -> CtxId:
        return list(self._map.keys())[-1]

    @property
    def last_action_item(self) -> _ActionItem:
        return list(self._map.values())[-1]

    @property
    def yields(self) -> tuple[str, ...]:
        return tuple(e[1] for e in self._map.values() if e[0] == 'yield')

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._map.keys())
