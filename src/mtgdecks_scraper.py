import urllib.request
import urllib.error
from bs4 import BeautifulSoup
import re
import streamlit as st

@st.cache_data(ttl=86400, show_spinner="Fetching latest decks from mtgdecks.net...")
def get_recent_top_decks(archetype_name, limit=20):
    """
    Scrape mtgdecks.net for the given archetype and return up to `limit` recent decklists
    from tournaments with >= 16 players where the deck made Top 8.
    """
    
    # Map typical names to mtgdecks slugs
    # e.g., "Blue/Black Psychatog" -> "psychatog"
    slug = archetype_name.lower().replace('/', '-').replace(' ', '-')
    
    # Custom mapping for known drift
    mapping = {
        "blue-black-psychatog": "psychatog",
        "the-rock": "the-rock",
        "uw-standstill": "uw-standstill",
        "survival-welder": "survival-welder",
        "stiflenought": "stiflenought",
        "goblins": "goblins",
        "sligh": "sligh",
        "deadguy-ale": "deadguy-ale",
        "burn": "burn",
        "elfball": "elves",
        "landstill": "uw-standstill",  # fallback or guess
        "blue-black-psychatog": "psychatog",
    }
    
    slug = mapping.get(slug, slug)
    
    top_decks = []
    valid_ranks = ["1st", "2nd", "3rd", "4th", "5th", "6th", "7th", "8th", "top 4", "top 8", "1", "2", "3", "4", "5", "6", "7", "8", "top4", "top8"]
    
    for page in range(1, 11):
        url = f"https://mtgdecks.net/Premodern/{slug}/page:{page}"
        
        try:
            import gzip
            
            req = urllib.request.Request(
                url, 
                data=None, 
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1'
                }
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                html_bytes = response.read()
                if response.info().get('Content-Encoding') == 'gzip':
                    html_bytes = gzip.decompress(html_bytes)
                html = html_bytes.decode('utf-8', errors='ignore')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                break # No more pages
            print(f"HTTPError fetching {url}: {e}")
            break
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            break

        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table', class_='clickable')
        if not table:
            break
        
        rows = table.find_all('tr')
        if not rows or len(rows) <= 1:
            break
            
        for row in rows:
            cols = row.find_all('td')
            if len(cols) < 6:
                continue
            
            try:
                # 0: Rank, 1: blank, 2: Player/DeckName, 3: Colors, 4: Format, 5: Event, 6: Level, 7: Players, 8: Spiciness, 9: Date
                rank_text = cols[0].get_text(strip=True).split('(')[0].strip()
                
                player_td = cols[2]
                deck_link = player_td.find('a')
                deck_url = deck_link['href'] if deck_link else ""
                
                strong_tag = player_td.find('strong')
                player = strong_tag.get_text(strip=True).replace('By', '').strip() if strong_tag else "Unknown"
                
                event = cols[5].get_text(strip=True)
                
                players_text = cols[7].get_text(strip=True)
                players = int(re.sub(r'\D', '', players_text)) if players_text and re.sub(r'\D', '', players_text) else 0
                
                date_text = cols[9].get_text(separator=' ', strip=True) # e.g. "21-Feb -2026"
                
                if not deck_url:
                    continue
                    
                # Extract colors
                color_td = cols[3]
                colors_list = []
                for span in color_td.find_all('span', class_='ms-cost'):
                    for cls in span.get('class', []):
                        if cls.startswith('ms-') and len(cls) == 4 and cls != 'ms-cost':
                            colors_list.append(cls.replace('ms-', '').upper())
                
                # Extract spiciness
                spice_td = cols[8]
                spice_bar = spice_td.find('div', class_='progress-bar')
                spice_val = int(spice_bar['aria-valuenow']) if spice_bar and 'aria-valuenow' in spice_bar.attrs else 0
                    
                rank_lower = rank_text.lower()
                is_top_8 = any(r == rank_lower or rank_lower.startswith(r) for r in valid_ranks)
                
                # If players isn't given but we have a match record like "5-0", estimate minimum players
                if players == 0:
                    match_record = re.match(r'^(\d+)-(\d+)(?:-(\d+))?$', rank_text)
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
                        # Strong winning record = top finish
                        # e.g. 5-0, 8-1, 7-1 — win rate >= 80% with at least 4 rounds
                        if losses == 0 and wins >= 3:
                            is_top_8 = True
                        elif total_rounds >= 5 and wins / total_rounds >= 0.80:
                            is_top_8 = True
                    elif is_top_8:
                        # Rank like "1st"/"2nd" but no player count — treat as small event (~16)
                        players = 16

                if players >= 16 and is_top_8:
                    top_decks.append({
                        "player": player,
                        "rank": rank_text,
                        "players": players,
                        "event": event,
                        "date": date_text,
                        "colors": colors_list,
                        "spice": spice_val,
                        "url": "https://mtgdecks.net" + deck_url if not deck_url.startswith('http') else deck_url
                    })
                    
                if len(top_decks) >= limit:
                    break

            except Exception as e:
                print(f"Error parsing row: {e}")
                continue

        if len(top_decks) >= limit:
            break

    # If nothing was found, output a warning for debugging purposes
    if not top_decks:
        print(f"No decks found for {archetype_name} (mapped to slug: {slug})")

    return top_decks

@st.cache_data(ttl=86400, show_spinner=False)
def get_decklist(url):
    """
    Fetch a specific decklist from mtgdecks.net and return its cards.
    Returns: list of dicts {"qty": int, "name": str}
    """
    try:
        import urllib.request, gzip
        from bs4 import BeautifulSoup
        import re
        
        import time
        time.sleep(1) # Be nice to the server to avoid 403 Formbidden
        
        req = urllib.request.Request(
            url, 
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html_bytes = response.read()
            if response.info().get('Content-Encoding') == 'gzip':
                html_bytes = gzip.decompress(html_bytes)
            html = html_bytes.decode('utf-8', errors='ignore')
            
        soup = BeautifulSoup(html, 'html.parser')
        cards = []
        
        # Iterate through tables or rows to find section headers and cards
        current_section = "Maindeck"
        current_type = "Other"
        
        # MTGDecks often organizes by tables or headers
        # We'll look for <th> for headers and <tr> for cards
        all_elements = soup.find_all(['th', 'tr'])
        
        for elem in all_elements:
            if elem.name == 'th':
                header_text = elem.get_text(strip=True)
                if "Sideboard" in header_text:
                    current_section = "Sideboard"
                    current_type = "Sideboard"
                elif header_text:
                    current_type = header_text
            
            elif elem.name == 'tr' and 'cardItem' in elem.get('class', []):
                qty = elem.get('data-required')
                name = elem.get('data-card-id')
                if qty and name:
                    try:
                        cards.append({
                            "qty": int(qty), 
                            "name": name, 
                            "section": current_section,
                            "type": current_type
                        })
                    except ValueError:
                        continue
        
        # Fallback to old behavior if no cardItems found (unlikely with modern site)
        if not cards:
            # Simple fallback logic similar to before but without type info
            number_tds = soup.find_all('td', class_='number')
            for td in number_tds:
                row = td.find_parent('tr')
                if not row: continue
                qty_text = re.sub(r'\D', '', td.get_text(strip=True))
                if not qty_text: continue
                qty = int(qty_text)
                name_tag = row.find('a')
                if name_tag:
                    name = name_tag.get_text(strip=True)
                    cards.append({"qty": qty, "name": name, "section": "Maindeck", "type": "Unknown"})
                
        return cards[:100] # Increase cap to accommodate sideboard
        
    except Exception as e:
        print(f"Error fetching decklist {url}: {e}")
        return []
