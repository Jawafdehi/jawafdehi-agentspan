## File System Layout

The following directories are used by the CIAA workflow. All paths are absolute.

### Layout

The file system will be organized as following.

```
files/                # Usually a path in the system. aka: jawafdehi_file_store_root.
  data/               # Configuration data shared across cases. aka: "Data folder"
  cases/
    {case-number}/    # aka: "Case folder"
      sources/
        index.md      # Source preparation index: table of source artifacts plus detailed notes
        raw/          # Original downloaded files (PDFs, DOCs, HTML wrappers, etc.)
        markdown/     # Markdown conversions of raw sources
      news/
        raw/          # Original downloaded files (PDFs, etc.)
        markdown/     # Markdown conversions of raw sources
        summary.md
      tmp/
        run-{run-id}/  # The "run directory". aka "Run workspace" or "workspace root" in code.
```

### Run Directory

Each workflow run gets its own run directory in the file store. It is located at files/cases/{case-number}/tmp/run-{run-id}. Muliple case runs will live side by side.

```
files/cases/{case-number}/tmp/run-{run-id}/
  draft.md            # Working draft (intermediate, may be overwritten)
  draft-final.md      # Final approved draft (written when drafting is complete)
  draft-review.md     # Review document written by the reviewer agent
  logs/
    run.log           # Verbose run log
  case_details-{case_number}.md  # Case details fetched from NGM
  *.tmp               # Any temporary or scratch files created during the run belong here
```

Note: Sources should be saved in `{case_folder}/sources`, outside the run directory. Any temporary or scratch file must be saved in the run directory under `files/cases/{case-number}/tmp/run-{run-id}/`.

### Canonical Source Filenames

Use stable case-number-based filenames for saved source artifacts.

```
files/cases/{case-number}/sources/
  index.md
  raw/
    ciaa-press-release-{case-number}.html
    ciaa-press-release-{case-number}.{ext}
    ag-charge-sheet-{case-number}.pdf
  markdown/
    case-details-{case-number}.md
    ciaa-press-release-{case-number}.md
    ag-charge-sheet-{case-number}.md
```

The press-release source document extension may vary, but the basename must remain `ciaa-press-release-{case-number}`.

### Reference/Assets Data (/data directory)

Read-only CSV index files are available for lookups:

```
{data_dir}/
  ag_index.csv              # Attorney General charge sheet index. Use this to find the charge sheet.
  ciaa-press-releases.csv   # CIAA press release index (maps case numbers to press release IDs and URLs)
  ciaa-template.md          # The local Jawafdehi case template. Use this to draft a new Jawafdehi case.
```

Use `grepNew` tool to read these CSVs when looking up press release URLs or charge sheet information. The files may be quite large to read at once.


### Important Notes

- Always use absolute paths when reading or writing files.
- The case directory is shared across runs; DO NOT delete files from it.
- Keep `sources/index.md` updated as the running inventory of source preparation work.
- `sources/index.md` should include both a summary table of source artifacts and a detailed explanation section below the table.
- Write persistent source artifacts only to the case `sources/` folders using the canonical filenames.
- Write temporary or scratch files only to the case run directory.
- Write `draft-final.md` only when the draft has been reviewed and approved.
- **Never read `.log` files** — they are large debug logs and will cause errors. Ignore them entirely.

