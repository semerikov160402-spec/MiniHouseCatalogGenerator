"""Main entry point for the Mini House Catalog Generator."""

import asyncio
import logging
from pathlib import Path

from scraper import Bitovki24Scraper
from exporters import PDFExporter, DocxExporter, ExcelExporter

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Paths
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
IMAGES_DIR = DATA_DIR / "images"
OUTPUT_DIR = DATA_DIR / "output"

# Create directories
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


async def main():
    """Main function."""
    logger.info("Starting Mini House Catalog Generator")
    logger.info(f"Images will be saved to: {IMAGES_DIR}")
    logger.info(f"Output files will be saved to: {OUTPUT_DIR}")
    
    # Scrape
    logger.info("\n=== SCRAPING ===")
    scraper = Bitovki24Scraper(images_dir=IMAGES_DIR)
    await scraper.initialize()
    
    try:
        houses = await scraper.scrape()
        logger.info(f"Successfully scraped {len(houses)} houses")
    finally:
        await scraper.close()
    
    if not houses:
        logger.warning("No houses scraped. Exiting.")
        return
    
    # Export
    logger.info("\n=== EXPORTING ===")
    
    # PDF
    logger.info("Generating PDF catalog...")
    pdf_exporter = PDFExporter()
    pdf_exporter.export(houses, OUTPUT_DIR / "catalog.pdf")
    logger.info(f"✓ PDF saved to {OUTPUT_DIR / 'catalog.pdf'}")
    
    # DOCX
    logger.info("Generating DOCX catalog...")
    docx_exporter = DocxExporter()
    docx_exporter.export(houses, OUTPUT_DIR / "catalog.docx")
    logger.info(f"✓ DOCX saved to {OUTPUT_DIR / 'catalog.docx'}")
    
    # XLSX
    logger.info("Generating XLSX catalog...")
    excel_exporter = ExcelExporter()
    excel_exporter.export(houses, OUTPUT_DIR / "catalog.xlsx")
    logger.info(f"✓ XLSX saved to {OUTPUT_DIR / 'catalog.xlsx'}")
    
    logger.info("\n=== DONE ===")
    logger.info(f"All catalogs generated successfully in {OUTPUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
