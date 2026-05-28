import json
import re
import os
import gzip
import time
import argparse
import urllib.request
import urllib.error
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
HISTORICAL_DIR = os.path.join(DATA_DIR, 'historical')

SOURCES = [
    ("30_days",  "range:last30days",  "metagame:last-month"),
    ("60_days",  "range:last60days",  "metagame:last-2-months"),
    ("180_days", "range:last180days", "metagame:last-6-months"),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate',
    'Connection': 'keep-alive',
}


def fetch_html(url):
    print(f"  Fetching: {url}")
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read()
            if r.info().get('Content-Encoding') == 'gzip':
                raw = gzip.decompress(raw)
            return raw.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [!] Error fetching {url}: {e}")
        return None


def get_tiers():
    print("Fetching tiers...")
    html = fetch_html('https://mtgdecks.net/Premodern')
    if not html:
        return {}
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', id='allArchetypes')
    if not table:
        return {}
    tier_mapping = {}
    for row in table.find_all('tr'):
        classes = row.get('class', [])
        tier = next((c for c in classes if c.startswith('tier-') and c != 'tier-all'), None)
        if tier:
            cells = row.find_all(['td', 'th'])
            if len(cells) > 1:
                arch_name_tag = cells[1].find('a') or cells[1]
                tier_mapping[arch_name_tag.get_text(strip=True)] = tier.replace('tier-', 'Tier ').title()
    return tier_mapping


def parse_matrix(html, time_frame, tier_mapping, end_date_str):
    if not html:
        return None
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='winrates') or soup.find('table')
    if not table:
        print(f"  [!] No winrate table found for {time_frame}")
        return None

    rows = table.find_all('tr')
    if len(rows) < 2:
        return None

    headers = [c.get_text(strip=True) for c in rows[0].find_all(['td', 'th'])]
    opponents = headers[2:]

    matrix = {}
    archetypes = set()

    for row in rows[1:]:
        cells = row.find_all(['td', 'th'])
        if len(cells) < len(headers):
            continue
        archetype = cells[0].get_text(strip=True)
        if not archetype:
            continue
        archetypes.add(archetype)
        if archetype not in matrix:
            matrix[archetype] = {}

        for i, opp in enumerate(opponents):
            cell_html = str(cells[i + 2])
            m = re.search(r'<b>(\d+)</b><span[^>]*>%</span>\s*<div[^>]*>([\d,]+)\s*matches</div>', cell_html)
            if m:
                win_pct = int(m.group(1)) / 100.0
                matches = int(m.group(2).replace(',', ''))
                wins = round(matches * win_pct)
                matrix[archetype][opp] = {
                    "archetype": opp,
                    "wins": wins,
                    "losses": matches - wins,
                    "draws": 0,
                    "total_matches": matches,
                    "win_rate": round(wins / matches, 4) if matches > 0 else 0,
                }
                archetypes.add(opp)

    return {
        "time_frame": time_frame,
        "end_date": end_date_str,
        "archetypes": sorted(list(archetypes)),
        "tiers": tier_mapping,
        "matrix": matrix,
    }


def parse_meta_shares(html):
    if not html:
        return {}
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table', class_='table-striped')
    if not table:
        return {}
    shares = {}
    for row in table.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) < 3:
            continue
        name_tag = cols[1].find('strong')
        if not name_tag:
            continue
        cell_text = cols[2].get_text(separator=' ', strip=True)
        # MTGDecks cell contains both rounded "9%" (mobile) and decimal "8.75%" — prefer decimal
        decimal_match = re.search(r'(\d+\.\d+)%', cell_text)
        whole_match   = re.search(r'(\d+)%', cell_text)
        m = decimal_match or whole_match
        if m:
            try:
                shares[name_tag.get_text(strip=True)] = float(m.group(1)) / 100.0
            except ValueError:
                pass
    return shares


def merge_matrices(m1, m2):
    if not m1: return m2
    if not m2: return m1
    merged = {}
    for arch in set(list(m1.keys()) + list(m2.keys())):
        merged[arch] = {}
        for opp in set(list(m1.get(arch, {}).keys()) + list(m2.get(arch, {}).keys())):
            s1 = m1.get(arch, {}).get(opp, {"wins": 0, "losses": 0, "total_matches": 0})
            s2 = m2.get(arch, {}).get(opp, {"wins": 0, "losses": 0, "total_matches": 0})
            total_wins = s1.get('wins', 0) + s2.get('wins', 0)
            total_matches = s1.get('total_matches', 0) + s2.get('total_matches', 0)
            if total_matches > 0:
                merged[arch][opp] = {
                    "archetype": opp,
                    "wins": total_wins,
                    "losses": total_matches - total_wins,
                    "draws": 0,
                    "total_matches": total_matches,
                    "win_rate": round(total_wins / total_matches, 4),
                }
    return merged


def total_matches_in_matrix(matrix):
    return sum(s.get('total_matches', 0) for matchups in matrix.values() for s in matchups.values())


def merge_meta_shares(shares_list, matrices_list):
    weights = [max(total_matches_in_matrix(m), 1) for m in matrices_list]
    total_weight = sum(weights)
    all_archs = set(k for s in shares_list for k in s.keys())
    return {arch: sum(s.get(arch, 0.0) * w for s, w in zip(shares_list, weights)) / total_weight for arch in all_archs}


def save(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)


