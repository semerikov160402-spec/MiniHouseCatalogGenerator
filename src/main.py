"""Main entry point for the Mini House Catalog Generator."""

import sys
import asyncio
import logging
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from scraper import Bitovki24Scraper
from exporters import PDFExporter, DocxExporter, ExcelExporter

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
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
    try:
        logger.info("="*80)
        logger.info("Mini House Catalog Generator - MVP Test")
        logger.info("="*80)
        logger.info(f"Images directory: {IMAGES_DIR}")
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info("")
        
        # Scrape
        logger.info("PHASE 1: SCRAPING")
        logger.info("-"*80)
        scraper = Bitovki24Scraper(images_dir=IMAGES_DIR)
        await scraper.initialize()
        
        try:
            houses = await scraper.scrape()
            logger.info(f"\n✓ Successfully scraped {len(houses)} houses\n")
        finally:
            await scraper.close()
        
        if not houses:
            logger.error("No houses scraped. Cannot generate catalogs.")
            return False
        
        # Display scraped data
        logger.info("Scraped Products:")
        logger.info("-"*80)
        for idx, house in enumerate(houses, 1):
            logger.info(f"{idx}. {house.title}")
            logger.info(f"   Price: {house.price} RUB")
            logger.info(f"   Size: {house.size}")
            logger.info(f"   Images: {len(house.images)}")
            logger.info(f"   URL: {house.url}")
            logger.info("")
        
        # Export
        logger.info("\nPHASE 2: EXPORTING")
        logger.info("-"*80)
        
        # PDF
        logger.info("Generating PDF catalog...")
        try:
            pdf_exporter = PDFExporter()
            pdf_path = OUTPUT_DIR / "catalog.pdf"
            pdf_exporter.export(houses, pdf_path)
            if pdf_path.exists():
                logger.info(f"✓ PDF saved: {pdf_path} ({pdf_path.stat().st_size / 1024:.1f} KB)")
            else:
                logger.error("✗ PDF file not created")
        except Exception as e:
            logger.error(f"✗ Error generating PDF: {e}")
            import traceback
            traceback.print_exc()
        
        # DOCX
        logger.info("Generating DOCX catalog...")
        try:
            docx_exporter = DocxExporter()
            docx_path = OUTPUT_DIR / "catalog.docx"
            docx_exporter.export(houses, docx_path)
            if docx_path.exists():
                logger.info(f"✓ DOCX saved: {docx_path} ({docx_path.stat().st_size / 1024:.1f} KB)")
            else:
                logger.error("✗ DOCX file not created")
        except Exception as e:
            logger.error(f"✗ Error generating DOCX: {e}")
            import traceback
            traceback.print_exc()
        
        # XLSX
        logger.info("Generating XLSX catalog...")
        try:
            excel_exporter = ExcelExporter()
            xlsx_path = OUTPUT_DIR / "catalog.xlsx"
            excel_exporter.export(houses, xlsx_path)
            if xlsx_path.exists():
                logger.info(f"✓ XLSX saved: {xlsx_path} ({xlsx_path.stat().st_size / 1024:.1f} KB)")
            else:
                logger.error("✗ XLSX file not created")
        except Exception as e:
            logger.error(f"✗ Error generating XLSX: {e}")
            import traceback
            traceback.print_exc()
        
        # Summary
        logger.info("\nPHASE 3: VERIFICATION")
        logger.info("-"*80)
        logger.info(f"Images downloaded: {len(list(IMAGES_DIR.glob('*')))} files")
        logger.info(f"Output files:")
        for output_file in OUTPUT_DIR.glob('*'):
            logger.info(f"  - {output_file.name} ({output_file.stat().st_size / 1024:.1f} KB)")
        
        logger.info("\n" + "="*80)
        logger.info("✓ MVP TEST COMPLETED SUCCESSFULLY")
        logger.info("="*80)
        return True
        
    except Exception as e:
        logger.error(f"\n✗ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
