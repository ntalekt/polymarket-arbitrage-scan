
# Polymarket Arbitrage Scanner MVP

A measurement-first arbitrage opportunity scanner for Polymarket prediction markets.  
**No live trading** — this is a data collection and analysis tool only.

---

## 🎯 What This Does

Over a configurable period (e.g., 7 days), this scanner:

1. **Continuously polls** Polymarket for active binary markets
2. **Detects opportunities** where YES_price + NO_price < 1
3. **Simulates execution** at your target position sizes (e.g., $50, $200)
4. **Adjusts for fees and slippage** using order book depth
5. **Logs everything** to a SQLite database for analysis

After collection, you can analyze:
- How often arbitrage opportunities appear
- How many survive fees at your intended trade size
- How long opportunities stay open (persistence)
- Which markets offer the most opportunities

---

## 📁 Project Structure

```
polymarket-arb-scanner/
├── config.py                    # All configuration parameters
├── database.py                  # SQLite database operations
├── fetch_markets.py             # Polymarket API interaction
├── arb_scanner.py              # Main scanning logic (run this)
├── analyze_opportunities.py     # Analytics and reporting
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── polymarket_arbitrage.db      # SQLite database (created on first run)
└── scanner.log                  # Execution log
```

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install requests pandas
```

Or use `requirements.txt`:

```bash
pip install -r requirements.txt
```

### 2. Configure Scanner

Edit `config.py` to adjust:

- **POLL_INTERVAL**: How often to scan (default: 10 seconds)
- **TARGET_SIZES**: Position sizes to simulate (default: [50, 200])
- **EDGE_THRESHOLDS**: Minimum edges to flag (default: [0.5%, 1%, 2%])
- **FEE_RATE_YES / FEE_RATE_NO**: Taker fee assumptions (default: 1.5%)

### 3. Run Scanner

```bash
python arb_scanner.py
```

The scanner will run continuously until you press `Ctrl+C`.

### 4. Analyze Results

After collecting data (recommend at least a few hours, ideally 7 days):

```bash
python analyze_opportunities.py
```

This prints comprehensive statistics:
- Total opportunities detected
- Edge distribution (how many above each threshold)
- Statistics by target size
- Persistence analysis (how long opportunities last)
- Top markets by opportunity count

---

## 📊 Understanding the Output

### Scanner Console Output

```
2026-02-11 20:00:15 - INFO - Starting market scan...
2026-02-11 20:00:16 - INFO - ✓ Fetched 127 active markets
2026-02-11 20:00:28 - INFO - 🎯 OPPORTUNITY FOUND: Will Trump win 2028? | Size: $50 | Edge: 1.23% | YES: 0.4850 | NO: 0.5020
2026-02-11 20:00:35 - INFO - Scan complete. Opportunities found: 3
2026-02-11 20:00:35 - INFO - Sleeping 10s until next scan...
```

### Database Schema

**opportunities table:**
- Logs every detected arbitrage opportunity
- Fields: timestamp, market_id, market_title, target_size, vwap_yes, vwap_no, edge_decimal, etc.

**opportunity_persistence table:**
- Tracks how long each opportunity stays open
- Fields: first_seen, last_seen, duration_seconds, avg_edge, observation_count

---

## 🔧 Configuration Details

### Fee Rate Assumptions

Default: **1.5%** taker fee per leg.

**Important:** Polymarket's actual fee structure is dynamic (varies by probability).  
For Phase 1 (measurement), we use a simplified flat rate.

**Phase 2 Enhancement:** Implement the actual Polymarket fee curve:
- ~0.1% at extreme probabilities (0.01, 0.99)
- ~1.6% near 0.50 probability
- See: https://docs.polymarket.com/polymarket-learn/trading/fees

### Target Sizes

Defaults: `[50, 200]` USD per leg.

- **Small size (50):** Tests if opportunities exist at micro-scale
- **Larger size (200):** Tests if they survive with realistic position sizes

You can add more sizes: `[50, 100, 200, 500]`

### Poll Interval

Default: **10 seconds**

- Faster polling (5s) captures more fleeting opportunities but increases API load
- Slower polling (30s) is gentler but may miss short-lived edges

### Edge Thresholds

Defaults: `[0.005, 0.010, 0.020]` = 0.5%, 1%, 2%

These define what gets flagged in analytics:
- **0.5%:** Minimal but theoretically profitable
- **1%:** Realistic minimum after execution risk
- **2%:** High-quality opportunities worth prioritizing

---

## 📈 What to Look For in Results

### Good Signs (Worth Pursuing in Phase 2)

✅ **10+ opportunities per day** at your target size  
✅ **Median edge ≥1%** after fees  
✅ **Duration ≥30 seconds** for a meaningful portion  
✅ **Consistent opportunities** across multiple markets

### Red Flags (Pivot to Copy Trading Instead)

❌ **<5 opportunities per day** — too sparse  
❌ **Median edge <0.5%** — eaten by execution risk  
❌ **Duration <10 seconds** — can't execute manually, need HFT infrastructure  
❌ **Opportunities only in illiquid markets** — can't scale

---

## 🛠️ Phase 2: Live Trading Extensions

This MVP is **measurement only**. To add live trading:

### 1. Order Execution Module
- Create `execute_orders.py`
- Implement Polymarket CLOB order submission
- Handle limit orders, confirmations, and cancellations

### 2. Position Management
- Create `positions.py`
- Track open positions across both legs
- Monitor settlements and calculate realized P&L

### 3. Risk Controls
- Create `risk.py`
- Implement position size limits
- Add daily loss limits and circuit breakers
- Monitor account balance

### 4. Enhanced Fee Model
- Replace flat fee rates with dynamic calculation
- Use actual Polymarket fee curve based on outcome probability

### 5. Integration
- In `arb_scanner.py`, add execution logic:
  - Check if edge > execution threshold
  - Call `execute_orders.submit_arb_trade(opportunity)`
  - Monitor fills and update positions

**See Phase 2 extension comments in `arb_scanner.py` for details.**

---

## 🔒 API & Data Notes

### Polymarket Public APIs

This scanner uses **unauthenticated public endpoints**:

- **Gamma API** (`https://gamma-api.polymarket.com`): Market metadata
- **CLOB API** (`https://clob.polymarket.com`): Order book data

