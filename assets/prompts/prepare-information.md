## Prepare Information Instructions

You are responsible for downloading and preparing all source documents needed to draft a CIAA corruption case.

### What to do

1. Download the CIAA press release PDF for the case number from the CIAA website and save it to the global raw sources directory as `ciaa-press-release-{case_number}.pdf`.
2. Download any other relevant PDFs (charge sheets, court orders) if available.
3. Convert downloaded PDFs to Markdown using the `convert_to_markdown` tool and save them alongside the originals.

### Output

You must save the press release PDF to:
`{global_raw_sources_dir}/ciaa-press-release-{case_number}.pdf`

Use `run_shell_command` to move or copy files as needed. Use `fetch_url` to download documents from URLs.
