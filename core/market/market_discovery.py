import logging
import aiohttp
from typing import Optional, List
from config.config_new_bot import GAMMA_EVENTS_URL, ASSETS
from core.models import MarketInfo

logger = logging.getLogger("MarketDiscovery")


class MarketDiscovery:    
    def __init__(self, assets: List[str] = None):
        self.assets = assets or ASSETS
        logger.info(f"MarketDiscovery initialized for assets: {', '.join(self.assets)}")
    
    async def find_active_market(self) -> Optional[MarketInfo]:
        try:
            return await self._find_15min_market_via_gamma()
        except Exception as e:
            logger.error(f"Error finding market: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def _find_15min_market_via_gamma(self) -> Optional[MarketInfo]:
        from datetime import datetime, timezone
        
        async with aiohttp.ClientSession() as session:
            for asset in self.assets:
                asset = asset.strip().lower()
                
                for offset in [0, 1, 2]:
                    epoch = self._get_15min_window_epoch(offset)
                    slug = f"{asset}-updown-15m-{epoch}"
                    
                    try:
                        async with session.get(
                            GAMMA_EVENTS_URL,
                            params={"slug": slug},
                            timeout=aiohttp.ClientTimeout(total=5)
                        ) as resp:
                            if resp.status != 200:
                                continue
                            
                            events = await resp.json()
                            if not events or not isinstance(events, list):
                                continue
                            
                            event = events[0]
                            if event.get('closed'):
                                continue
                            
                            markets = event.get('markets', [])
                            if not markets:
                                continue
                            
                            market = markets[0]
                            
                            end_date_str = market.get('endDate') or event.get('endDate')
                            if not end_date_str:
                                continue
                            
                            try:
                                from datetime import datetime, timezone
                                end_dt = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
                                time_to_expiry = (end_dt - datetime.now(timezone.utc)).total_seconds()
                                
                                if time_to_expiry <= 120:
                                    logger.debug(f"Market {slug} expires in {time_to_expiry:.0f}s - too close")
                                    continue
                            except Exception:
                                continue
                            
                            tokens = market.get('clobTokenIds', [])
                            if isinstance(tokens, str):
                                import json
                                try:
                                    tokens = json.loads(tokens)
                                except Exception:
                                    continue
                            
                            if len(tokens) < 2:
                                continue
                            
                            market_info = MarketInfo(
                                slug=slug,
                                question=market.get('question', slug),
                                asset=asset.upper(),
                                token_id_yes=tokens[0],
                                token_id_no=tokens[1],
                                end_date_iso=end_date_str,
                                description=market.get('description', '')
                            )
                            
                            logger.info(f"  Found 15-minute market: {slug}")
                            logger.info(f"  Question: {market_info.question}")
                            logger.info(f"  Expires in: {time_to_expiry/60:.1f} minutes")
                            return market_info
                            
                    except Exception as e:
                        logger.debug(f"Error checking {slug}: {e}")
                        continue
            
            logger.warning("Active 15-minute market not found")
            return None
    
    def _get_15min_window_epoch(self, offset_windows=0) -> int:
        from datetime import datetime, timezone
        now = int(datetime.now(timezone.utc).timestamp())
        window_size = 900  
        current_window_start = (now // window_size) * window_size
        return current_window_start + (offset_windows * window_size)
    
    def _extract_asset(self, question: str) -> str:
        for asset in self.assets:
            if asset.lower() in question.lower():
                return asset.upper()
        return "UNKNOWN"
    
    async def get_market_details(self, market_slug: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(GAMMA_EVENTS_URL) as resp:
                    if resp.status != 200:
                        return None
                    
                    events = await resp.json()
                    
                    for event in events:
                        markets = event.get("markets", [])
                        for market in markets:
                            if market.get("slug") == market_slug:
                                return market
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting market details: {e}")
            return None
