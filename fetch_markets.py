
'''
Polymarket Arbitrage Scanner - Market Data Fetcher
===================================================
Handles all interactions with Polymarket public APIs.
Fetches market data and order book information.
'''

import requests
import time
import logging
from typing import Dict, List, Optional, Tuple
import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(config.LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PolymarketAPIError(Exception):
    '''Custom exception for Polymarket API errors'''
    pass

def make_request_with_retry(url: str, params: Optional[Dict] = None) -> Dict:
    '''
    Make HTTP request with exponential backoff retry logic.

    Args:
        url: API endpoint URL
        params: Query parameters

    Returns:
        JSON response as dictionary

    Raises:
        PolymarketAPIError: If all retries fail
    '''
    for attempt in range(config.MAX_RETRIES):
        try:
            response = requests.get(
                url, 
                params=params, 
                timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            return response.json()

        except requests.exceptions.RequestException as e:
            wait_time = config.RETRY_BACKOFF ** attempt
            logger.warning(
                f"Request failed (attempt {attempt + 1}/{config.MAX_RETRIES}): {e}. "
                f"Retrying in {wait_time}s..."
            )
            if attempt < config.MAX_RETRIES - 1:
                time.sleep(wait_time)
            else:
                raise PolymarketAPIError(f"Failed after {config.MAX_RETRIES} attempts: {e}")

def fetch_active_markets(limit: int = 100) -> List[Dict]:
    '''
    Fetch active markets from Polymarket.

    Args:
        limit: Maximum number of markets to fetch per request

    Returns:
        List of market dictionaries with structure:
        {
            'condition_id': str,
            'question': str,
            'tokens': [{'token_id': str, 'outcome': str}, ...]
            'active': bool,
            ...
        }
    '''
    try:
        # Polymarket Gamma API endpoint for markets
        url = f"{config.GAMMA_API_BASE}/markets"

        params = {
            'limit': limit,
            'active': 'true',  # Only active markets
            'closed': 'false'   # Exclude closed markets
        }

        logger.info(f"Fetching active markets (limit={limit})...")
        data = make_request_with_retry(url, params)

        # The response structure may vary; adjust based on actual API
        # Typically returns a list or object with 'data' field
        if isinstance(data, list):
            markets = data
        elif isinstance(data, dict) and 'data' in data:
            markets = data['data']
        else:
            markets = []

        logger.info(f"Fetched {len(markets)} active markets")
        return markets

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []

def fetch_order_book(token_id: str) -> Dict:
    """
    Fetch the order book for a specific token from CLOB API.
    
    Args:
        token_id: The token ID to fetch order book for
        
    Returns:
        Dictionary with 'asks' and 'bids' lists
    """
    try:
        url = f"{config.CLOB_API_BASE}/book"
        params = {
            'token_id': token_id
        }
        
        logger.debug(f"Fetching order book for token {token_id}...")
        data = make_request_with_retry(url, params)
        
        # CLOB API returns structure like:
        # {
        #   "market": "...",
        #   "asset_id": "...",
        #   "bids": [{"price": "0.52", "size": "100"}, ...],
        #   "asks": [{"price": "0.48", "size": "50"}, ...]
        # }
        
        return {
            'asks': data.get('asks', []),
            'bids': data.get('bids', [])
        }
        
    except Exception as e:
        logger.error(f"Error fetching order book for token {token_id}: {e}")
        return {'asks': [], 'bids': []}

def fetch_active_markets(limit_per_page: int = 100, max_markets: int = 1000) -> List[Dict]:
    """
    Fetch active markets from Polymarket with simple pagination.

    Args:
        limit_per_page: Number of markets to fetch per page (API limit)
        max_markets: Safety cap on total markets to fetch

    Returns:
        List of market dictionaries
    """
    try:
        url = f"{config.GAMMA_API_BASE}/markets"
        all_markets: List[Dict] = []
        offset = 0

        logger.info(
            f"Fetching active markets with pagination "
            f"(limit_per_page={limit_per_page}, max_markets={max_markets})..."
        )

        while len(all_markets) < max_markets:
            params = {
                "limit": limit_per_page,
                "offset": offset,
                "active": "true",   # Only active markets
                "closed": "false",  # Exclude closed markets
            }

            data = make_request_with_retry(url, params)

            # Response may be list or { "data": [...] }
            if isinstance(data, list):
                page = data
            elif isinstance(data, dict) and "data" in data:
                page = data["data"]
            else:
                page = []

            if not page:
                # No more markets
                break

            all_markets.extend(page)
            offset += limit_per_page

        # Trim to max_markets just in case
        if len(all_markets) > max_markets:
            all_markets = all_markets[:max_markets]

        count = len(all_markets)
        logger.info(f"Fetched {count} active markets total")

        # Debug: show first 3 market titles so we know it's real data
        for m in all_markets[:3]:
            title = m.get("question", "Unknown title")
            mid = m.get("condition_id") or m.get("id")
            logger.info(f"  Sample market: [{mid}] {title}")

        return all_markets

    except Exception as e:
        logger.error(f"Error fetching markets: {e}")
        return []

def calculate_vwap(orders: List[Dict], target_size: float) -> Tuple[float, int]:
    '''
    Calculate volume-weighted average price for a target size.
    Walks down the order book until target size is filled.

    Args:
        orders: List of orders [{'price': str, 'size': str}, ...]
        target_size: Target position size to fill

    Returns:
        Tuple of (vwap, depth_count) where:
        - vwap: Volume-weighted average price (0.0 if insufficient liquidity)
        - depth_count: Number of price levels required to fill
    '''
    if not orders or target_size <= 0:
        return 0.0, 0

    total_cost = 0.0
    filled_size = 0.0
    depth_count = 0

    for order in orders:
        # Convert string prices/sizes to float
        price = float(order['price'])
        size = float(order['size'])

        if filled_size >= target_size:
            break

        # How much we can fill from this level
        remaining = target_size - filled_size
        fill_amount = min(remaining, size)

        total_cost += fill_amount * price
        filled_size += fill_amount
        depth_count += 1

    # If we couldn't fill the full size, return 0 (insufficient liquidity)
    if filled_size < target_size:
        logger.debug(f"Insufficient liquidity: needed {target_size}, found {filled_size}")
        return 0.0, depth_count

    vwap = total_cost / filled_size
    return vwap, depth_count

def get_market_arbitrage_data(market: Dict, target_size: float) -> Optional[Dict]:
    """
    Fetch and compute arbitrage data for a single market at a target size.

    Args:
        market: Market dictionary from fetch_active_markets()
        target_size: Position size to simulate

    Returns:
        Dictionary with arbitrage opportunity data or None if not applicable
    """
    try:
        import json

        # Extract market metadata
        market_id = market.get('condition_id') or market.get('id')
        market_title = market.get('question', 'Unknown')

        # KEY: Gamma API uses clobTokenIds, not tokens
        clob_token_ids_raw = market.get('clobTokenIds', '')

        # Parse clobTokenIds into a list of two token IDs
        if isinstance(clob_token_ids_raw, str) and clob_token_ids_raw:
            try:
                clob_token_ids = json.loads(clob_token_ids_raw)
            except json.JSONDecodeError:
                return None
        elif isinstance(clob_token_ids_raw, list):
            clob_token_ids = clob_token_ids_raw
        else:
            return None

        # Need exactly 2 tokens (binary market)
        if len(clob_token_ids) != 2:
            return None

        token_yes = clob_token_ids[0]
        token_no = clob_token_ids[1]

        if not token_yes or not token_no:
            return None

        # Fetch order books for both outcomes
        book_yes = fetch_order_book(token_yes)
        book_no = fetch_order_book(token_no)

        # Take asks on both sides (taker)
        asks_yes = book_yes.get('asks', [])
        asks_no = book_no.get('asks', [])

        # Optional debug: first 3 ask levels
        if asks_yes and asks_no:
            logger.debug(
                f"RAW YES asks (first 3): "
                f"{[(a['price'], a['size']) for a in asks_yes[:3]]}"
            )
            logger.debug(
                f"RAW NO asks (first 3): "
                f"{[(a['price'], a['size']) for a in asks_no[:3]]}"
            )

        # VWAP for target size on both legs
        vwap_yes, depth_yes = calculate_vwap(asks_yes, target_size)
        vwap_no, depth_no = calculate_vwap(asks_no, target_size)

        # Skip if insufficient liquidity
        if vwap_yes == 0.0 or vwap_no == 0.0:
            return None

        return {
            "market_id": market_id,
            "market_title": market_title,
            "target_size": target_size,
            "vwap_yes": vwap_yes,
            "vwap_no": vwap_no,
            "yes_book_depth": depth_yes,
            "no_book_depth": depth_no,
        }

    except Exception as e:
        logger.warning(f"Error processing market {market.get('question', 'unknown')}: {e}")
        return None
