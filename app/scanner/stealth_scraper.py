import asyncio
from typing import List, Dict, Optional
from playwright.async_api import async_playwright
from app.utils.logging_config import logger
from app.config import settings
from playwright_stealth import Stealth
from fake_useragent import UserAgent

class StealthScraper:
    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.running = False
        self.ua = UserAgent()

    async def start(self):
        """Starts the browser session."""
        self.running = True
        logger.info("Initializing Stealth Scraper (Playwright)...")
        # Ensure browsers are installed: playwright install chromium
        pass

    async def fetch_new_pairs(self) -> List[Dict]:
        """
        Scrapes DexScreener for new pairs.
        Returns a list of simplified pair dicts compatible with the pipeline.
        """
        pairs = []
        async with async_playwright() as p:
            # Evasion Args
            args = [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certifcate-errors",
                "--ignore-certifcate-errors-spki-list",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu"
            ]
            
            browser = await p.chromium.launch(
                headless=True, 
                args=args
            )
            
            # Randomize Context
            context = await browser.new_context(
                user_agent=self.ua.random,
                viewport={'width': 1920, 'height': 1080},
                locale="en-US",
                timezone_id="America/New_York",
                permissions=["geolocation"]
            )
            
            # Add init script to remove webdriver property
            await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = await context.new_page()
            
            # Apply Stealth
            await Stealth().apply_stealth_async(page)
            
            try:
                # 1. Navigate to New Pairs (Search filter or specific page)
                # "Most Recent" is tricky on DexScreener without filters
                # Let's try to search specifically for new pairs via a generic search
                # OR go to a specific chain page and sort by age?
                # DexScreener URL for New Pairs on Solana: https://dexscreener.com/solana?rankBy=pairAgeAsc
                # This is efficient!
                
                url = "https://dexscreener.com/solana?rankBy=pairAgeAsc" # Specific chain is better/faster?
                # User asked for "all new coins". Let's do Solana + ETH? Or generic.
                # Generic "New Pairs" doesn't have a single URL.
                # Let's use Solana for speed (Meme capital).
                
                logger.info(f"Scraping {url}...")
                # Use domcontentloaded for speed
                await page.goto(url, wait_until="domcontentloaded", timeout=45000) # Increased timeout for evasion
                
                # Wait for ANY link to a pair, not a specific table class which might change
                # DexScreener links usually look like /solana/address
                try:
                    await page.wait_for_selector("a[href*='/solana/']", timeout=45000)
                except Exception as wait_err:
                     logger.warning(f"Timeout waiting for selectors. Taking screenshot. Error: {wait_err}")
                     await page.screenshot(path="scraper_timeout_debug.png")
                     raise wait_err
                
                # 2. Extract Data
                # Get all links matching the pattern
                rows = await page.query_selector_all("a[href*='/solana/']")
                
                for row in rows[:20]: # Top 20 newest
                    # Extract Href -> /solana/address
                    href = await row.get_attribute("href")
                    if not href: continue
                    
                    # /solana/8w...
                    parts = href.split('/')
                    if len(parts) < 3: continue
                    
                    chain = parts[1]
                    pair_address = parts[2]
                    
                    # Fix: Scraper picks up DEX links like /solana/raydium or /solana/pumpswap
                    # Solana addresses are usually 32-44 chars. DEX names are short.
                    if len(pair_address) < 30:
                        continue
                    
                    # Extract Symbol/Name
                    # Text often looks like "WIF / SOL"
                    text = await row.inner_text()
                    lines = text.split('\n')
                    # This is loose. 
                    
                    # Construct a mimic of the API object
                    pair_obj = {
                        "chainId": chain,
                        "pairAddress": pair_address,
                        "baseToken": {
                            "address": "unknown", # We might need to visit page to get token addr? 
                            # Or infer? DEXScreener API is better for full data.
                            # SCRAPER ONLY GETS ADDRESSES. 
                            # WE THEN FECTH API DATA FOR THOSE ADDRESSES?
                            # YES! That avoids parsing complex DOM.
                            "symbol": "NewToken", 
                            "name": "New Token" 
                        },
                        "url": f"https://dexscreener.com{href}"
                    }
                    pairs.append(pair_obj)

            except Exception as e:
                logger.error("Scraper failed", error=str(e))
                # Take screenshot on error?
                # await page.screenshot(path="scraper_error.png")
            finally:
                await browser.close()
                
        return pairs

    async def scrape_twitter_profile(self, username: str) -> Optional[Dict]:
        """
        Directly scrapes Nitter using Playwright fallback.
        """
        data = None
        async with async_playwright() as p:
            # Firefox is often better for Nitter/Cloudflare
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            # Apply Stealth to bypass 403
            await Stealth().apply_stealth_async(page)
            
            # Using a stable Nitter instance (Poast is usually good, but failing 403)
            # Try nitter.net or nitter.privacydev.net
            url = f"https://nitter.net/{username}"
            
            try:
                logger.debug(f"Nitter Fallback: Visiting {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                
                # Check for 404/suspended
                if "Account not found" in await page.content():
                    return None

                # Extract Stats
                # CSS Selectors for Nitter: .profile-stat-num
                stats = await page.query_selector_all(".profile-stat-num")
                followers = 0
                tweets = 0
                
                if len(stats) >= 3:
                    # Usually: [Tweets, Following, Followers, Likes]
                    tweets_text = await stats[0].inner_text()
                    followers_text = await stats[2].inner_text()
                    
                    tweets = int(tweets_text.replace(',', '').replace(' ', ''))
                    followers = int(followers_text.replace(',', '').replace(' ', ''))
                
                # Extract Bio
                bio = ""
                bio_elem = await page.query_selector(".profile-bio")
                if bio_elem:
                    bio = await bio_elem.inner_text()
                    
                data = {
                    "stats": {"followers": followers, "tweets": tweets},
                    "bio": bio
                }
                
            except Exception as e:
                logger.warning(f"Nitter Direct Scrape failed for {username}: {e}")
            finally:
                await browser.close()
                
        return data

stealth_scraper = StealthScraper()
