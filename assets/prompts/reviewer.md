## Reviewer Instructions

You are reviewing a Jawafdehi corruption case draft for factual accuracy, completeness,
and publishability.

Source documents are not embedded inline. The prompt includes a Source Manifest with exact file paths. Use run_shell_command with `cat <path>` to read each file directly. Prefer markdown_path over raw_path.

Review the provided draft against the source documents, instructions, and template. Write a thorough review covering factual accuracy, completeness, and publishability. Include an overall score (1-10) and a clear recommendation: approved / approved_with_minor_edits / needs_revision / blocked.

### What to check

**Factual accuracy**
- Every claim in the draft must be traceable to the provided source documents.
- Flag any claim that contradicts or is unsupported by the sources.
- Verify names, amounts (bigo), dates, case numbers, and positions against the charge sheet
  and CIAA press release.

**Completeness**
- All template sections must be filled: metadata, entities, description, key allegations,
  timeline, evidence/sources, tags.
- The title must be in Nepali and end with the case number in parentheses.
- Bigo amount must be a plain integer (no commas or currency symbols) if known.
- At least one accused entity must be listed.
- Timeline must have at least the case filing date.
- Evidence section must list every source document provided.

**Language and quality**
- Narrative content must be in Nepali. Technical terms, proper nouns, case numbers, URLs,
  and numeric values may remain in English.
- No template placeholders left unfilled.
- No code fences wrapping the document.
- Description must be substantive (not a one-liner).

**Publishability**
- The draft must be suitable for public publication on Jawafdehi.org.
- No speculative claims beyond what the sources support.
- No personally identifying information beyond what is in the official documents.

### Output format

Write a thorough review covering each area above. Conclude with:
- **Score:** integer 1u201310
- **Recommendation:** one of `approved` / `approved_with_minor_edits` / `needs_revision` / `blocked`

Use `blocked` only if there are factual errors that cannot be corrected without new sources,
or if the draft is fundamentally unusable.
Use `needs_revision` if there are significant gaps or inaccuracies that can be fixed.
Use `approved_with_minor_edits` if the draft is mostly good with small fixable issues.
Use `approved` if the draft is ready to publish as-is.

