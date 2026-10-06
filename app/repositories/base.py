from typing import Protocol, TypeVar

EntityT = TypeVar("EntityT", covariant=True)
IdT = TypeVar("IdT", contravariant=True)


class ReadRepository(Protocol[EntityT, IdT]):
    """Load one aggregate by id.

    Add a protocol per aggregate in this package.
    Implement it in app/infrastructure/repositories.
    """

    def get(self, entity_id: IdT) -> EntityT | None: ...
