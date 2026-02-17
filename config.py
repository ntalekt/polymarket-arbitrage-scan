
'''
Polymarket Arbitrage Scanner - Configuration
==============================================
All configurable parameters for the scanner.
Modify these values to adjust scanning behavior, fee assumptions, and thresholds.
'''

# ============================================================================
# SCANNING PARAMETERS
# ============================================================================

# How often to poll Polymarket for new data (seconds)
POLL_INTERVAL = 10

# Target position sizes to test (USD per leg)
# The scanner will simulate fills at each of these sizes
TARGET_SIZES = [50, 200]

# Minimum edge thresholds to flag opportunities (decimal, e.g., 0.005 = 0.5%)
EDGE_THRESHOLDS = [0.005, 0.010, 0.020]  # 0.5%, 1%, 2%

# ============================================================================
# FEE ASSUMPTIONS
# ============================================================================

# Taker fee rates for YES and NO legs (decimal)
# Default: 1.5% (0.015) - adjust based on Polymarket fee curve
# NOTE: Polymarket fees vary by probability. This is a simplified flat rate.
# Phase 2: implement dynamic fee curve based on outcome probability
FEE_RATE_YES = 0.015
FEE_RATE_NO = 0.015

# ============================================================================
# API ENDPOINTS
# ============================================================================

# Polymarket public API base URLs
GAMMA_API_BASE = "https://gamma-api.polymarket.com"
CLOB_API_BASE = "https://clob.polymarket.com"

# ============================================================================
# DATA PERSISTENCE
# ============================================================================

# SQLite database file path
DB_PATH = "polymarket_arbitrage.db"

# Log file path
LOG_FILE = "scanner.log"

# ============================================================================
# NETWORK & RETRY SETTINGS
# ============================================================================

# Maximum retries for failed API calls
MAX_RETRIES = 3

# Timeout for HTTP requests (seconds)
REQUEST_TIMEOUT = 10

# Backoff multiplier for retries (exponential backoff)
RETRY_BACKOFF = 2

# ============================================================================
# OPPORTUNITY TRACKING
# ============================================================================

# Time window for grouping the same opportunity (seconds)
# Opportunities within this window are considered the same persistent opportunity
OPPORTUNITY_WINDOW = 30