def main():
    parser = argparse.ArgumentParser(description='MTGDecks Monthly Data Update')
    parser.add_argument('--no-replace', action='store_true', help='Do not overwrite root data files, only create historical backup')
    parser.add_argument('--date', help='Override current date for folder naming, e.g. 2026-05-01')
    args = parser.parse_args()

    current_date = datetime.strptime(args.date, '%Y-%m-%d') if args.date else datetime.now()
    folder_name = current_date.strftime('%Y-%m-01')
    end_date_str = current_date.strftime('%Y-%m-%d')
    output_historical_dir = os.path.join(HISTORICAL_DIR, folder_name)
    os.makedirs(output_historical_dir, exist_ok=True)

    print(f"Starting monthly update for {folder_name} (end_date={end_date_str})")
    if args.no_replace:
        print("!!! NO-REPLACE MODE — root data files will NOT be updated !!!")
    print("VPN must be active (MTGDecks blocks requests without VPN).\n")

    tiers = get_tiers()
    print(f"  -> {len(tiers)} archetypes with tiers\n")

    all_data = {}

    for label, wr_path, meta_path in SOURCES:
        print(f"[{label}]")
        time.sleep(1)

        meta_shares = parse_meta_shares(fetch_html(f"https://mtgdecks.net/Premodern/{meta_path}"))
        print(f"  -> {len(meta_shares)} meta shares")
        time.sleep(1)

        data = parse_matrix(
            fetch_html(f"https://mtgdecks.net/Premodern/winrates/{wr_path}"),
            label, tiers, end_date_str
        )

        if not data:
            data = {
                "time_frame": label,
                "end_date": end_date_str,
                "archetypes": sorted(list(meta_shares.keys())),
                "tiers": tiers,
                "matrix": {},
            }

        data["meta_shares"] = meta_shares
        all_data[label] = data

        hist_path = os.path.join(output_historical_dir, f"mtgdecks_matrix_{label}.json")
        save(data, hist_path)

        if not args.no_replace:
            save(data, os.path.join(DATA_DIR, f"mtgdecks_matrix_{label}.json"))
            print(f"  -> Saved to root + historical/{folder_name}/")
        else:
            print(f"  -> Saved to historical/{folder_name}/ only")

    # Synthesize 90_days = prev month 60_days + current 30_days
    print("\nSynthesizing 90_days...")
    first_of_current = current_date.replace(day=1)
    prev_folder_name = (first_of_current - timedelta(days=1)).strftime('%Y-%m-01')
    prev_60_path = os.path.join(HISTORICAL_DIR, prev_folder_name, "mtgdecks_matrix_60_days.json")

    if "30_days" in all_data and os.path.exists(prev_60_path):
        try:
            with open(prev_60_path, 'r', encoding='utf-8') as f:
                prev_60 = json.load(f)
            cur_30 = all_data["30_days"]
            data_90 = {
                "time_frame": "90_days",
                "end_date": end_date_str,
                "archetypes": sorted(set(prev_60.get("archetypes", []) + cur_30.get("archetypes", []))),
                "tiers": tiers,
                "matrix": merge_matrices(prev_60.get("matrix", {}), cur_30.get("matrix", {})),
                "meta_shares": merge_meta_shares(
                    [prev_60.get("meta_shares", {}), cur_30.get("meta_shares", {})],
                    [prev_60.get("matrix", {}), cur_30.get("matrix", {})]
                ),
            }
            save(data_90, os.path.join(output_historical_dir, "mtgdecks_matrix_90_days.json"))
            if not args.no_replace:
                save(data_90, os.path.join(DATA_DIR, "mtgdecks_matrix_90_days.json"))
            print(f"  -> OK (merged {prev_folder_name}/60_days + current 30_days)")
        except Exception as e:
            print(f"  [!] Error: {e}")
    else:
        print(f"  [!] Skipped — prev backup not found at {prev_60_path}")

    # Synthesize 210_days = prev month 180_days + current 30_days
    print("\nSynthesizing 210_days...")
    prev_180_path = os.path.join(HISTORICAL_DIR, prev_folder_name, "mtgdecks_matrix_180_days.json")

    if "30_days" in all_data and os.path.exists(prev_180_path):
        try:
            with open(prev_180_path, 'r', encoding='utf-8') as f:
                prev_180 = json.load(f)
            cur_30 = all_data["30_days"]
            data_210 = {
                "time_frame": "210_days",
                "end_date": end_date_str,
                "archetypes": sorted(set(prev_180.get("archetypes", []) + cur_30.get("archetypes", []))),
                "tiers": tiers,
                "matrix": merge_matrices(prev_180.get("matrix", {}), cur_30.get("matrix", {})),
                "meta_shares": merge_meta_shares(
                    [prev_180.get("meta_shares", {}), cur_30.get("meta_shares", {})],
                    [prev_180.get("matrix", {}), cur_30.get("matrix", {})]
                ),
            }
            save(data_210, os.path.join(output_historical_dir, "mtgdecks_matrix_210_days.json"))
            if not args.no_replace:
                save(data_210, os.path.join(DATA_DIR, "mtgdecks_matrix_210_days.json"))
            print(f"  -> OK (merged {prev_folder_name}/180_days + current 30_days)")
        except Exception as e:
            print(f"  [!] Error: {e}")
    else:
        print(f"  [!] Skipped — prev backup not found at {prev_180_path}")

    print("\nUpdate complete.")


if __name__ == "__main__":
    main()
