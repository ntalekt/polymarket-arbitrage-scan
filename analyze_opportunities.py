
'''
Polymarket Arbitrage Scanner - Analytics Module
================================================
Analyze logged opportunities and generate summary statistics.
'''

import sqlite3
from datetime import datetime
from typing import Dict, List
import config
import database

def analyze_opportunities():
    '''
    Analyze all logged opportunities and print comprehensive statistics.
    '''
    print("\n" + "=" * 70)
    print("POLYMARKET ARBITRAGE SCANNER - OPPORTUNITY ANALYSIS")
    print("=" * 70)

    # Fetch all opportunities
    opportunities = database.get_all_opportunities()

    if not opportunities:
        print("\n⚠️  No opportunities found in database.")
        print("Run the scanner first to collect data.\n")
        return

    total_count = len(opportunities)
    print(f"\n📊 Total Opportunities Logged: {total_count}")

    # ========================================================================
    # 1. EDGE DISTRIBUTION
    # ========================================================================
    print("\n" + "-" * 70)
    print("EDGE DISTRIBUTION")
    print("-" * 70)

    for threshold in config.EDGE_THRESHOLDS:
        count = sum(1 for opp in opportunities if opp['edge_decimal'] >= threshold)
        pct = (count / total_count) * 100 if total_count > 0 else 0
        print(f"  Edge >= {threshold*100:4.1f}%: {count:5d} opportunities ({pct:5.1f}%)")

    # ========================================================================
    # 2. STATISTICS BY TARGET SIZE
    # ========================================================================
    print("\n" + "-" * 70)
    print("STATISTICS BY TARGET SIZE")
    print("-" * 70)

    for size in config.TARGET_SIZES:
        size_opps = [opp for opp in opportunities if opp['target_size'] == size]

        if not size_opps:
            continue

        edges = [opp['edge_decimal'] for opp in size_opps]
        avg_edge = sum(edges) / len(edges)
        median_edge = sorted(edges)[len(edges) // 2]
        max_edge = max(edges)

        print(f"\n  Target Size: ${size}")
        print(f"    Count:       {len(size_opps)}")
        print(f"    Avg Edge:    {avg_edge*100:.3f}%")
        print(f"    Median Edge: {median_edge*100:.3f}%")
        print(f"    Max Edge:    {max_edge*100:.3f}%")

    # ========================================================================
    # 3. PERSISTENCE ANALYSIS
    # ========================================================================
    print("\n" + "-" * 70)
    print("OPPORTUNITY PERSISTENCE")
    print("-" * 70)

    persistence_data = database.get_persistence_data()

    if persistence_data:
        # Duration buckets
        buckets = {
            '0-10s': (0, 10),
            '10-30s': (10, 30),
            '30-60s': (30, 60),
            '60-120s': (60, 120),
            '>120s': (120, float('inf'))
        }

        for bucket_name, (min_dur, max_dur) in buckets.items():
            count = sum(
                1 for p in persistence_data 
                if min_dur <= p['duration_seconds'] < max_dur
            )
            pct = (count / len(persistence_data)) * 100 if persistence_data else 0
            print(f"  {bucket_name:>10}: {count:5d} opportunities ({pct:5.1f}%)")

        # Top 10 longest-lasting opportunities
        print("\n  Top 10 Longest-Lasting Opportunities:")
        print("  " + "-" * 66)

        sorted_persistence = sorted(
            persistence_data, 
            key=lambda x: x['duration_seconds'], 
            reverse=True
        )[:10]

        for i, p in enumerate(sorted_persistence, 1):
            print(
                f"  {i:2d}. Duration: {p['duration_seconds']:6.1f}s | "
                f"Avg Edge: {p['avg_edge']*100:5.2f}% | "
                f"Observations: {p['observation_count']:3d}"
            )
    else:
        print("  No persistence data available.")

    # ========================================================================
    # 4. TOP MARKETS BY OPPORTUNITY COUNT
    # ========================================================================
    print("\n" + "-" * 70)
    print("TOP MARKETS BY OPPORTUNITY COUNT")
    print("-" * 70)

    market_counts = {}
    for opp in opportunities:
        market_id = opp['market_id']
        market_title = opp['market_title']

        if market_id not in market_counts:
            market_counts[market_id] = {'title': market_title, 'count': 0}

        market_counts[market_id]['count'] += 1

    sorted_markets = sorted(
        market_counts.items(),
        key=lambda x: x[1]['count'],
        reverse=True
    )[:10]

    for i, (market_id, data) in enumerate(sorted_markets, 1):
        title = data['title'][:55] + "..." if len(data['title']) > 55 else data['title']
        print(f"  {i:2d}. {title}")
        print(f"      Opportunities: {data['count']}")

    # ========================================================================
    # 5. TIME SERIES SUMMARY
    # ========================================================================
    print("\n" + "-" * 70)
    print("TIME SERIES SUMMARY")
    print("-" * 70)

    if opportunities:
        timestamps = [datetime.fromisoformat(opp['timestamp']) for opp in opportunities]
        first_scan = min(timestamps)
        last_scan = max(timestamps)
        duration = (last_scan - first_scan).total_seconds()

        print(f"  First Scan:  {first_scan.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Last Scan:   {last_scan.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print(f"  Duration:    {duration/3600:.2f} hours ({duration/86400:.2f} days)")

        if duration > 0:
            opps_per_hour = (total_count / duration) * 3600
            print(f"  Avg Rate:    {opps_per_hour:.1f} opportunities/hour")

    print("\n" + "=" * 70 + "\n")

def export_opportunities_csv(filename: str = "opportunities_export.csv"):
    '''
    Export all opportunities to CSV for further analysis.

    Args:
        filename: Output CSV filename
    '''
    import csv

    opportunities = database.get_all_opportunities()

    if not opportunities:
        print("No opportunities to export.")
        return

    with open(filename, 'w', newline='', encoding='utf-8') as f:
        if opportunities:
            writer = csv.DictWriter(f, fieldnames=opportunities[0].keys())
            writer.writeheader()
            writer.writerows(opportunities)

    print(f"✓ Exported {len(opportunities)} opportunities to {filename}")

if __name__ == "__main__":
    analyze_opportunities()
