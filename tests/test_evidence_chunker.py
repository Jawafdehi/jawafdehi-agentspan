from jawafdehi_agentspan.evidence.chunker import chunk_text, estimate_prompt_chars


def test_chunk_text_respects_max_chars() -> None:
    text = "अ" * 6200

    chunks = chunk_text("src1", text, max_chars=2000, overlap_chars=200)

    assert len(chunks) >= 3
    assert all(len(chunk.text) <= 2000 for chunk in chunks)
    assert chunks[0].chunk_id.startswith("src1#")


def test_estimate_prompt_chars_adds_system_and_user_content() -> None:
    system = "system"
    user = "user"
    chunks = [100, 200]

    assert estimate_prompt_chars(system, user, chunks) >= 306
