
'''
Polymarket Arbitrage Scanner - Database Module
===============================================
Handles SQLite database initialization and all data persistence operations.
'''

import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional
import config

def init_database():
    '''
    Initialize SQLite database with required tables.
    Creates tables if they don't exist.
    '''
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    # Main opportunities table - stores every detected arbitrage opportunity
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_hash TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            market_id TEXT NOT NULL,
            market_title TEXT,
            target_size REAL NOT NULL,
            vwap_yes REAL NOT NULL,
            vwap_no REAL NOT NULL,
            raw_sum REAL NOT NULL,
            fee_rate_yes REAL NOT NULL,
            fee_rate_no REAL NOT NULL,
            effective_cost REAL NOT NULL,
            edge_decimal REAL NOT NULL,
            yes_book_depth INTEGER,
            no_book_depth INTEGER,
            UNIQUE(opportunity_hash, timestamp)
        )
    ''')

    # Persistence tracking table - tracks how long opportunities stay open
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS opportunity_persistence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            opportunity_hash TEXT UNIQUE NOT NULL,
            market_id TEXT NOT NULL,
            target_size REAL NOT NULL,
            first_seen TEXT NOT NULL,
            last_seen TEXT NOT NULL,
            duration_seconds REAL,
            max_edge REAL,
            min_edge REAL,
            avg_edge REAL,
            observation_count INTEGER DEFAULT 1
        )
    ''')

    # Create indexes for faster queries
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON opportunities(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_market_id ON opportunities(market_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_edge ON opportunities(edge_decimal)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hash ON opportunities(opportunity_hash)')

    conn.commit()
    conn.close()
    print(f"✓ Database initialized at {config.DB_PATH}")

def generate_opportunity_hash(market_id: str, target_size: float, timestamp_bucket: int) -> str:
    '''
    Generate a unique hash for an opportunity based on market, size, and time window.

    Args:
        market_id: Polymarket market ID
        target_size: Position size in USD
        timestamp_bucket: Rounded timestamp to group opportunities

    Returns:
        SHA256 hash string
    '''
    data = f"{market_id}_{target_size}_{timestamp_bucket}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def log_opportunity(opp_data: Dict):
    '''
    Log a detected arbitrage opportunity to the database.

    Args:
        opp_data: Dictionary containing opportunity fields
    '''
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    # Insert into opportunities table
    cursor.execute('''
        INSERT OR IGNORE INTO opportunities (
            opportunity_hash, timestamp, market_id, market_title,
            target_size, vwap_yes, vwap_no, raw_sum,
            fee_rate_yes, fee_rate_no, effective_cost, edge_decimal,
            yes_book_depth, no_book_depth
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        opp_data['opportunity_hash'],
        opp_data['timestamp'],
        opp_data['market_id'],
        opp_data['market_title'],
        opp_data['target_size'],
        opp_data['vwap_yes'],
        opp_data['vwap_no'],
        opp_data['raw_sum'],
        opp_data['fee_rate_yes'],
        opp_data['fee_rate_no'],
        opp_data['effective_cost'],
        opp_data['edge_decimal'],
        opp_data.get('yes_book_depth', 0),
        opp_data.get('no_book_depth', 0)
    ))

    conn.commit()
    conn.close()

def update_persistence(opp_hash: str, market_id: str, target_size: float, 
                       timestamp: str, edge: float):
    '''
    Update or create persistence tracking record for an opportunity.

    Args:
        opp_hash: Opportunity hash
        market_id: Market identifier
        target_size: Position size
        timestamp: Current timestamp
        edge: Current edge value
    '''
    conn = sqlite3.connect(config.DB_PATH)
    cursor = conn.cursor()

    # Check if this opportunity hash already exists
    cursor.execute('''
        SELECT first_seen, max_edge, min_edge, avg_edge, observation_count
        FROM opportunity_persistence WHERE opportunity_hash = ?
    ''', (opp_hash,))

    result = cursor.fetchone()

    if result:
        # Update existing record
        first_seen, max_edge, min_edge, avg_edge, count = result
        new_count = count + 1
        new_avg_edge = ((avg_edge * count) + edge) / new_count

        first_dt = datetime.fromisoformat(first_seen)
        last_dt = datetime.fromisoformat(timestamp)
        duration = (last_dt - first_dt).total_seconds()

        cursor.execute('''
            UPDATE opportunity_persistence
            SET last_seen = ?, duration_seconds = ?, 
                max_edge = ?, min_edge = ?, avg_edge = ?,
                observation_count = ?
            WHERE opportunity_hash = ?
        ''', (
            timestamp, duration,
            max(max_edge, edge), min(min_edge, edge), new_avg_edge,
            new_count, opp_hash
        ))
    else:
        # Create new persistence record
        cursor.execute('''
            INSERT INTO opportunity_persistence (
                opportunity_hash, market_id, target_size,
                first_seen, last_seen, duration_seconds,
                max_edge, min_edge, avg_edge, observation_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            opp_hash, market_id, target_size,
            timestamp, timestamp, 0.0,
            edge, edge, edge, 1
        ))

    conn.commit()
    conn.close()

def get_all_opportunities() -> List[Dict]:
    '''
    Retrieve all logged opportunities from database.

    Returns:
        List of opportunity dictionaries
    '''
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM opportunities ORDER BY timestamp DESC')
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]

def get_persistence_data() -> List[Dict]:
    '''
    Retrieve all persistence tracking data.

    Returns:
        List of persistence records
    '''
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT * FROM opportunity_persistence 
        ORDER BY duration_seconds DESC
    ''')
    rows = cursor.fetchall()

    conn.close()
    return [dict(row) for row in rows]
