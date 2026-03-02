# PPT QA Pipeline — System Dependencies

For full presentation quality assurance (vision-based slide inspection, reflection loop), the following system packages are required:

## Linux (Ubuntu/Debian)

```bash
sudo apt-get update
sudo apt-get install -y libreoffice poppler-utils
```

## macOS

```bash
brew install libreoffice poppler
```

## Docker

Add to your Dockerfile:

```dockerfile
RUN apt-get update && apt-get install -y libreoffice poppler-utils && rm -rf /var/lib/apt/lists/*
```

## Verification

The system checks for `soffice` (LibreOffice) and `pdftoppm` (Poppler) at runtime. If missing, the QA step is skipped with a clear message; the presentation is still generated.

To verify manually:

```bash
soffice --version
pdftoppm -v
```

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Required for LLM planning, research synthesis, and vision QA |
| `TAVILY_API_KEY` | Optional — enables Tavily search for deeper research (get key at tavily.com) |
