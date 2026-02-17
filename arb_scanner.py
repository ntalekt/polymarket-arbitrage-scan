
'''
Polymarket Arbitrage Scanner - Main Scanner
============================================
Core arbitrage detection logic and main execution loop.
'''

import time
import logging
from datetime import datetime
from typing import Dict, List
import config
import database
import fetch_markets

# Configure logging
logger = logging.getLogger(__name__)

def detect_arbitrage(arb_data: Dict) -> Dict:
    '''
    Analyze market data and detect arbitrage opportunities.
    Applies fee calculations and edge computation.

    Args:
        arb_data: Dictionary from get_market_arbitrage_data() containing:
            - market_id, market_title, target_size
            - vwap_yes, vwap_no
            - yes_book_depth, no_book_depth

    Returns:
        Dictionary with opportunity details including edge, or None if no opportunity
    '''
    vwap_yes = arb_data['vwap_yes']
    vwap_no = arb_data['vwap_no']
    target_size = arb_data['target_size']

    # Calculate raw sum (before fees)
    raw_sum = vwap_yes + vwap_no

    # Quick filter: if raw_sum >= 1, no arbitrage possible
    if raw_sum >= 1.0:
        return None

    # Apply taker fees on both legs
    # Cost to buy YES: vwap_yes * size * (1 + fee)
    # Cost to buy NO: vwap_no * size * (1 + fee)
    cost_yes = vwap_yes * target_size * (1 + config.FEE_RATE_YES)
    cost_no = vwap_no * target_size * (1 + config.FEE_RATE_NO)
    total_cost = cost_yes + cost_no

    # Payoff: one outcome settles to 1, the other to 0
    # So we get back: target_size * 1 = target_size
    payoff = target_size

    # Effective cost per unit of size
    effective_cost = total_cost / target_size

    # Edge = 1 - effective_cost (in decimal, e.g., 0.012 = 1.2%)
    edge = 1.0 - effective_cost

    # Only flag if edge is positive
    if edge <= 0:
        return None

    # Build opportunity record
    timestamp = datetime.utcnow().isoformat()
    timestamp_bucket = int(time.time() // config.OPPORTUNITY_WINDOW)

    opportunity_hash = database.generate_opportunity_hash(
        arb_data['market_id'],
        target_size,
        timestamp_bucket
    )

    opportunity = {
        'opportunity_hash': opportunity_hash,
        'timestamp': timestamp,
        'market_id': arb_data['market_id'],
        'market_title': arb_data['market_title'],
        'target_size': target_size,
        'vwap_yes': vwap_yes,
        'vwap_no': vwap_no,
        'raw_sum': raw_sum,
        'fee_rate_yes': config.FEE_RATE_YES,
        'fee_rate_no': config.FEE_RATE_NO,
        'effective_cost': effective_cost,
        'edge_decimal': edge,
        'yes_book_depth': arb_data['yes_book_depth'],
        'no_book_depth': arb_data['no_book_depth']
    }

    return opportunity

def scan_markets_once() -> int:
    '''
    Perform one complete scan of all active markets.
    Detects and logs all arbitrage opportunities.

    Returns:
        Number of opportunities detected in this scan
    '''
    logger.info("=" * 60)
    logger.info("Starting market scan...")

    # Fetch all active markets
    markets = fetch_markets.fetch_active_markets(limit_per_page=100, max_markets=1000)

    if not markets:
        logger.warning("No markets fetched. Check API connectivity.")
        return 0
    
    # DEBUG: log raw JSON for the first market only
    first_market = markets[0]
    logger.debug(f"First market raw JSON: {first_market}")

    opportunities_found = 0

    # For each market, check each target size
    for market in markets:
        market_title = market.get('question', 'Unknown')

        for target_size in config.TARGET_SIZES:
            # Get arbitrage data (VWAPs, book depth)
            arb_data = fetch_markets.get_market_arbitrage_data(market, target_size)

            if not arb_data:
                continue  # Skip if insufficient liquidity or not binary

            # DEBUG: for the first few markets per scan, show VWAPs
            # This tells us we're actually reading order books and computing prices
            if opportunities_found < 3:
                logger.info(
                    f"Market: {market_title[:60]}... | "
                    f"Size: ${target_size} | "
                    f"VWAP_YES: {arb_data['vwap_yes']:.4f} | "
                    f"VWAP_NO: {arb_data['vwap_no']:.4f} | "
                    f"Depth YES/NO: {arb_data['yes_book_depth']}/{arb_data['no_book_depth']}"
                )

            # Check for arbitrage opportunity
            opportunity = detect_arbitrage(arb_data)

            if opportunity:
                edge_pct = opportunity['edge_decimal'] * 100

                # Log to database
                database.log_opportunity(opportunity)

                # Update persistence tracking
                database.update_persistence(
                    opportunity['opportunity_hash'],
                    opportunity['market_id'],
                    opportunity['target_size'],
                    opportunity['timestamp'],
                    opportunity['edge_decimal']
                )

                # Console log for significant opportunities
                if opportunity['edge_decimal'] >= min(config.EDGE_THRESHOLDS):
                    logger.info(
                        f"OPPORTUNITY FOUND: {market_title[:50]}... | "
                        f"Size: ${target_size} | Edge: {edge_pct:.2f}% | "
                        f"YES: {opportunity['vwap_yes']:.4f} | "
                        f"NO: {opportunity['vwap_no']:.4f}"
                    )

                opportunities_found += 1


    logger.info(
        f"Scan complete. Opportunities found: {opportunities_found} "
        f"| Markets scanned: {len(markets)}"
    )

    return opportunities_found

def run_continuous_scanner():
    '''
    Main execution loop - continuously scans markets at configured interval.
    Runs indefinitely until interrupted.
    '''
    logger.info("=" * 60)
    logger.info("POLYMARKET ARBITRAGE SCANNER - STARTING")
    logger.info("=" * 60)
    logger.info(f"Poll interval: {config.POLL_INTERVAL}s")
    logger.info(f"Target sizes: {config.TARGET_SIZES}")
    logger.info(f"Edge thresholds: {[f'{t*100}%' for t in config.EDGE_THRESHOLDS]}")
    logger.info(f"Fee rates: YES={config.FEE_RATE_YES*100}%, NO={config.FEE_RATE_NO*100}%")
    logger.info("=" * 60)

    # Initialize database
    database.init_database()

    scan_count = 0

    try:
        while True:
            scan_count += 1
            logger.info(f"\n--- Scan #{scan_count} ---")

            # Perform one market scan
            scan_markets_once()

            # Wait before next scan
            logger.info(f"Sleeping {config.POLL_INTERVAL}s until next scan...\n")
            time.sleep(config.POLL_INTERVAL)

    except KeyboardInterrupt:
        logger.info("\n" + "=" * 60)
        logger.info("Scanner stopped by user")
        logger.info(f"Total scans completed: {scan_count}")
        logger.info("=" * 60)

# ============================================================================
# PHASE 2 EXTENSION POINTS
# ============================================================================
# 
# To add live trading in Phase 2:
# 
# 1. ORDER EXECUTION MODULE (execute_orders.py):
#    - Add functions to submit limit orders to Polymarket CLOB
#    - Implement order status tracking and confirmation
#    - Handle partial fills and cancellations
#
# 2. POSITION MANAGEMENT (positions.py):
#    - Track open positions across both legs
#    - Monitor settlements and payouts
#    - Calculate realized P&L
#
# 3. RISK CONTROLS (risk.py):
#    - Implement position size limits
#    - Add daily loss limits
#    - Monitor account balance and margin
#
# 4. ENHANCED FEE CURVE:
#    - Replace flat fee rates with dynamic calculation based on outcome probability
#    - Use Polymarket's actual fee curve: varies from ~0.1% to 1.6%
#    - See: https://docs.polymarket.com/polymarket-learn/trading/fees
#
# 5. EXECUTION LOGIC:
#    - In detect_arbitrage(), instead of just logging, also:
#      a) Check if edge > execution threshold (e.g., 1.5%)
#      b) Call execute_orders.submit_arb_trade(opportunity)
#      c) Monitor fills and update positions
#
# ============================================================================

if __name__ == "__main__":
    run_continuous_scanner()
