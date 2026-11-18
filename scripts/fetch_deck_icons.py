"""
Fetch archetype icon art from Scryfall API (old border / Premodern-legal printings preferred).
Saves art_crop images to assets/deck_icons/<archetype_slug>.jpg
"""
import urllib.request
import json
import os
import time

ICONS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "deck_icons")
os.makedirs(ICONS_DIR, exist_ok=True)

# Map archetype name -> iconic card name
# If the deck IS a card name, it maps to itself.
ARCHETYPE_TO_CARD = {
    "5 Color Control": "Vindicate",
    "Aluren": "Aluren",
    "Angry Hermit": "Deranged Hermit",
    "Astral Slide": "Astral Slide",
    "BUG Control": "Pernicious Deed",
    "BW Control": "Gerrard's Verdict",
    "Balancing Tings": "Balancing Act",
    "Broccoli Soup": "Quirion Dryad",
    "Burn": "Lightning Bolt",
    "Cephalid Breakfast": "Cephalid Illusionist",
    "Clerics": "Rotlung Reanimator",
    "Contamination": "Contamination",
    "Deadguy Ale": "Vindicate",
    "Devourer Combo": "Phyrexian Devourer",
    "Doomsday": "Doomsday",
    "Draco Blast": "Draco",
    "Dragonstorm": "Dragonstorm",
    "Dream Halls": "Dream Halls",
    "Dreams Ponza": "Burning Wish",
    "Dredgeless Dredge": "Ichorid",
    "Elves": "Llanowar Elves",
    "Enchantress": "Argothian Enchantress",
    "Fires": "Fires of Yavimaya",
    "Fluctuator": "Fluctuator",
    "Form of Dragon": "Form of the Dragon",
    "Full English Breakfast": "Volrath's Shapeshifter",
    "GR Aggro": "Kird Ape",
    "GW Aggro": "Swords to Plowshares",
    "GW Madness": "Arrogant Wurm",
    "GW Midrange": "Call of the Herd",
    "GWR Aggro": "Wild Mongrel",
    "Goblins": "Goblin Lackey",
    "Great Combo": "Cunning Wish",
    "Gro-a-Tog": "Quirion Dryad",
    "Iggy Pop": "Ill-Gotten Gains",
    "Jund": "Spiritmonger",
    "Lands": "Exploration",
    "Landstill": "Standstill",
    "Life": "Test of Endurance",
    "MUD": "Metalworker",
    "Machine Head": "Phyrexian Arena",
    "Madness": "Basking Rootwalla",
    "Manabond": "Manabond",
    "Merfolks": "Lord of Atlantis",
    "Minotaurs": "Didgeridoo",
    "Mono Black": "Dark Ritual",
    "Mono Black Ponza": "Rain of Tears",
    "Mono Blue Control": "Counterspell",
    "Mono Blue Flyers": "Spiketail Hatchling",
    "Mono Green Order": "Natural Order",
    "Mono Green Stompy": "Rogue Elephant",
    "Mono White Control": "Eternal Dragon",
    "Oath": "Oath of Druids",
    "Oath Control": "Oath of Druids",
    "Oath Ponza": "Oath of Druids",
    "Oath Spec": "Oath of Druids",
    "Pandeburst Control": "Pandemonium",
    "Pattern Combo": "Pattern of Rebirth",
    "Pit Rack": "Bottomless Pit",
    "Ponza": "Stone Rain",
    "Pox": "Pox",
    "Psychatog": "Psychatog",
    "Pyrostatic Oath": "Pyrostatic Pillar",
    "RW Aggro": "Lightning Helix",
    "Reanimator": "Reanimate",
    "Rebels": "Lin Sivvi, Defiant Hero",
    "Replenish": "Replenish",
    "Slivers": "Crystalline Sliver",
    "Sneak Attack": "Sneak Attack",
    "Soldiers": "Daru Warchief",
    "Spec Midrange": "Spectral Lynx",
    "Stasis": "Stasis",
    "Stiflenought": "Phyrexian Dreadnought",
    "Storm": "Brain Freeze",
    "Suicide": "Carnophage",
    "Survival": "Survival of the Fittest",
    "Survival Infestation": "Survival of the Fittest",
    "Survival Opposition": "Opposition",
    "Survival Rock": "Survival of the Fittest",
    "Survival Welder": "Goblin Welder",
    "Tempting Rack": "Tempting Wurm",
    "Terrageddon": "Terravore",
    "The Rack": "The Rack",
    "The Rock": "Pernicious Deed",
    "The Solution": "Meddling Mage",
    "Threshold": "Nimble Mongoose",
    "Tide Control": "High Tide",
    "Tinker Welder": "Tinker",
    "Tireless Tribe Combo": "Tireless Tribe",
    "Tron": "Urza's Tower",
    "UB Control": "Undermine",
    "UR Control": "Fire // Ice",
    "UW Control": "Absorb",
    "UW Midrange": "Mystic Enforcer",
    "UW Prison": "Solitary Confinement",
    "UWB Control": "Vindicate",
    "UWG Control": "Mystic Enforcer",
    "White Weenie": "Savannah Lions",
    "Zombie Infestation": "Zombie Infestation",
    "Zombies": "Sarcomancy",
    "Zoo": "Kird Ape",
    "Oath Spec": "Quiet Speculation",
    # --- added 2026-11 (archetypes that appeared in MTGDecks data without an icon) ---
    "4 Color Control": "Fact or Fiction",
    "4 Color Solution": "Meddling Mage",
    "4 Color Threshold": "Werebear",
    "5 Color Aggro": "Flametongue Kavu",
    "Abzan Control": "Pernicious Deed",
    "Altar of Dementia": "Altar of Dementia",
    "Angels": "Exalted Angel",
    "BR Cycling Rift": "Undead Gladiator",
    "BW Aggro": "Phyrexian Negator",
    "BW Discard": "Hymn to Tourach",
    "BWG Control": "Pernicious Deed",
    "Battle of Wits": "Battle of Wits",
    "Beasts": "Ravenous Baloth",
    "Big Red": "Rathi Dragon",
    "Birds": "Battle Screech",
    "Blessing Control": "Wrath of God",
    "Bösium Storm": "Bösium Strip",
    "Cats": "Savannah Lions",
    "Covetous MUD": "Covetous Dragon",
    "Draco Zoo": "Draco",
    "Druids": "Rofellos, Llanowar Emissary",
    "Dwarfs": "Dwarven Recruiter",
    "False Cure": "False Cure",
    "Frenetic Encounter": "Frenetic Efreet",
    "GR Madness": "Fiery Temper",
    "GW Control": "Armageddon",
    "GW Oatmeal": "Oath of Druids",
    "Gamekeeper": "Gamekeeper",
    "Goblin Welder": "Goblin Welder",
    "Green Weenie": "River Boa",
    "Horrors": "Grinning Demon",
    "Intruder Alarm": "Intruder Alarm",
    "Kavus Aggro": "Flametongue Kavu",
    "Living Slide": "Living Wish",
    "Madness Tribe": "Tireless Tribe",
    "Magnivore": "Magnivore",
    "Mercenaries": "Rathi Assassin",
    "Mon Blue Bounce": "Man-o'-War",
    "Mono Black Coffers": "Cabal Coffers",
    "Mono Black Control": "Corrupt",
    "Mono Black Discard": "Duress",
    "Mono Green": "Blastoderm",
    "Mono Green Control": "Plow Under",
    "Mono White Tron": "Decree of Justice",
    "Nic Fit": "Veteran Explorer",
    "Oath Burn": "Oath of Druids",
    "Oath Tron": "Oath of Druids",
    "Oath and Tell": "Show and Tell",
    "Opposition": "Opposition",
    "Parfait": "Land Tax",
    "Phyrexian Tyranny": "Phyrexian Tyranny",
    "RW Rift": "Lightning Rift",
    "Rogue": "Brainstorm",
    "Super Gro": "Quirion Dryad",
    "Tainted Pact": "Tainted Pact",
    "Trix": "Illusions of Grandeur",
    "Turbo Fog": "Moment's Peace",
    "UBr Control": "Recoil",
    "UR Landstill": "Standstill",
    "UW Aggro": "Soltari Priest",
    "UW Familiar": "Sunscape Familiar",
    "UW Glasses": "Decree of Justice",
    "UWR Control": "Lightning Angel",
    "Upheaval Oath": "Upheaval",
    "WGu Aggro": "Armadillo Cloak",
    "Wake Control": "Mirari's Wake",
    "Welder Stax": "Smokestack",
    "White Enchantments": "Worship",
    "Wildfire": "Wildfire",
    "Wurms": "Roar of the Wurm",
}

