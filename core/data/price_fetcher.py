import logging
import aiohttp
from typing import Optional, Dict
from config.config_new_bot import DATA_API, CLOB_API
from core.models import MarketInfo

logger = logging.getLogger("PriceFetcher")


class PriceFetcher:    
    def __init__(self):
        logger.info("PriceFetcher initialized")
    
    async def get_prices(self, market: MarketInfo) -> Optional[Dict[str, float]]:
        try:
            async with aiohttp.ClientSession() as session:
                up_price = await self._get_token_price(session, market.token_id_yes)
                if up_price is None:
                    logger.warning(f"Failed to get price for YES token: {market.token_id_yes[:20]}...")
                    return None

                down_price = await self._get_token_price(session, market.token_id_no)
                if down_price is None:
                    logger.warning(f"Failed to get price for NO token: {market.token_id_no[:20]}...")
                    return None
                
                logger.debug(f"Prices retrieved: UP={up_price:.3f}, DOWN={down_price:.3f}")
                return {"up": up_price, "down": down_price}
            
        except Exception as e:
            logger.error(f"Error getting prices: {e}")
            return None
    
    async def _get_token_price(self, session: aiohttp.ClientSession, token_id: str) -> Optional[float]:
        data_api_url = f"{DATA_API}/book/{token_id}"
        try:
            async with session.get(data_api_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    price = self._extract_price_from_response(data)
                    if price is not None:
                        logger.debug(f"Price retrieved via {data_api_url}: {price:.3f}")
                        return price
                else:
                    logger.debug(f"Data API {data_api_url} returned status {resp.status}")
        except Exception as e:
            logger.debug(f"Data API error {data_api_url}: {e}")
        
        endpoints_to_try = [
            f"{CLOB_API}/book?token_id={token_id}",
            f"{CLOB_API}/midpoint?token_id={token_id}",
            f"{CLOB_API}/price?token_id={token_id}",
        ]
        
        for endpoint in endpoints_to_try:
            try:
                async with session.get(endpoint, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        
                        price = self._extract_price_from_response(data)
                        if price is not None:
                            logger.debug(f"Price retrieved via {endpoint}: {price:.3f}")
                            return price
                    else:
                        logger.debug(f"Endpoint {endpoint} returned status {resp.status}")
                        
            except Exception as e:
                logger.debug(f"Error with endpoint {endpoint}: {e}")
                continue
        
        logger.warning(f"All endpoints failed for token {token_id[:20]}...")
        return None
    
    def _extract_price_from_response(self, data) -> Optional[float]:
        try:
            if isinstance(data, dict) and "price" in data:
                try:
                    return float(data["price"])
                except Exception:
                    return None
            
            if isinstance(data, dict) and "mid" in data:
                try:
                    return float(data["mid"])
                except Exception:
                    return None
            
            if isinstance(data, dict):
                bids = data.get("bids", [])
                asks = data.get("asks", [])
                
                if bids and asks:
                    try:
                        best_bid = float(bids[0]["price"]) if isinstance(bids[0], dict) else float(bids[0][0])
                        best_ask = float(asks[0]["price"]) if isinstance(asks[0], dict) else float(asks[0][0])
                        midpoint = (best_bid + best_ask) / 2.0
                        return midpoint
                    except Exception:
                        return None
                elif bids:
                    try:
                        return float(bids[0]["price"]) if isinstance(bids[0], dict) else float(bids[0][0])
                    except Exception:
                        return None
                elif asks:
                    try:
                        return float(asks[0]["price"]) if isinstance(asks[0], dict) else float(asks[0][0])
                    except Exception:
                        return None
            
            if isinstance(data, list) and len(data) > 0:
                if isinstance(data[0], dict) and "price" in data[0]:
                    try:
                        return float(data[0]["price"])
                    except Exception:
                        return None
                elif isinstance(data[0], (int, float, str)):
                    try:
                        return float(data[0])
                    except Exception:
                        return None
            
            return None
            
        except Exception as e:
            logger.debug(f"Error extracting price from response: {e}")
            return None
    
    async def get_orderbook(self, token_id: str) -> Optional[dict]:
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{DATA_API}/book/{token_id}"
                async with session.get(url) as resp:
                    if resp.status == 200:
                        orderbook = await resp.json()
                        return orderbook
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting orderbook: {e}")
            return None
