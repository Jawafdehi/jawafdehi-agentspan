from __future__ import annotations

from jawafdehi_agentspan.evidence.contracts import SourceChunk


def chunk_text(
    source_id: str,
    text: str,
    max_chars: int = 2800,
    overlap_chars: int = 250,
) -> list[SourceChunk]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be non-negative and less than max_chars")
    if not text:
        return []

    chunks: list[SourceChunk] = []
    step = max_chars - overlap_chars
    start = 0
    idx = 1

    while start < len(text):
        end = min(len(text), start + max_chars)
        content = text[start:end]
        chunks.append(
            SourceChunk(
                chunk_id=f"{source_id}#{idx:04d}",
                source_id=source_id,
                text=content,
                char_start=start,
                char_end=end,
                token_estimate=max(1, len(content) // 4),
            )
        )
        if end >= len(text):
            break
        start += step
        idx += 1

    return chunks


def estimate_prompt_chars(system: str, user: str, chunk_lengths: list[int]) -> int:
    return len(system) + len(user) + sum(chunk_lengths)
