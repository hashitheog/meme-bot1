import asyncio
import random
from typing import Dict, Optional
from app.utils.logging_config import logger
try:
    from ntscraper import Nitter
except ImportError:
    Nitter = None

class SocialAnalyzer:
    """
    Fetches real stats from Twitter using Nitter (Stealth Scraper).
    """
    def __init__(self):
        self.scraper = Nitter(log_level=1, skip_instance_check=False) if Nitter else None
        # Cache for working instances or results could go here
    
    async def analyze(self, pair_data: Dict) -> Dict:
        """
        Extracts social links and scrapes Twitter profile.
        """
        socials = pair_data.get("info", {}).get("socials", [])
        twitter_url = next((s['url'] for s in socials if s['type'] == 'twitter'), None)
        telegram_url = next((s['url'] for s in socials if s['type'] == 'telegram'), None)

        start_input = {
            "twitter": {"exists": False, "mentions_last_hour": 0, "account_age_days": 0},
            "telegram": {"exists": bool(telegram_url), "members": 0}, # TG scraping is harder without auth
            "website_text": ""
        }
        
        if not twitter_url:
            return start_input

        # Extract username
        # Filters: https://twitter.com/Username -> Username
        # https://x.com/Username?s=21 -> Username
        try:
            # Handle standard handle: https://twitter.com/username
            # Handle status: https://twitter.com/username/status/123
            # Handle query params: https://x.com/username?s=20
            
            clean_url = twitter_url.split("?")[0]
            parts = clean_url.split("/")
            
            # Remove empty strings from trailing slashes
            parts = [p for p in parts if p]
            
            if "status" in parts:
                # /username/status/id -> Get index of 'status' and go back 1
                idx = parts.index("status")
                if idx > 0:
                    username = parts[idx - 1]
                else:
                    return start_input
            else:
                # Assume last part is username
                username = parts[-1]
            
            # Clean potential garbage
            if username in ["twitter.com", "x.com", "www.twitter.com"]:
                 return start_input

        except Exception as e:
            logger.warning(f"Failed to parse username from {twitter_url}: {e}")
            return start_input

        if self.scraper:
            # Run blocking scrape in thread
            logger.info(f"Scraping Twitter for {username} via Nitter...")
            try:
                profile_data = await asyncio.to_thread(self._scrape_profile, username)
                if profile_data:
                    start_input["twitter"]["exists"] = True
                    start_input["twitter"]["followers"] = profile_data.get("stats", {}).get("followers", 0)
                    start_input["twitter"]["tweets"] = profile_data.get("stats", {}).get("tweets", 0)
                    # Infer age or mentions? 
                    # Nitter might not give precise account age easily without deep parsing, 
                    # but we can get 'joined' date if available in bio sometimes or just trust existence.
                    # We can also scrape recent tweets to count "mentions" (activity).
                    
                    # Let's try to get bio as website text context
                    start_input["website_text"] = profile_data.get("bio", "")
            except Exception as e:
                # Nitter lib failed. Try our custom Playwright Fallback.
                logger.warning(f"ntscraper failed for {username} ({e}), trying Playwright Fallback...")
                try:
                    from app.scanner.stealth_scraper import stealth_scraper
                    profile_data = await stealth_scraper.scrape_twitter_profile(username)
                    
                    if profile_data:
                        start_input["twitter"]["exists"] = True
                        start_input["twitter"]["followers"] = profile_data.get("stats", {}).get("followers", 0)
                        start_input["twitter"]["tweets"] = profile_data.get("stats", {}).get("tweets", 0)
                        start_input["website_text"] = profile_data.get("bio", "")
                        logger.info(f"Playwright Scrape Success: {username} ({start_input['twitter']['followers']} followers)")
                except Exception as ex:
                    logger.warning(f"Social All-Fail for {username}: {ex}")
        
        return start_input

    def _scrape_profile(self, username: str) -> Optional[Dict]:
        """
        Blocking call to Nitter scraper.
        """
        try:
            # get_profile returns dict with 'stats', 'bio', etc.
            profile = self.scraper.get_profile_info(username)
            return profile
        except Exception as e:
            # Retry logic handled by ntscraper internally to some extent, 
            # or we could implement instance rotation here.
            raise e

