"""
Quick CLI test for mtgdecks_scraper (no Streamlit needed).
Usage: python test_scraper.py [archetype_name]
"""
import sys
import json
import unittest.mock as mock

# Patch st.cache_data so the scraper works without Streamlit
import streamlit as st
mock_cache = lambda *a, **kw: (lambda f: f)
st.cache_data = mock_cache

from src.mtgdecks_scraper import get_recent_top_decks, get_decklist

ARCHETYPE = sys.argv[1] if len(sys.argv) > 1 else "Psychatog"

print(f"\n{'='*60}")
print(f"  Testing: get_recent_top_decks('{ARCHETYPE}')")
print(f"{'='*60}")

decks = get_recent_top_decks(ARCHETYPE)

if not decks:
    print("  [!] No decks found. Check archetype name or network.")
    sys.exit(1)

print(f"  Found {len(decks)} deck(s):\n")
for i, d in enumerate(decks, 1):
    print(f"  [{i}] {d['rank']:>4}  {d['player']:<20}  {d['event'][:35]:<35}  {d['players']:>4} players  {d['date']}")
    print(f"       {d['url']}")

# Fetch first decklist
print(f"\n{'='*60}")
first_url = decks[0]["url"]
print(f"  Fetching decklist: {first_url}")
print(f"{'='*60}\n")

cards = get_decklist(first_url)

if not cards:
    print("  [!] No cards found. Check HTML parsing.")
    sys.exit(1)

maindeck = [c for c in cards if c["section"] != "Sideboard"]
sideboard = [c for c in cards if c["section"] == "Sideboard"]
total_main = sum(c["qty"] for c in maindeck)
total_side = sum(c["qty"] for c in sideboard)

print(f"  Maindeck ({total_main} cards):")
for c in maindeck:
    print(f"    {c['qty']:>2}x  {c['name']:<30}  [{c['type']}]")

if sideboard:
    print(f"\n  Sideboard ({total_side} cards):")
    for c in sideboard:
        print(f"    {c['qty']:>2}x  {c['name']:<30}")

print(f"\n  Done. {total_main} main + {total_side} side = {total_main + total_side} total cards.")
