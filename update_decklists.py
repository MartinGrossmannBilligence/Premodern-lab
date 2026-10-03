"""
Update decklists.json with fresh data from mtgdecks.net.
Merges new decks with existing ones (deduplicates by URL).
Usage: python update_decklists.py [--archetypes "Psychatog,Burn"] [--max-decks 10]
"""
import sys
import os
import json
import time
import argparse
import unittest.mock as mock

# Patch st.cache_data so the scraper works without Streamlit
import streamlit as st
st.cache_data = lambda *a, **kw: (lambda f: f)

from src.mtgdecks_scraper import get_recent_top_decks, get_decklist

DATA_PATH = "data/decklists.json"

def load_existing():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save(data):
    tmp = DATA_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, DATA_PATH)  # atomic rename — safe against interruption

def update_archetype(arch, existing_decks, max_decks):
    existing_cards = {d["url"]: d.get("cards", []) for d in existing_decks}

    print(f"\n  [{arch}] Fetching top decks...")
    try:
        top_decks = get_recent_top_decks(arch)
    except Exception as e:
        print(f"  [!] Error fetching list for '{arch}': {e}")
        return existing_decks  # safe fallback

    # If scraper returned nothing (e.g. 403), keep existing unchanged
    if not top_decks:
        return existing_decks

    new_decks = [d for d in top_decks if d["url"] not in existing_cards]
    print(f"  [{arch}] Found {len(top_decks)} total, {len(new_decks)} new")

    # Fetch cards only for new decks
    for deck in new_decks:
        print(f"  [{arch}]   Fetching decklist: {deck['url']}")
        try:
            cards = get_decklist(deck["url"])
            deck["cards"] = cards
            main_n = sum(c["qty"] for c in cards if c["section"] != "Sideboard")
            side_n = sum(c["qty"] for c in cards if c["section"] == "Sideboard")
            print(f"  [{arch}]   -> {main_n} main + {side_n} side")
        except Exception as e:
            print(f"  [!] Error fetching decklist: {e}")
            deck["cards"] = []
        time.sleep(0.5)

    # Merge existing + new, deduplicate, sort newest first (by URL ID), keep top max_decks
    merged = {d["url"]: d for d in existing_decks}
    for d in new_decks:
        merged[d["url"]] = d

    def _url_id(d):
        try:
            return int(d["url"].rstrip("/").split("-")[-1])
        except:
            return 0

    return sorted(merged.values(), key=_url_id, reverse=True)[:max_decks]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetypes", help="Comma-separated list of archetypes to update (default: all)")
    parser.add_argument("--max-decks", type=int, default=20, help="Max decks to keep per archetype (default: 20)")
    args = parser.parse_args()

    data = load_existing()
    all_archetypes = list(data.keys())

    if args.archetypes:
        targets = [a.strip() for a in args.archetypes.split(",")]
        # Add any new archetypes not yet in data
        for t in targets:
            if t not in data:
                data[t] = []
    else:
        targets = all_archetypes

    print(f"Updating {len(targets)} archetype(s), max {args.max_decks} decks each.")
    print("=" * 60)

    updated_count = 0
    for i, arch in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {arch}")
        existing = data.get(arch, [])
        before = len(existing)
        data[arch] = update_archetype(arch, existing, args.max_decks)
        after = len(data[arch])
        if after > before:
            updated_count += after - before
        # Save after each archetype in case of interruption
        save(data)

    print(f"\n{'='*60}")
    print(f"Done. Added {updated_count} new deck(s) across {len(targets)} archetype(s).")
    print(f"Saved to {DATA_PATH}")

if __name__ == "__main__":
    main()
