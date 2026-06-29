"""Bitovki24 scraper using Playwright."""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup
import re

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
        self.images_dir = Path(images_dir)
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.playwright = None
    
    async def initialize(self):
        """Initialize Playwright browser."""
        logger.info("Initializing browser...")
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True)
            self.context = await self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            logger.info("✓ Browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize browser: {e}")
            raise
    
    async def close(self):
        """Close browser and cleanup."""
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("✓ Browser closed")
        except Exception as e:
            logger.warning(f"Error closing browser: {e}")
    
    async def scrape(self) -> List[House]:
        """Scrape all houses from bitovki24.ru.
        
        Returns:
            List of House objects.
        """
        houses: List[House] = []
        page = await self.context.new_page()
        
        try:
            # Navigate to catalog
            catalog_url = f"{self.BASE_URL}/catalog/"
            logger.info(f"Opening {catalog_url}")
            
            try:
                await page.goto(catalog_url, wait_until="domcontentloaded", timeout=60000)
            except Exception as e:
                logger.warning(f"Navigation timeout, continuing anyway: {e}")
            
            # Wait for products to load
            try:
                await page.wait_for_selector('a[href*="/products/"], .product-link', timeout=10000)
            except:
                logger.warning("Product links not found, trying alternative selectors")
            
            # Get all product links
            links = await page.locator('a[href*="/product"], a.product-link').all()
            logger.info(f"Found {len(links)} product links")
            
            if not links:
                logger.warning("No product links found. The website structure may have changed.")
                # Try getting all links and filtering
                all_links = await page.locator('a').all()
                logger.info(f"Found {len(all_links)} total links on page")
            
            for idx, link in enumerate(links[:10]):  # Limit to first 10 for MVP test
                try:
                    href = await link.get_attribute('href')
                    if not href:
                        continue
                    
                    product_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                    
                    # Skip if not a product URL
                    if '/product' not in product_url.lower():
                        continue
                    
                    logger.info(f"[{idx + 1}] Scraping: {product_url[:80]}...")
                    
                    house = await self._scrape_product(page, product_url)
                    if house:
                        houses.append(house)
                        logger.info(f"   ✓ {house.title}")
                    
                except Exception as e:
                    logger.debug(f"Error scraping product {idx}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in scrape method: {e}")
        
        finally:
            await page.close()
        
        logger.info(f"\nScraped {len(houses)} houses total")
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
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(1)  # Give page time to render
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Extract title
            title_elem = soup.find('h1') or soup.find('h2')
            if not title_elem:
                logger.debug("Could not find title")
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None
            
            # Extract price
            price = None
            # Try various price selectors
            price_elem = soup.find('span', class_=re.compile('price', re.I))
            if not price_elem:
                price_elem = soup.find('div', class_=re.compile('price', re.I))
            if not price_elem:
                price_elem = soup.find('div', string=re.compile(r'\d+.*РУБ|руб', re.I))
            
            if price_elem:
                price_text = price_elem.get_text(strip=True)
                # Extract numbers
                price_match = re.search(r'(\d+\s*)*\d+', price_text.replace(' ', '').replace('РУБ', '').replace('руб', ''))
                if price_match:
                    try:
                        price_str = price_match.group().replace(' ', '')
                        price = float(price_str)
                    except:
                        pass
            
            # Extract size
            size = None
            size_elem = soup.find('span', class_=re.compile('size|dimension', re.I))
            if not size_elem:
                size_elem = soup.find('div', class_=re.compile('size|dimension', re.I))
            if size_elem:
                size = size_elem.get_text(strip=True)
            
            # Extract description
            description = None
            desc_elem = soup.find('div', class_=re.compile('description|desc', re.I))
            if not desc_elem:
                desc_elem = soup.find('p', class_=re.compile('description|desc', re.I))
            if desc_elem:
                description = desc_elem.get_text(strip=True)[:500]
            
            # Extract contact info
            phone = None
            email = None
            
            # Try to find phone
            phone_patterns = [
                soup.find('a', href=re.compile(r'^tel:', re.I)),
                soup.find('span', string=re.compile(r'\+?\d{1,3}.*\d{4,}')),
            ]
            for elem in phone_patterns:
                if elem:
                    phone = elem.get_text(strip=True)
                    break
            
            # Try to find email
            email_patterns = [
                soup.find('a', href=re.compile(r'^mailto:', re.I)),
                soup.find('span', string=re.compile(r'[\w\.-]+@[\w\.-]+\.\w+'))
            ]
            for elem in email_patterns:
                if elem:
                    email = elem.get_text(strip=True)
                    break
            
            # Extract insulation info
            insulation = None
            insul_elem = soup.find('span', class_=re.compile('insul', re.I))
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
            logger.debug(f"Error scraping product: {e}")
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
        
        try:
            # Find all images
            img_elements = soup.find_all('img')
            logger.debug(f"Found {len(img_elements)} img elements")
            
            for idx, img in enumerate(img_elements[:8]):  # Limit to 8 images per product
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
        
        except Exception as e:
            logger.debug(f"Error in _download_images: {e}")
        
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
            filename = hashlib.md5(url.encode()).hexdigest()
            ext = Path(url).suffix or '.jpg'
            filename = filename + ext
            filepath = self.images_dir / filename
            
            # Skip if already downloaded
            if filepath.exists():
                return filepath
            
            # Download
            try:
                response = await page.request.get(url, timeout=30000)
                if response.ok:
                    with open(filepath, 'wb') as f:
                        f.write(await response.body())
                    logger.debug(f"Downloaded: {filename}")
                    return filepath
            except Exception as e:
                logger.debug(f"Failed to download via page.request: {e}")
                # Fallback to requests library
                try:
                    import requests
                    resp = requests.get(url, timeout=10)
                    if resp.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(resp.content)
                        logger.debug(f"Downloaded (fallback): {filename}")
                        return filepath
                except Exception as e2:
                    logger.debug(f"Fallback download also failed: {e2}")
        
        except Exception as e:
            logger.debug(f"Error downloading image {url}: {e}")
        
        return None
