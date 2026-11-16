"""
Přegeneruje 210_days (9M) pro daný snapshot aktuální konstrukcí (build_210), bez scrapování.

    210_days = current 180_days + 6M-ago 90_days            (preferováno)
             = current 180_days + (3M-ago 180_days - 3M-ago 90_days)   (fallback)

Vstupy se čtou z data/historical/, takže nevyžaduje VPN ani síť.

Usage: python scripts/resynthesize_210.py [--date 2026-09-01] [--dry-run]
"""
import os
import sys
import json
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.update_data_monthly import (  # noqa: E402
    DATA_DIR, HISTORICAL_DIR, build_210, total_matches_in_matrix, save,
)


def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='Resynthesize 210_days with the current formula')
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-01'),
                        help='Snapshot to rebuild, e.g. 2026-09-01')
    parser.add_argument('--dry-run', action='store_true', help='Only print, do not write')
    parser.add_argument('--no-replace', action='store_true',
                        help='Write only the historical snapshot, not root data files')
    args = parser.parse_args()

    snapshot = datetime.strptime(args.date, '%Y-%m-%d')
    folder_name = snapshot.strftime('%Y-%m-01')
    snap_dir = os.path.join(HISTORICAL_DIR, folder_name)

    cur_180 = load(os.path.join(snap_dir, 'mtgdecks_matrix_180_days.json'))
    end_date = cur_180.get('end_date', snapshot.strftime('%Y-%m-%d'))

    try:
        data_210, source = build_210(cur_180, snapshot.replace(day=1), cur_180.get('tiers', {}), end_date)
    except FileNotFoundError as e:
        print(f"  [!] {e}")
        return 1

    cur_total = total_matches_in_matrix(cur_180.get('matrix', {}))
    new_total = total_matches_in_matrix(data_210['matrix'])

    print(f"Snapshot {folder_name}  (zdroj ctvrtleti: {source})")
    print(f"  current 180d = {cur_total:7}")
    print(f"  tail         = {new_total - cur_total:7}")
    print(f"  novy 210d    = {new_total:7}")

    violations = sum(
        1
        for arch, row in cur_180.get('matrix', {}).items()
        for opp, s in row.items()
        if data_210['matrix'].get(arch, {}).get(opp, {}).get('total_matches', 0) < s.get('total_matches', 0)
    )
    print(f"  bunek s 9M < 6M = {violations}")

    if violations or new_total < cur_total:
        print("  [!] INVARIANT 9M >= 6M PORUSEN - nic se nezapisuje")
        return 1

    if args.dry_run:
        print("  dry-run, nic se nezapisuje")
        return 0

    save(data_210, os.path.join(snap_dir, 'mtgdecks_matrix_210_days.json'))
    print(f"  -> zapsano historical/{folder_name}/")
    if not args.no_replace:
        save(data_210, os.path.join(DATA_DIR, 'mtgdecks_matrix_210_days.json'))
        print("  -> zapsano data/")
    return 0


if __name__ == '__main__':
    sys.exit(main())
