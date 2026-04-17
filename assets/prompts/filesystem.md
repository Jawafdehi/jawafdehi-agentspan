## File System Layout

The following directories are used by the CIAA workflow. All paths are absolute.

### Global Store

The global store persists data across runs for the same case.

```
{global_store_root}/
  cases/
    {case_number}/
      sources/
        raw/          # Original downloaded files (PDFs, etc.)
        markdown/     # Markdown conversions of raw sources
      news/
        raw/          # Raw downloaded news articles
        markdown/     # Markdown conversions of news articles
```

Key files in the global store:
- `{global_store_root}/cases/{case_number}/sources/raw/ciaa-press-release-*.{pdf,html,doc,docx,md}` — CIAA press release (filename uses press release ID, not case number)
- `{global_store_root}/cases/{case_number}/sources/raw/charge-sheet-{case_number}.pdf` — Charge sheet PDF (if available)
- `{global_store_root}/cases/{case_number}/sources/markdown/` — Markdown versions of all source documents

### Run Workspace

Each workflow run gets its own workspace directory under the runs root.

```
{workspace_root}/
  draft.md            # Working draft (intermediate, may be overwritten)
  draft-final.md      # Final approved draft (written when drafting is complete)
  draft-review.md     # Review document written by the reviewer agent
  tmp/                # Temporary files for this run
  logs/
    run.log           # Verbose run log
  data/
    case_details-{case_number}.md  # Case details fetched from NGM
```

### Reference Data

Read-only CSV index files are available for lookups:

```
{data_dir}/
  ag_index.csv              # Attorney General charge sheet index
  ciaa-press-releases.csv   # CIAA press release index (maps case numbers to press release IDs and URLs)
```

Use `read_file` to read these CSVs when looking up press release URLs or charge sheet information.

### Important Notes

- Always use absolute paths when reading or writing files.
- The global store is shared across runs; do not delete files from it.
- Write `draft-final.md` only when the draft has been reviewed and approved.
- The `workspace_root` for the current run is provided in the prompt.
