## Prepare Information Instructions

You are responsible for downloading and preparing all source documents needed to draft a CIAA corruption case.

The prompt includes:
- A **File System Layout** section describing the global store and run workspace directories with their absolute paths.
- A **Source Manifest** listing the documents to download, with their `source_url`, `raw_path`, and `markdown_path`.

### Available tools

- `read_file(file_path)` — read a file's contents
- `write_file(file_path, content)` — write text content to a file
- `list_files(directory, pattern)` — list files and folders; files show line count, folders end with `/`
- `tree(directory)` — show full directory structure with file sizes
- `grep(pattern, path)` — search for text in files
- `fetch_url(url)` — fetch a URL and return its text content
- `download_file(url, output_path)` — download a binary file to disk
- `convert_to_markdown(file_path, output_path)` — convert a document to Markdown

### What to do

**Step 1: Orient yourself.**
Start by calling `tree` on the global store sources directory (see File System Layout for the path) to see what files already exist. Also call `tree` on the run workspace directory to see what has been done in this run. Read any existing markdown files that are relevant.

**Step 2: Download missing sources.**
For each source in the manifest that has a `source_url`:

1. Check the `tree` output to see if `raw_path` already exists. If it does, skip downloading.
2. Download the document (see special cases below).
3. Use `convert_to_markdown` to convert the downloaded file and save the result to `markdown_path`.

**Step 3: Verify.**
Call `tree` again on the sources directory to confirm all expected files are present.

### Special case: CIAA press release

The press release `source_url` is a CIAA website HTML page (e.g. `https://ciaa.gov.np/pressrelease/3354`). The actual press release document is linked inside that page.

To download the press release:
1. Use `fetch_url` to fetch the HTML page and save it to `raw_path` (which ends in `.html`) using `write_file`.
2. Look for a link to a `.doc`, `.docx`, or `.pdf` file inside the HTML (e.g. `href="https://ciaa.gov.np/uploads//pressRelease/..."`).
3. Use `download_file` to download that linked document next to the HTML file with the correct extension (e.g. replace `.html` with `.pdf` or `.doc`).
4. Use `convert_to_markdown` to convert the downloaded document and save to `markdown_path`.

### Using the reference data CSVs

Before downloading, check the reference data CSVs (paths shown in the File System Layout section):

- `ciaa-press-releases.csv` — maps case numbers to press release IDs and direct document URLs. If the case number is listed, you can use the URL directly with `download_file` instead of scraping the HTML page.
- `ag_index.csv` — Attorney General charge sheet index. Use this to look up charge sheet URLs.

Use `read_file` to read these CSVs.

### Special case: charge sheet

The charge sheet `source_url` is a direct PDF link. Use `download_file` to download it to `raw_path`, then `convert_to_markdown` to convert it.

### Notes

- Always use the exact paths provided in the manifest.
- Use `tree` to verify the directory structure before and after downloading.
