# Mini House Catalog Generator

A simple tool to scrape mini house data from bitovki24.ru and generate catalogs in PDF, DOCX, and XLSX formats.

## Installation

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

## Usage

```bash
python src/main.py
```

This will:
1. Scrape houses from bitovki24.ru
2. Download all images locally
3. Generate PDF, DOCX, and XLSX catalogs in `data/output/`

## Output

- `data/output/catalog.pdf`
- `data/output/catalog.docx`
- `data/output/catalog.xlsx`
- `data/images/` - Downloaded product images
