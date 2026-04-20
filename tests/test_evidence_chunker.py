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
    chunks = [100, 196]

    assert estimate_prompt_chars(system, user, chunks) == 306


def test_chunk_text_rejects_non_positive_max_chars() -> None:
    try:
        chunk_text("src1", "abcdef", max_chars=0)
    except ValueError as exc:
        assert str(exc) == "max_chars must be positive"
    else:
        raise AssertionError("Expected ValueError")


def test_chunk_text_rejects_negative_overlap_chars() -> None:
    try:
        chunk_text("src1", "abcdef", overlap_chars=-1)
    except ValueError as exc:
        assert str(exc) == "overlap_chars must be non-negative and less than max_chars"
    else:
        raise AssertionError("Expected ValueError")


def test_chunk_text_maintains_overlap_continuity() -> None:
    text = "abcdefghijklmnopqrstuvwxyz"

    chunks = chunk_text("src1", text, max_chars=10, overlap_chars=3)

    assert len(chunks) > 1
    for index in range(len(chunks) - 1):
        assert chunks[index + 1].char_start == chunks[index].char_end - 3