def fetch_scryfall_art(card_name):
    """Fetch art_crop URL from Scryfall, preferring old frame printings."""
    # Search for the card with prefer-oldest to get old border art
    query = urllib.parse.quote(card_name)
    url = f"https://api.scryfall.com/cards/named?fuzzy={query}"
    
    req = urllib.request.Request(url, headers={"User-Agent": "MTGMetaDashboard/1.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode("utf-8"))
        
        # Try to get the prints search URI to find old frame version
        prints_url = data.get("prints_search_uri", "")
        if prints_url:
            # Add frame filter for old border
            prints_url += "&q=frame:old"
            req2 = urllib.request.Request(prints_url, headers={"User-Agent": "MTGMetaDashboard/1.0"})
            try:
                with urllib.request.urlopen(req2, timeout=15) as r2:
                    prints_data = json.loads(r2.read().decode("utf-8"))
                    if prints_data.get("data"):
                        old_card = prints_data["data"][0]
                        art_url = old_card.get("image_uris", {}).get("art_crop")
                        if art_url:
                            return art_url
            except Exception:
                pass
        
        # Fallback to whatever Scryfall gives us
        art_url = data.get("image_uris", {}).get("art_crop")
        return art_url
        
    except Exception as e:
        print(f"  Error fetching {card_name}: {e}")
        return None

def download_image(url, filepath):
    """Download image from URL to filepath."""
    req = urllib.request.Request(url, headers={"User-Agent": "MTGMetaDashboard/1.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        with open(filepath, "wb") as f:
            f.write(r.read())

import urllib.parse

def main():
    print(f"Downloading art for {len(ARCHETYPE_TO_CARD)} archetypes...")
    
    # Track which cards we've already downloaded to avoid duplicates
    downloaded_cards = {}
    
    for archetype, card_name in sorted(ARCHETYPE_TO_CARD.items()):
        slug = archetype.lower().replace(" ", "_").replace("/", "_").replace("'", "")
        filepath = os.path.join(ICONS_DIR, f"{slug}.jpg")
        
        if os.path.exists(filepath):
            print(f"  [skip] {archetype} -> already exists")
            continue
        
        print(f"  {archetype} -> {card_name}")
        
        # If we already downloaded this card for another archetype, just copy it
        if card_name in downloaded_cards:
            import shutil
            shutil.copy2(downloaded_cards[card_name], filepath)
            print(f"    [copied from previous]")
            continue
        
        art_url = fetch_scryfall_art(card_name)
        if art_url:
            try:
                download_image(art_url, filepath)
                downloaded_cards[card_name] = filepath
                print(f"    [OK] saved")
            except Exception as e:
                print(f"    [FAIL] {e}")
        else:
            print(f"    [FAIL] no art found")
        
        # Scryfall asks for 75ms between requests
        time.sleep(0.1)
    
    print(f"\nDone! Icons saved to {ICONS_DIR}")

if __name__ == "__main__":
    main()