No API keys or authentication required for read-only access.

### Rate Limiting

Polymarket does not publish explicit rate limits for public APIs, but we implement:
- Configurable poll interval (default: 10s)
- Exponential backoff on failed requests
- Request timeout (10s)

If you encounter 429 errors, increase `POLL_INTERVAL` in config.

### Data Accuracy

- Order book data is **real-time** but may change between fetch and execution
- VWAP calculations assume **full fills at displayed prices** (optimistic)
- Actual execution may face additional slippage

---

## 🐛 Troubleshooting

### "No markets fetched"
- Check internet connectivity
- Verify Polymarket API endpoints are accessible
- Check `scanner.log` for detailed errors

### "Insufficient liquidity" warnings
- Normal for small/new markets
- Scanner will skip these and continue
- Adjust `TARGET_SIZES` to smaller values if needed

### Database locked errors
- Only run one scanner instance at a time
- If crashed, delete `polymarket_arbitrage.db` and restart

### No opportunities detected
- Markets may be efficient at the moment
- Try running for longer (24+ hours)
- Reduce `EDGE_THRESHOLDS` to see smaller opportunities
- Check fee rate assumptions (may be too high)

---

## 📝 Export & Further Analysis

### Export to CSV

```python
from analyze_opportunities import export_opportunities_csv
export_opportunities_csv("my_data.csv")
```

### Custom Queries

The SQLite database is accessible directly:

```python
import sqlite3
conn = sqlite3.connect('polymarket_arbitrage.db')

# Custom query
query = '''
    SELECT market_title, AVG(edge_decimal) as avg_edge, COUNT(*) as count
    FROM opportunities
    WHERE edge_decimal >= 0.01
    GROUP BY market_id
    ORDER BY count DESC
    LIMIT 10
'''

results = conn.execute(query).fetchall()
```

---

## 📞 Questions?

This scanner is designed to be **extended by you**.  
All code is heavily commented with clear extension points.

Key files to understand:
1. **config.py** — adjust all parameters here first
2. **arb_scanner.py** — main logic, start here to understand flow
3. **analyze_opportunities.py** — customize analytics output

Happy scanning! 🚀
