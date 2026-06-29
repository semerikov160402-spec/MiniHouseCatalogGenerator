"""Bitovki24 scraper using Playwright with improved selectors."""

import asyncio
import logging
import hashlib
import json
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
        specifications: Optional[dict] = None,
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
        self.specifications = specifications or {}
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
            
            # Wait for content to load
            try:
                await page.wait_for_selector('a', timeout=10000)
            except:
                logger.warning("Timeout waiting for links")
            
            # Get page content for analysis
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Log available selectors for debugging
            logger.info("\n=== PAGE STRUCTURE ANALYSIS ===")
            logger.info(f"Page title: {soup.title.string if soup.title else 'No title'}")
            logger.info(f"Total links on page: {len(soup.find_all('a'))}")
            
            # Analyze product card structures
            logger.info("\n=== LOOKING FOR PRODUCT CARDS ===")
            
            # Try multiple selectors to find product containers
            product_selectors = [
                ('div[class*="product"]', 'div with product class'),
                ('div[class*="item"]', 'div with item class'),
                ('article', 'article elements'),
                ('div[data-product]', 'div with data-product'),
                ('.product-item', 'product-item class'),
                ('.catalog-item', 'catalog-item class'),
            ]
            
            for selector, desc in product_selectors:
                elements = soup.select(selector)
                if elements:
                    logger.info(f"Found {len(elements)} elements matching '{desc}' ({selector})")
            
            # Get all potential product links
            all_links = soup.find_all('a', href=True)
            logger.info(f"\nTotal <a> tags: {len(all_links)}")
            
            # Filter product links
            product_links = []
            for link in all_links:
                href = link.get('href', '')
                # Look for product URLs (typical patterns)
                if any(pattern in href.lower() for pattern in ['/product', '/item', '/catalog/', '/byt']):
                    product_links.append(href)
            
            logger.info(f"Filtered to {len(product_links)} potential product links")
            
            if not product_links:
                logger.warning("No product links found. Trying to extract from data attributes...")
                # Try to find links in data attributes
                for link in all_links[:20]:
                    logger.debug(f"  Sample link: {link.get('href')}")
            
            logger.info("\n=== SCRAPING PRODUCTS ===")
            
            # Scrape each product
            for idx, href in enumerate(product_links[:15]):  # Limit to first 15
                try:
                    product_url = href if href.startswith('http') else f"{self.BASE_URL}{href}"
                    
                    logger.info(f"\n[{idx + 1}] Attempting to scrape: {product_url[:80]}...")
                    
                    house = await self._scrape_product(page, product_url)
                    if house:
                        houses.append(house)
                        logger.info(f"   ✓ SUCCESS: {house.title}")
                        logger.info(f"     - Price: {house.price} RUB")
                        logger.info(f"     - Size: {house.size}")
                        logger.info(f"     - Images: {len(house.images)}")
                    else:
                        logger.info(f"   ✗ Failed to extract data")
                    
                except Exception as e:
                    logger.warning(f"   ✗ Error: {str(e)[:100]}")
                    continue
        
        except Exception as e:
            logger.error(f"Error in scrape method: {e}")
        
        finally:
            await page.close()
        
        logger.info(f"\n=== SCRAPING COMPLETE ===")
        logger.info(f"Successfully scraped {len(houses)} houses")
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
            await asyncio.sleep(0.5)  # Give page time to render
            
            html = await page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # Log page structure for debugging
            logger.debug(f"  Page title tag: {soup.title.string if soup.title else 'N/A'}")
            
            # Extract title - try multiple selectors
            title = None
            title_selectors = [
                soup.find('h1'),
                soup.find('h2'),
                soup.find('div', class_=re.compile('title', re.I)),
                soup.find('span', class_=re.compile('title', re.I)),
            ]
            
            for elem in title_selectors:
                if elem:
                    title = elem.get_text(strip=True)
                    if title and len(title) > 3:
                        break
            
            if not title or len(title) < 3:
                logger.debug("  Could not find valid title")
                return None
            
            logger.debug(f"  Title: {title[:50]}...")
            
            # Extract price - try multiple selectors
            price = None
            price_patterns = [
                soup.find(string=re.compile(r'\d+\s*(?:руб|RUB|р\.)', re.I)),
                soup.find('span', class_=re.compile('price|стоимость|цена', re.I)),
                soup.find('div', class_=re.compile('price|стоимость|цена', re.I)),
            ]
            
            for elem in price_patterns:
                if elem:
                    price_text = elem.get_text(strip=True) if hasattr(elem, 'get_text') else str(elem)
                    # Extract numbers
                    price_match = re.search(r'(\d+\s*)*\d+', price_text.replace(' ', '').replace('\xa0', ''))
                    if price_match:
                        try:
                            price = float(price_match.group().replace(' ', ''))
                            logger.debug(f"  Price: {price}")
                            break
                        except:
                            pass
            
            # Extract size/dimensions
            size = None
            size_patterns = [
                soup.find(string=re.compile(r'\d+x\d+|размер|габариты|длина|ширина', re.I)),
                soup.find('span', class_=re.compile('size|dimension|размер', re.I)),
                soup.find('div', class_=re.compile('size|dimension|размер', re.I)),
            ]
            
            for elem in size_patterns:
                if elem:
                    size = elem.get_text(strip=True) if hasattr(elem, 'get_text') else str(elem)
                    if size:
                        logger.debug(f"  Size: {size[:50]}")
                        break
            
            # Extract description
            description = None
            desc_elem = soup.find('div', class_=re.compile('description|desc|описание', re.I))
            if not desc_elem:
                desc_elem = soup.find('p', class_=re.compile('description|desc|описание', re.I))
            if desc_elem:
                description = desc_elem.get_text(strip=True)[:500]
                logger.debug(f"  Description: {description[:30]}...")
            
            # Extract contact info
            phone = None
            email = None
            
            # Try tel: links
            tel_link = soup.find('a', href=re.compile(r'^tel:', re.I))
            if tel_link:
                phone = tel_link.get_text(strip=True)
                logger.debug(f"  Phone: {phone}")
            
            # Try mailto: links
            mailto_link = soup.find('a', href=re.compile(r'^mailto:', re.I))
            if mailto_link:
                email = mailto_link.get_text(strip=True)
                logger.debug(f"  Email: {email}")
            
            # Extract specifications
            specifications = {}
            spec_containers = soup.find_all('div', class_=re.compile('spec|feature|параметр', re.I))
            if spec_containers:
                logger.debug(f"  Found {len(spec_containers)} specification elements")
            
            # Extract insulation info
            insulation = None
            insul_elem = soup.find(string=re.compile('изоляция|утепл|теплоизо', re.I))
            if insul_elem:
                insulation = insul_elem.get_text(strip=True)[:100]
                logger.debug(f"  Insulation: {insulation}")
            
            # Download images
            image_paths = await self._download_images(page, soup)
            logger.debug(f"  Downloaded {len(image_paths)} images")
            
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
                specifications=specifications,
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
            logger.debug(f"  Found {len(img_elements)} img elements")
            
            for idx, img in enumerate(img_elements[:8]):
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
                    logger.debug(f"  Downloaded image: {filename}")
                    return filepath
            except Exception as e:
                logger.debug(f"Failed via page.request: {e}")
                # Fallback to requests library
                try:
                    import requests
                    resp = requests.get(url, timeout=10, verify=False)
                    if resp.status_code == 200:
                        with open(filepath, 'wb') as f:
                            f.write(resp.content)
                        logger.debug(f"Downloaded (fallback): {filename}")
                        return filepath
                except Exception as e2:
                    logger.debug(f"Fallback download also failed: {e2}")
        
        except Exception as e:
            logger.debug(f"Error downloading image: {e}")
        
        return None
