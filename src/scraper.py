"""Bitovki24 scraper using Playwright."""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class House:
    """Simple house data model."""
    
    def __init__(
        self,
        title: str,
        url: str,
        price: Optional[float] = None,
        size: Optional[str] = None,
        description: Optional[str] = None,
        images: Optional[List[Path]] = None,
        phone: Optional[str] = None,
        email: Optional[str] = None,
        insulation: Optional[str] = None,
    ):
        self.title = title
        self.url = url
        self.price = price
        self.size = size
        self.description = description
        self.images = images or []
        self.phone = phone
        self.email = email
        self.insulation = insulation
        self.scraped_at = datetime.now()


class Bitovki24Scraper:
    """Scraper for bitovki24.ru."""
    
    BASE_URL = "https://bitovki24.ru"
    
    def __init__(self, images_dir: Path):
        """Initialize scraper.
        
        Args:
            images_dir: Directory to save downloaded images.
        """
        self.images_dir = images_dir
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.session = None
    
    async def initialize(self):
        """Initialize Playwright browser."""
        logger.info("Initializing browser...")
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.context = await self.browser.new_context()
        logger.info("Browser initialized")
    
    async def close(self):
        """Close browser and cleanup."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        logger.info("Browser closed")
    
    async def scrape(self) -> List[House]:
        """Scrape all houses from bitovki24.ru.
        
        Returns:
            List of House objects.
        """
        houses: List[House] = []
        page = await self.context.new_page()
        
        try:
            # Navigate to catalog
            logger.info(f"Opening {self.BASE_URL}/catalog/")
            await page.goto(f"{self.BASE_URL}/catalog/", wait_until="networkidle", timeout=60000)
            
            # Get all product links
            links = await page.locator('a.product-link, a[href*="/products/"]').all()
            logger.info(f"Found {len(links)} product links")
            
            for idx, link in enumerate(links[:20]):  # Limit to first 20 for MVP
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    product_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                    logger.info(f"[{idx + 1}/{min(20, len(links))}] Scraping {product_url}")
                    
                    house = await self._scrape_product(page, product_url)
                    if house:
                        houses.append(house)
                        logger.info(f"  ✓ {house.title} ({house.price} RUB)")
                    
                except Exception as e:
                    logger.warning(f"Error scraping product {idx}: {e}")
                    continue
        
        finally:
            await page.close()
        
        return houses
    
    async def _scrape_product(self, page: Page, url: str) -> Optional[House]:
        """Scrape individual product page.
        
        Args:
            page: Playwright page object.
            url: Product URL.
            
        Returns:
            House object or None.
        """
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title_elem = soup.find('h1') or soup.find('h2', class_='product-title')
            if not title_elem:
                logger.warning("Could not find title")
                return None
            title = title_elem.get_text(strip=True)
            
            # Extract price
            price = None
            price_elem = soup.find('span', class_='price') or soup.find('div', class_='price')
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                import re
                match = re.search(r'\d+\s*\d*', price_text.replace(' ', ''))
                if match:
                    try:
                        price = float(match.group().replace(' ', ''))
                    except:
                        pass
            
            # Extract size
            size = None
            size_elem = soup.find('span', class_='size') or soup.find('div', class_='dimensions')
            if size_elem:
                size = size_elem.get_text(strip=True)
            
            # Extract description
            description = None
            desc_elem = soup.find('div', class_='description') or soup.find('p', class_='product-description')
            if desc_elem:
                description = desc_elem.get_text(strip=True)[:500]  # First 500 chars
            
            # Extract contact info
            phone = None
            email = None
            phone_elem = soup.find('a', href=lambda x: x and 'tel:' in x if x else False)
            if phone_elem:
                phone = phone_elem.get_text(strip=True)
            email_elem = soup.find('a', href=lambda x: x and 'mailto:' in x if x else False)
            if email_elem:
                email = email_elem.get_text(strip=True)
            
            # Extract insulation info
            insulation = None
            insul_elem = soup.find('span', class_='insulation')
            if insul_elem:
                insulation = insul_elem.get_text(strip=True)
            
            # Download images
            image_paths = await self._download_images(page, soup)
            
            return House(
                title=title,
                url=url,
                price=price,
                size=size,
                description=description,
                images=image_paths,
                phone=phone,
                email=email,
                insulation=insulation,
            )
        
        except Exception as e:
            logger.error(f"Error scraping product: {e}")
            return None
    
    async def _download_images(self, page: Page, soup: BeautifulSoup) -> List[Path]:
        """Download all product images.
        
        Args:
            page: Playwright page object.
            soup: BeautifulSoup object.
            
        Returns:
            List of local image paths.
        """
        image_paths: List[Path] = []
        
        # Find all images
        img_elements = soup.find_all('img')
        
        for idx, img in enumerate(img_elements[:5]):  # Limit to 5 images per product
            try:
                img_url = img.get('src') or img.get('data-src')
                if not img_url:
                    continue
                
                # Make absolute URL
                if img_url.startswith('/'):
                    img_url = f"{self.BASE_URL}{img_url}"
                elif not img_url.startswith('http'):
                    continue
                
                # Download
                local_path = await self._download_image(page, img_url)
                if local_path:
                    image_paths.append(local_path)
            
            except Exception as e:
                logger.debug(f"Error downloading image {idx}: {e}")
                continue
        
        return image_paths
    
    async def _download_image(self, page: Page, url: str) -> Optional[Path]:
        """Download single image.
        
        Args:
            page: Playwright page object.
            url: Image URL.
            
        Returns:
            Local file path or None.
        """
        try:
            # Generate filename
            filename = hashlib.md5(url.encode()).hexdigest() + Path(url).suffix
            filepath = self.images_dir / filename
            
            # Skip if already downloaded
            if filepath.exists():
                return filepath
            
            # Download
            response = await page.request.get(url, timeout=30000)
            if response.ok:
                with open(filepath, 'wb') as f:
                    f.write(await response.body())
                logger.debug(f"Downloaded image: {filename}")
                return filepath
            else:
                logger.debug(f"Failed to download image (status {response.status})")
                return None
        
        except Exception as e:
            logger.debug(f"Error downloading image: {e}")
            return None
