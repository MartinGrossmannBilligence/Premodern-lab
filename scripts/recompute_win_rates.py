"""
Recompute win_rate = wins / total_matches across all JSON data files.
Replaces the scraped integer percentage with our own calculation.
"""
import json
import os
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def recompute_win_rates(matrix):
    changed = 0
    for arch, matchups in matrix.items():
        for opp, stats in matchups.items():
            w = stats.get('wins', 0)
            m = stats.get('total_matches', 0)
            if m > 0:
                new_wr = round(w / m, 4)
                old_wr = stats.get('win_rate', None)
                if old_wr != new_wr:
                    stats['win_rate'] = new_wr
                    changed += 1
            else:
                stats['win_rate'] = 0
    return changed

# Find all JSON files in data/ and data/historical/
patterns = [
    os.path.join(DATA_DIR, 'mtgdecks_matrix_*.json'),
    os.path.join(DATA_DIR, 'historical', '*', 'mtgdecks_matrix_*.json'),
]

all_files = []
for pattern in patterns:
    all_files.extend(glob.glob(pattern))

total_changed = 0
for path in sorted(all_files):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    matrix = data.get('matrix', {})
    if not matrix:
        print(f"  SKIP (no matrix): {os.path.relpath(path, BASE_DIR)}")
        continue

    changed = recompute_win_rates(matrix)
    total_changed += changed

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

    rel = os.path.relpath(path, BASE_DIR)
    print(f"  {'+' if changed else ' '} {rel}  ({changed} cells updated)")

print(f"\nDone. Total cells updated: {total_changed}")
