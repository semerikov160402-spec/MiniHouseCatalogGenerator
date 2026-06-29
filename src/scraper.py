"""Bitovki24 scraper using Playwright with MVP fallback parser."""

import asyncio
import logging
import hashlib
from pathlib import Path
from typing import List, Optional, Set
from datetime import datetime
from urllib.parse import urljoin

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
        images: Optional[List[Path]] = None,
    ):
        self.title = title
        self.url = url
        self.price = price
        self.size = size
        self.images = images or []
        self.scraped_at = datetime.now()


class Bitovki24Scraper:
    """Scraper for bitovki24.ru using fallback extraction."""
    
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
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
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
    
    def _filter_product_urls(self, urls: List[str]) -> List[str]:
        """Filter URLs that look like product pages.
        
        Args:
            urls: List of URLs from catalog page.
            
        Returns:
            Filtered list of product-like URLs.
        """
        filtered = []
        
        # Product URL patterns
        product_patterns = [
            r'/product/',
            r'/item/',
            r'/tovar',
            r'/bitovka',
            r'/byt',
        ]
        
        # Exclude patterns
        exclude_patterns = [
            r'#',
            r'javascript:',
            r'/page/',
            r'/category/',
            r'/search',
            r'/filter',
        ]
        
        for url in urls:
            url_lower = url.lower()
            
            # Skip external URLs
            if url.startswith('http') and 'bitovki24.ru' not in url_lower:
                continue
            
            # Check exclude patterns
            if any(re.search(pattern, url_lower) for pattern in exclude_patterns):
                continue
            
            # Check if matches product patterns
            if any(re.search(pattern, url_lower) for pattern in product_patterns):
                filtered.append(url)
                continue
            
            # Fallback: if URL is deep path (3+ segments) and not excluded, treat as potential product
            path = url.replace(self.BASE_URL, '').strip('/')
            segments = [s for s in path.split('/') if s]
            if len(segments) >= 2 and not any(keyword in url_lower for keyword in ['catalog', 'page', 'category']):
                filtered.append(url)
        
        return filtered
    
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
            
            # Wait for links
            try:
                await page.wait_for_selector('a', timeout=10000)
            except:
                logger.warning("Timeout waiting for links")
            
            # Extract all links
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            all_links = soup.find_all('a', href=True)
            urls = [urljoin(self.BASE_URL, link['href']) for link in all_links]
            logger.info(f"Found {len(urls)} links on catalog page")
            
            # Filter product URLs
            product_urls = self._filter_product_urls(urls)
            logger.info(f"Filtered to {len(product_urls)} product-like URLs")
            
            # Remove duplicates while preserving order
            seen: Set[str] = set()
            unique_urls = []
            for url in product_urls:
                if url not in seen:
                    seen.add(url)
                    unique_urls.append(url)
            
            logger.info(f"\n=== SCRAPING {len(unique_urls)} PRODUCTS ===")
            
            # Scrape each product
            for idx, url in enumerate(unique_urls[:50], 1):  # Limit to 50 for safety
                try:
                    logger.info(f"\n[{idx}] {url}")
                    house = await self._scrape_product_page(page, url)
                    
                    if house:
                        houses.append(house)
                        logger.info(f"    ✓ {house.title}")
                        logger.info(f"      Price: {house.price} RUB" if house.price else "      Price: N/A")
                        logger.info(f"      Size: {house.size}" if house.size else "      Size: N/A")
                        logger.info(f"      Images: {len(house.images)}")
                    else:
                        logger.info(f"    ✗ Failed to extract data")
                
                except Exception as e:
                    logger.warning(f"    ✗ Error: {str(e)[:80]}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in scrape: {e}")
        
        finally:
            await page.close()
        
        logger.info(f"\n=== SCRAPING COMPLETE ===")
        logger.info(f"✓ Successfully scraped {len(houses)} houses")
        return houses
    
    async def _scrape_product_page(self, page: Page, url: str) -> Optional[House]:
        """Scrape individual product page using fallback extraction.
        
        Args:
            page: Playwright page object.
            url: Product URL.
            
        Returns:
            House object or None.
        """
        try:
            # Navigate to product page
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(0.3)  # Brief pause for rendering
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # 1. Extract title from h1
            title_elem = soup.find('h1')
            if not title_elem:
                logger.debug("    No h1 found")
                return None
            
            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                logger.debug(f"    Invalid title: {title}")
                return None
            
            logger.debug(f"    Title: {title[:60]}")
            
            # 2. Extract price using regex for ₽ / руб
            price = None
            html_text = str(soup)
            
            # Search for prices with рублей, руб, ₽
            price_patterns = [
                r'(\d+\s*(?:₽|руб|RUB))',
                r'(\d+\s*(?:руб|рублей))',
                r'price["\']?\s*[:"]\s*(\d+)',
                r'(\d{4,})[^\d]',  # 4+ digit numbers likely prices
            ]
            
            for pattern in price_patterns:
                matches = re.findall(pattern, html_text, re.IGNORECASE)
                if matches:
                    for match in matches:
                        # Extract just the number part
                        numbers = re.findall(r'\d+', str(match))
                        if numbers:
                            price_candidate = float(numbers[0])
                            # Reasonable price range check
                            if 5000 <= price_candidate <= 5000000:
                                price = price_candidate
                                break
                if price:
                    break
            
            if price:
                logger.debug(f"    Price: {price} RUB")
            
            # 3. Extract dimensions using regex (6×4, 6x4, 5×4.6, 6*6)
            size = None
            size_pattern = r'([3-9]|\d{2})\s*[×x*]\s*([3-9]|\d{2})(?:\.\d+)?'
            size_matches = re.findall(size_pattern, html_text)
            if size_matches:
                # Take first match
                w, h = size_matches[0]
                size = f"{w}×{h}"
                logger.debug(f"    Size: {size}")
            
            # 4. Collect all img src URLs
            img_urls = []
            for img in soup.find_all('img'):
                src = img.get('src') or img.get('data-src')
                if src:
                    abs_url = urljoin(url, src)
                    img_urls.append(abs_url)
            
            logger.debug(f"    Found {len(img_urls)} images")
            
            # 5. Download 3-5 largest images
            downloaded_images = await self._download_images(page, img_urls[:10])
            
            if not title:
                return None
            
            return House(
                title=title,
                url=url,
                price=price,
                size=size,
                images=downloaded_images,
            )
        
        except asyncio.TimeoutError:
            logger.debug(f"    Timeout loading page")
            return None
        except Exception as e:
            logger.debug(f"    Exception: {str(e)[:60]}")
            return None
    
    async def _download_images(self, page: Page, img_urls: List[str]) -> List[Path]:
        """Download images from URLs.
        
        Args:
            page: Playwright page object.
            img_urls: List of image URLs.
            
        Returns:
            List of local image paths.
        """
        downloaded: List[Path] = []
        
        for idx, url in enumerate(img_urls[:5]):  # Max 5 images
            try:
                path = await self._download_single_image(page, url)
                if path:
                    downloaded.append(path)
            except Exception as e:
                logger.debug(f"    Could not download image {idx+1}: {str(e)[:40]}")
                continue
        
        return downloaded
    
    async def _download_single_image(self, page: Page, url: str) -> Optional[Path]:
        """Download single image.
        
        Args:
            page: Playwright page object.
            url: Image URL.
            
        Returns:
            Local file path or None.
        """
        try:
            # Skip data URLs and invalid URLs
            if not url or url.startswith('data:'):
                return None
            
            # Generate filename from URL hash
            filename = hashlib.md5(url.encode()).hexdigest()
            ext = Path(url.split('?')[0]).suffix or '.jpg'
            filepath = self.images_dir / (filename + ext)
            
            # Skip if already exists
            if filepath.exists():
                return filepath
            
            # Download using Playwright
            try:
                response = await page.request.get(url, timeout=15000)
                if response.ok:
                    with open(filepath, 'wb') as f:
                        f.write(await response.body())
                    logger.debug(f"    Downloaded: {filename + ext}")
                    return filepath
            except Exception as e:
                logger.debug(f"    Playwright download failed: {str(e)[:40]}")
                # Try with requests as fallback
                try:
                    import requests
                    resp = requests.get(url, timeout=10, verify=False)
                    if resp.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(resp.content)
                        logger.debug(f"    Downloaded (requests): {filename + ext}")
                        return filepath
                except:
                    pass
        
        except Exception as e:
            logger.debug(f"    Download error: {str(e)[:40]}")
        
        return None
