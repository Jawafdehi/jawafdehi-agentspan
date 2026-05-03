# Jawafdehi Drafting Workflow Design (Payload-Safe Multi-Agent Orchestration)

Date: 2026-04-20  
Status: Approved for planning

## 1. Problem Statement

The current drafting pipeline can exceed LLM payload limits (around 256 KB) when large source documents are repeatedly loaded into multi-turn agent contexts. This causes runtime failures and unstable completion behavior before `draft-final.md` is produced.

At the same time, the output must remain factually complete and traceable, with all required template sections filled, including explicit handling for missing facts.

## 2. Goals

1. Reliably produce `draft-final.md` without payload overflow.
2. Preserve full factual coverage from available sources.
3. Enforce claim-to-source traceability.
4. Keep all required template sections present; when data is unavailable, explicitly mark `"not available from sources"`.
5. Generate `short_description` alongside the final draft.

## 3. Non-Goals

1. Full publishing workflow redesign (outside drafting finalization scope).
2. UI changes for public site rendering.
3. New source types beyond current CIAA/AG/case details baseline.

## 4. Recommended Architecture

Use a staged, artifact-driven, payload-safe workflow:

1. **Source Preparation Agent**
   - Ensures canonical case source structure exists.
   - Maintains `sources/index.md`.
   - Produces `source-registry.json` with normalized source metadata.

2. **Evidence Structuring Agent**
   - Reads source markdown in bounded chunks.
   - Produces `source-chunks/<source_id>.jsonl`.
   - Extracts normalized facts into `claim-candidates.jsonl`.

3. **Section Drafting Swarm**
   - One focused drafting agent per section:
     - metadata
     - entities
     - description
     - key allegations
     - timeline
     - evidence/sources
     - tags
     - missing details
     - short description
   - Each agent receives only relevant chunks + claims.
   - Outputs `draft-section-<section>.md`.

4. **Composer + Validator Agent**
   - Composes `draft-final.md` in template order.
   - Produces `traceability-map.json`.
   - Runs completeness + traceability validation before acceptance.

5. **Review + Single Revision Loop**
   - Reviewer evaluates `draft-final.md` and traceability artifacts.
   - Reviser updates only failing sections.
   - Recompose and revalidate once.

## 5. Data Contracts

### 5.1 `source-registry.json`

Each source item includes:
- `source_id`
- `source_type`
- `url`
- `raw_path`
- `markdown_path`
- `status` (`existing|downloaded|converted|missing`)

### 5.2 `source-chunks/<source_id>.jsonl`

Each line includes:
- `chunk_id`
- `source_id`
- `text`
- `char_start`
- `char_end`
- `token_estimate`

### 5.3 `claim-candidates.jsonl`

Each line includes:
- `claim_id`
- `claim_type` (e.g., accused_name, amount, date, legal_ref)
- `value`
- `confidence`
- `source_refs` (`source_id`, `chunk_id`)

### 5.4 `traceability-map.json`

Maps final draft claims to evidence:
- `claim_text`
- `section`
- `source_refs` (one or more `source_id/chunk_id`)

## 6. Payload Control Strategy

1. **Chunk limits**: bounded chunk size (2k-3k chars target).
2. **Prompt limits**: bounded chunks per prompt (8-12 target).
3. **Section isolation**: section agents are stateless, no large shared conversational memory.
4. **Preflight estimator**: estimate prompt size before model call; auto-split retrieval rounds if threshold is exceeded.
5. **No full-corpus prompts**: entire source corpus must never be sent in a single request.

## 7. End-to-End Workflow

1. Initialize workspace and fetch case details.
2. Gather and normalize source metadata.
3. Prepare/download/convert missing sources.
4. Build source registry and chunks.
5. Extract structured claims.
6. Draft each section with targeted evidence.
7. Compose final draft.
8. Validate completeness and traceability.
9. Review and optionally revise once.
10. Emit final artifacts:
   - `draft-final.md`
   - `short-description.txt`
   - `traceability-map.json`
   - `validation-report.json`

## 8. Validation and Error Handling

### 8.1 Completeness Gate

Fail if any required section/field is missing from final draft.

### 8.2 Traceability Gate

Fail if key factual claims (amounts, dates, accused identities, legal bases, timeline events) are not mapped to at least one source reference.

### 8.3 Payload Gate

Fail-safe behavior: split retrieval and retry with smaller context before sending an oversized request.

### 8.4 Revision Gate

Allow one bounded revision pass; if still blocked, emit actionable diagnostics instead of looping indefinitely.

## 9. Testing Strategy

1. **Unit tests**
   - Chunking boundaries
   - Claim extraction schema validity
   - Prompt size estimator and split behavior
   - Section composition and placeholder enforcement

2. **Integration tests**
   - End-to-end run with medium source corpus
   - Simulated oversized source corpus to verify payload-safe splitting
   - Traceability map generation and validation failures

3. **Quality tests**
   - Required section coverage
   - Deterministic handling of missing facts (`"not available from sources"`)

## 10. Risks and Mitigations

1. **Risk:** Over-fragmented chunks reduce coherence.  
   **Mitigation:** section-level retrieval ranking and limited neighboring-chunk inclusion.

2. **Risk:** Claim extraction misses critical facts.  
   **Mitigation:** reviewer gate checks key claim classes and forces targeted re-extraction.

3. **Risk:** Increased orchestration complexity.  
   **Mitigation:** strict artifact contracts and deterministic stage boundaries.

## 11. Acceptance Criteria

The design is considered successful when:

1. `draft-final.md` is produced without payload overflow.
2. All required sections are present.
3. Missing facts are explicitly marked as `"not available from sources"`.
4. Key claims are traceable via `traceability-map.json`.
5. `short-description.txt` is produced.
