"""
Update decklists.json using Playwright browser.
Otevře Chrome, ty projdeš Cloudflare challenge, pak skript převezme session.

Usage: python update_decklists_browser.py [--archetypes "Psychatog,Burn"] [--max-decks 20]
"""
import sys
import json
import time
import argparse
import re
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

DATA_PATH = "data/decklists.json"
BASE_URL = "https://mtgdecks.net"

VALID_RANKS = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th",
               "top 4", "top 8", "top4", "top8", "1", "2", "3", "4", "5", "6", "7", "8"]

def load_existing():
    try:
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save(data):
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def arch_to_slug(name):
    slug = name.lower().replace("/", "-").replace(" ", "-")
    mapping = {
        "blue-black-psychatog": "psychatog",
        "landstill": "uw-standstill",
        "elfball": "elves",
        "sligh": "sligh",
    }
    return mapping.get(slug, slug)

def wait_for_human(page, url):
    """Navigate to URL and wait for user to pass any challenge."""
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    # If Cloudflare challenge detected, wait for user to solve it
    for _ in range(30):  # up to 30 seconds
        content = page.content()
        if "Just a moment" in content or "challenge" in page.url:
            print("  [!] Cloudflare challenge detected — solve it in the browser...")
            time.sleep(2)
        else:
            break
    time.sleep(1)
    return page.content()

def scrape_top_decks(page, arch, max_decks=20):
    slug = arch_to_slug(arch)
    existing_urls = set()
    top_decks = []

    for page_num in range(1, 6):
        url = f"{BASE_URL}/Premodern/{slug}/page:{page_num}"
        print(f"  Fetching: {url}")
        html = wait_for_human(page, url)
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="clickable")
        if not table:
            break

        rows = table.find_all("tr")
        if len(rows) <= 1:
            break

        found_any = False
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 8:
                continue
            try:
                rank_text = cols[0].get_text(strip=True).split("(")[0].strip()
                player_td = cols[2]
                deck_link = player_td.find("a")
                deck_url = deck_link["href"] if deck_link else ""
                if not deck_url:
                    continue
                if not deck_url.startswith("http"):
                    deck_url = BASE_URL + deck_url
                if deck_url in existing_urls:
                    continue

                strong_tag = player_td.find("strong")
                player = strong_tag.get_text(strip=True).replace("By", "").strip() if strong_tag else "Unknown"
                event = cols[5].get_text(strip=True)
                players_text = cols[7].get_text(strip=True)
                players = int(re.sub(r"\D", "", players_text)) if re.sub(r"\D", "", players_text) else 0
                date_text = cols[9].get_text(separator=" ", strip=True) if len(cols) > 9 else ""

                color_td = cols[3]
                colors_list = []
                for span in color_td.find_all("span", class_="ms-cost"):
                    for cls in span.get("class", []):
                        if cls.startswith("ms-") and len(cls) == 4 and cls != "ms-cost":
                            colors_list.append(cls.replace("ms-", "").upper())

                spice_td = cols[8] if len(cols) > 8 else None
                spice_val = 0
                if spice_td:
                    spice_bar = spice_td.find("div", class_="progress-bar")
                    spice_val = int(spice_bar["aria-valuenow"]) if spice_bar and "aria-valuenow" in spice_bar.attrs else 0

                rank_lower = rank_text.lower()
                is_top_8 = any(r == rank_lower or rank_lower.startswith(r) for r in VALID_RANKS)

                if players == 0:
                    match_record = re.match(r"^(\d+)-(\d+)(?:-(\d+))?$", rank_text)
                    if match_record:
                        wins = int(match_record.group(1))
                        losses = int(match_record.group(2))
                        draws = int(match_record.group(3)) if match_record.group(3) else 0
                        total_rounds = wins + losses + draws
                        if total_rounds >= 8: players = 129
                        elif total_rounds == 7: players = 65
                        elif total_rounds == 6: players = 33
                        elif total_rounds == 5: players = 17
                        elif total_rounds == 4: players = 9
                        elif total_rounds == 3: players = 4
                        if wins >= 3 and losses == 0:
                            is_top_8 = True

                if players >= 50 and is_top_8:
                    top_decks.append({
                        "player": player,
                        "rank": rank_text,
                        "players": players,
                        "event": event,
                        "date": date_text,
                        "colors": colors_list,
                        "spice": spice_val,
                        "url": deck_url,
                    })
                    existing_urls.add(deck_url)
                    found_any = True

            except Exception as e:
                print(f"  [!] Row parse error: {e}")
                continue

        if not found_any or len(top_decks) >= max_decks:
            break

    return top_decks[:max_decks]


def scrape_decklist(page, url):
    print(f"    -> Fetching decklist: {url}")
    html = wait_for_human(page, url)
    soup = BeautifulSoup(html, "html.parser")

    cards = []
    current_section = "Maindeck"
    current_type = "Other"

    for elem in soup.find_all(["th", "tr"]):
        if elem.name == "th":
            header_text = elem.get_text(strip=True)
            if "Sideboard" in header_text:
                current_section = "Sideboard"
                current_type = "Sideboard"
            elif header_text:
                current_type = header_text
        elif elem.name == "tr" and "cardItem" in elem.get("class", []):
            qty = elem.get("data-required")
            name = elem.get("data-card-id")
            if qty and name:
                try:
                    cards.append({
                        "qty": int(qty),
                        "name": name,
                        "section": current_section,
                        "type": current_type,
                    })
                except ValueError:
                    continue

    return cards


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--archetypes", help="Comma-separated archetypes (default: all)")
    parser.add_argument("--max-decks", type=int, default=20)
    args = parser.parse_args()

    data = load_existing()

    if args.archetypes:
        targets = [a.strip() for a in args.archetypes.split(",")]
        for t in targets:
            if t not in data:
                data[t] = []
    else:
        targets = list(data.keys())

    print(f"Updating {len(targets)} archetype(s) via browser.")
    print("NOTE: If Cloudflare challenge appears, solve it in the browser window.")
    print("=" * 60)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False, slow_mo=200)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        )
        page = context.new_page()

        # Warm up — visit homepage so user can solve any initial challenge
        print("\nOpening mtgdecks.net — solve any Cloudflare challenge in the browser...")
        wait_for_human(page, "https://mtgdecks.net/Premodern")
        input("\nPress Enter when the page is loaded and challenge is solved...")

        added_total = 0
        for i, arch in enumerate(targets, 1):
            print(f"\n[{i}/{len(targets)}] {arch}")
            existing = data.get(arch, [])
            existing_urls = {d["url"] for d in existing}

            top_decks = scrape_top_decks(page, arch, args.max_decks)
            new_decks = [d for d in top_decks if d["url"] not in existing_urls]
            print(f"  Found {len(top_decks)} total, {len(new_decks)} new")

            updated = list(existing)
            for deck in new_decks:
                cards = scrape_decklist(page, deck["url"])
                main_count = sum(c["qty"] for c in cards if c["section"] != "Sideboard")
                side_count = sum(c["qty"] for c in cards if c["section"] == "Sideboard")
                print(f"    -> {main_count} main + {side_count} side")
                deck["cards"] = cards
                updated.append(deck)
                added_total += 1
                time.sleep(0.3)

            data[arch] = updated[:args.max_decks]
            save(data)

        browser.close()

    print(f"\n{'='*60}")
    print(f"Done. Added {added_total} new deck(s).")
    print(f"Saved to {DATA_PATH}")


if __name__ == "__main__":
    main()
