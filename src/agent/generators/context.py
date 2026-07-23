from __future__ import annotations

from src.agent.generators.evidence_packer import EvidencePacker
from src.schemas import EvidencePack, RetrievalResult


class EvidenceContextSerializer:
    """Compatibility facade around the intent-aware evidence packer."""

    def __init__(
        self,
        *,
        max_text_evidence: int = 8,
        max_graph_paths: int = 8,
        max_chars_per_evidence: int = 900,
        max_context_chars: int = 10000,
        comparison_evidence_per_entity: int = 2,
    ) -> None:
        self.packer = EvidencePacker(
            max_text_evidence=max_text_evidence,
            max_graph_paths=max_graph_paths,
            max_chars_per_evidence=max_chars_per_evidence,
            max_context_chars=max_context_chars,
            comparison_evidence_per_entity=comparison_evidence_per_entity,
        )

    def serialize(self, query: str, retrieval: RetrievalResult) -> str:
        return self.pack(query, retrieval).context

    def pack(self, query: str, retrieval: RetrievalResult) -> EvidencePack:
        return self.packer.pack(query, retrieval)
