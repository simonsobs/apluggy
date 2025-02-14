from collections.abc import Iterable

from apluggy.stack import GenCtxMngr

from .ctx_id import ContextIdGenerator, CtxId


class Created:
    def __init__(self) -> None:
        self._ctx_ids: list[CtxId] = []
        self._ctxs: list[GenCtxMngr] = []
        self._new_ctx_id = ContextIdGenerator()

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._ctx_ids)

    def add(self, ctx: GenCtxMngr) -> CtxId:
        ctx_id = self._new_ctx_id()
        self._ctx_ids.append(ctx_id)
        self._ctxs.append(ctx)
        return ctx_id

    def assert_on_created(self, ctxs: Iterable[GenCtxMngr]) -> None:
        assert list(ctxs) == self._ctxs


class Entered:
    def __init__(
        self,
        ctx_ids_expected: Iterable[CtxId] = (),
        yields_expected: Iterable[str] = (),
    ) -> None:
        self._ctx_ids_expected = list(ctx_ids_expected)
        self._yields_expected = list(yields_expected)
        self._ctx_ids: list[CtxId] = []

    @property
    def ctx_ids(self) -> list[CtxId]:
        return list(self._ctx_ids)

    def add(self, ctx_id: CtxId) -> None:
        self._ctx_ids.append(ctx_id)

    def assert_on_entered(self, yields: Iterable[str]) -> None:
        assert self._ctx_ids == self._ctx_ids_expected
        assert list(yields) == self._yields_expected


class Sent:
    def __init__(self, sent_expected: str, yields_expected: Iterable[str]) -> None:
        self._sent_expected = sent_expected
        self._yields_expected = list(yields_expected)
        self._sent_actual: list[str] = []

    def add(self, sent: str) -> None:
        self._sent_actual.append(sent)

    def assert_on_sent(self, yields: Iterable[str]) -> None:
        assert len(self._sent_actual) == len(self._yields_expected)
        assert set(self._sent_actual) == {self._sent_expected}
        assert list(yields) == self._yields_expected
