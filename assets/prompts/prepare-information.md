## Prepare Information Instructions

You are responsible for downloading and preparing all source documents needed to draft a CIAA corruption case.

The canonical source location is `files/cases/{case-number}/sources/`. Save persistent source artifacts only inside that case `sources/` folder. Any temporary or scratch file must be saved in the current case run folder under `files/cases/{case-number}/tmp/run-{run-id}/`, not in the shared case source folders.

### Available tools

These tools should be available for you to prepare the information.

- `read_file(file_path)` — read a file's contents
- `write_file(file_path, content)` — write text content to a file
- `list_files(directory, pattern)` — list files and folders; files show line count, folders end with `/`
- `mkdir(directory_path)` — create a directory inside the current case folder; warns if it already exists
- `tree(directory)` — show full directory structure with file sizes
- `grepNew(pattern, path)` — search for text in files
- `fetch_url(url)` — fetch a URL and return its text content
- `download_file(url, output_path)` — download a binary file to disk
- `convert_to_markdown(file_path, output_path)` — convert a document to Markdown
- `ngm_extract_case_data(court_identifier, case_number, file_path)` — fetch the latest case details from NGM

### What to do

#### Step 1: Setup

Before downloading anything, inspect the current case sources directory and the run directory. Check whether the expected source artifacts already exist and whether their markdown conversions already exist.

You must ensure these case folders exist before downloading files:

- `files/cases/{case-number}/sources/`
- `files/cases/{case-number}/sources/raw/`
- `files/cases/{case-number}/sources/markdown/`

You must also maintain `files/cases/{case-number}/sources/index.md` throughout the preparation process.

At the beginning of the run, use `ngm_extract_case_data(court_identifier, case_number, file_path)` to fetch the latest case details from NGM and save that output as a markdown source in `files/cases/{case-number}/sources/markdown/case-details-{case-number}.md`. Record it in `files/cases/{case-number}/sources/index.md` like any other source artifact.

#### Step 2: Maintain `sources/index.md`

The file `files/cases/{case-number}/sources/index.md` should be the running index of source preparation work.

It must contain:

1. A compact markdown table with one row per source.
2. A detailed explanation section below the table.

The table should include these columns:

- source type
- URL
- raw filename
- markdown filename
- status

Use statuses such as `existing`, `downloaded`, `converted`, and `missing`.

The explanation section should summarize what was found, what was downloaded, what was converted, and any missing, ambiguous, or pending issues.

Create or refresh `sources/index.md` during setup, then update both the table and the explanation section after each meaningful source action.

#### Step 3: Download missing sources

Once the source folders and `sources/index.md` are ready, download and prepare any missing sources.

### Special case: CIAA press release

The press release is a CIAA website HTML page such as `https://ciaa.gov.np/pressrelease/3354`. The actual press release document may be a PDF, DOC, or DOCX linked from that page.

Use these canonical filenames for the press release:

- HTML wrapper: `files/cases/{case-number}/sources/raw/ciaa-press-release-{case-number}.html`
- raw source document: `files/cases/{case-number}/sources/raw/ciaa-press-release-{case-number}.{ext}`
- markdown conversion: `files/cases/{case-number}/sources/markdown/ciaa-press-release-{case-number}.md`

The source document extension may vary, but the basename must remain `ciaa-press-release-{case-number}`.

To download the press release:
1. Use `grepNew` on `ciaa-press-releases.csv` to locate the relevant press release entry for the case.
2. If you have the press release page URL, use `fetch_url` to fetch the HTML page and save it with `write_file` to `files/cases/{case-number}/sources/raw/ciaa-press-release-{case-number}.html`.
3. Inspect that saved HTML and find the linked `.pdf`, `.doc`, or `.docx` source document URL.
4. Use `download_file` to save the linked source document to `files/cases/{case-number}/sources/raw/ciaa-press-release-{case-number}.{ext}` using the detected extension.
5. Use `convert_to_markdown` to convert that exact raw file to `files/cases/{case-number}/sources/markdown/ciaa-press-release-{case-number}.md`.
6. Update `files/cases/{case-number}/sources/index.md` after each step.

### Using the reference data CSVs

Before downloading, check the reference data CSVs shown in the File System Layout section:

- `ciaa-press-releases.csv` — use `grepNew` to discover press release IDs and direct source URLs. Use the discovered URL for network access, but always save the local files using the canonical case-number-based filenames.
- `ag_index.csv` — use `grepNew` to discover Attorney General charge sheet URLs. Use the discovered URL for network access, but always save the local files using the canonical case-number-based filenames.

Use `grepNew` to search these CSVs rather than reading the entire file.

### Special case: charge sheet

Use these canonical filenames for the charge sheet:

- raw source document: `files/cases/{case-number}/sources/raw/ag-charge-sheet-{case-number}.pdf`
- markdown conversion: `files/cases/{case-number}/sources/markdown/ag-charge-sheet-{case-number}.md`

If the charge sheet URL is available, use `download_file` to save it to `files/cases/{case-number}/sources/raw/ag-charge-sheet-{case-number}.pdf`, then use `convert_to_markdown` to convert it to `files/cases/{case-number}/sources/markdown/ag-charge-sheet-{case-number}.md`. Update `files/cases/{case-number}/sources/index.md` after each step.

### Notes

- Always use the canonical local filenames described above.
- Do not mirror remote filenames into the case directory.
- Save persistent source artifacts in the case `sources/` folder.
- Save scratch or temporary files only in the case run folder.
- Use `tree` to verify the directory structure before and after downloading.
- **Never read `.log` files** — they are large debug logs and will cause errors.
