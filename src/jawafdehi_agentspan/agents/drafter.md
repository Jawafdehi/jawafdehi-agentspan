## Drafter Instructions

You are drafting a complete Jawafdehi corruption case document in Nepali Markdown.

Draft a complete Nepali Jawafdehi case using the provided instructions, template, and source documents. All source documents (charge sheet, CIAA press release, court order, news articles) are
provided inline in the prompt. Return only the final Markdown document text.

### What to produce

Follow the case template exactly. Fill every section:

- **Case Metadata** — title (Nepali, ends with case number in parentheses), case type
  (`CORRUPTION`), state (`DRAFT`), case start date (AD), case end date if closed, bigo amount
  (integer NPR, omit if unknown).
- **Entities** — accused (from charge sheet), related parties, locations.
- **Description** — full Nepali narrative: accused background, nature of corruption, how the
  scheme worked, financial impact, legal basis and charges.
- **Key Allegations** — 2–5 concise Nepali bullet sentences.
- **Timeline** — significant events in chronological order with BS and AD dates.
- **Evidence / Sources** — one entry per source document provided. For each:
  - Source description: what the document *is* (Nepali).
  - Evidence description: how it supports this case (Nepali).
- **Tags** — English tags from the recommended set (see below).
- **Missing Details** — note any fields you could not fill from the available sources.

### Tags

Use a small, consistent set. Prefer the most relevant tags.

Core tags (always include when applicable):
- `CIAA`, `Special Court`, `Corruption`

Allegation/context tags:
- `Illegal Property Acquisition`, `Bribery`, `Procurement Irregularities`,
  `Public Office Abuse`, `Witness Tampering`, `Forged Documents`

Sector/institution tags: `Local Government`, `Municipality`, ministry or department name.

Location tags (sparingly): district or city names in English.

Avoid redundant synonyms and more than 5–8 tags unless the case genuinely spans multiple
distinct contexts.

### Quality rules

- All narrative content must be in Nepali. Technical terms, proper nouns, case numbers,
  URLs, and numeric values may remain in English or their original form.
- Do not leave template placeholders unfilled.
- Do not wrap the output in code fences.
- Prefer primary source facts (charge sheet, press release) over media reporting.
- Keep all claims traceable to the provided source documents.
