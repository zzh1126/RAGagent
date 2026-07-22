from __future__ import annotations

from typing import Protocol


class GraphRepository(Protocol):
    def find_entity(self, name: str) -> dict | None:
        ...

    def get_neighbors(
        self,
        entity_id: str,
        relation_types: list[str] | None = None,
        include_incoming: bool = True,
    ) -> list[dict]:
        ...

    def find_paths(
        self,
        source_id: str,
        target_id: str | None = None,
        max_hops: int = 2,
    ) -> list[dict]:
        ...

    def validate_path(self, triples: list[dict]) -> bool:
        ...
