# Jawaf Span

AgentSpan-based CIAA caseworker service for Jawafdehi.

## Development

Install dependencies:

```bash
cd services/jawafdehi-agentspan
poetry install
```

Run the CLI:

```bash
poetry run jawaf run 081-CR-0046
```

Run tests:

```bash
poetry run pytest
```

## Required Environment Variables

- `OPENAI_API_KEY`
- `JAWAFDEHI_API_TOKEN`

## Optional Environment Variables

- `JAWAFDEHI_API_BASE_URL`
- `AGENTSPAN_SERVER_URL`
- `AGENTSPAN_AUTH_KEY`
- `AGENTSPAN_AUTH_SECRET`
- `BRAVE_SEARCH_API_KEY`
- `NEWS_ARTICLE_LIMIT`
- `LLM_MODEL`
- `OPENAI_BASE_URL`

