import pandas as pd
import numpy as np
import json
import os
from scipy.stats import norm
import streamlit as st

@st.cache_data(ttl=3600, show_spinner=False)
def load_period_data(data_dir, period):
    matrix_path = os.path.join(data_dir, f"{period}.json")
    with open(matrix_path, 'r', encoding='utf-8') as f:
        matrix_data = json.load(f)

    # Merge "Oath Control" into "Oath"
    if "matrix" in matrix_data:
        m = matrix_data["matrix"]
        if "Oath Control" in m:
            o_ctrl = m.pop("Oath Control")
            if "Oath" not in m:
                m["Oath"] = {}
            for opp, stats in o_ctrl.items():
                if opp not in m["Oath"]:
                    m["Oath"][opp] = stats
                else:
                    e = m["Oath"][opp]
                    e["wins"] += stats.get("wins", 0)
                    e["losses"] += stats.get("losses", 0)
                    e["total_matches"] += stats.get("total_matches", 0)
                    if e["total_matches"] > 0:
                        e["win_rate"] = (e["wins"] + e.get("draws", 0)*0.5) / e["total_matches"]

        if "archetypes" in matrix_data:
            matrix_data["archetypes"] = [a for a in matrix_data["archetypes"] if a != "Oath Control"]
            if "Oath" not in matrix_data["archetypes"]:
                matrix_data["archetypes"].append("Oath")
                matrix_data["archetypes"].sort()

        for arch in m:
            matchups = m[arch]
            if "Oath Control" in matchups:
                stats = matchups.pop("Oath Control")
                if "Oath" not in matchups:
                    matchups["Oath"] = stats
                else:
                    e = matchups["Oath"]
                    e["wins"] += stats.get("wins", 0)
                    e["losses"] += stats.get("losses", 0)
                    e["total_matches"] += stats.get("total_matches", 0)
                    if e["total_matches"] > 0:
                        e["win_rate"] = (e["wins"] + e.get("draws", 0)*0.5) / e["total_matches"]

    records_data = []
    for arch, matchups in matrix_data.get("matrix", {}).items():
        wins, losses, draws, matches = 0, 0, 0, 0
        for opp, stats in matchups.items():
            wins += stats.get("wins", 0)
            losses += stats.get("losses", 0)
            matches += stats.get("total_matches", 0)
        if matches > 0:
            records_data.append({
                "archetype": arch,
                "wins": wins,
                "losses": losses,
                "draws": draws,
                "total_matches": matches,
                "win_rate": (wins + draws*0.5) / matches
            })

    # Merge "Oath Control" in meta_shares and tiers
    if "meta_shares" in matrix_data:
        shares = matrix_data["meta_shares"]
        if "Oath Control" in shares:
            shares["Oath"] = shares.get("Oath", 0) + shares.pop("Oath Control")
        matrix_data["meta_shares"] = {k.upper(): v for k, v in shares.items()}

    if "tiers" in matrix_data:
        tiers = matrix_data["tiers"]
        if "Oath Control" in tiers:
            o_ctrl_tier = tiers.pop("Oath Control")
            if "Oath" not in tiers or o_ctrl_tier < tiers["Oath"]:
                tiers["Oath"] = o_ctrl_tier

    return matrix_data, records_data

def wilson_score_interval(wins, total, confidence=0.95):
    """Calculate the Wilson score interval for a binomial proportion."""
    if total == 0:
        return 0, 0
    
    z = norm.ppf(1 - (1 - confidence) / 2)
    p = wins / total
    
    denom = 1 + z**2 / total
    centre_adj = p + z**2 / (2 * total)
    adj_error = z * np.sqrt(p * (1 - p) / total + z**2 / (4 * total**2))
    
    lower = (centre_adj - adj_error) / denom
    upper = (centre_adj + adj_error) / denom
    
    return lower, upper

def get_matchup_stats(matrix_dict, arch1, arch2):
    """Get stats for a specific matchup."""
    row = matrix_dict.get(arch1, {})
    cell = row.get(arch2, {})
    return cell

def calculate_polarity(archetype_name, matrix_dict, all_archetypes):
    """
    Calculate deck polarity: standard deviation of win rates across matchups.
    Excludes self-matchups and matchups with very low sample size.
    """
    win_rates = []
    row_data = matrix_dict.get(archetype_name, {})
    
    for other in all_archetypes:
        if other == archetype_name:
            continue
        
        cell = row_data.get(other, {})
        total = cell.get("total_matches", 0)
        if total >= 5: # Minimum threshold for polarity analysis
            win_rates.append(cell.get("win_rate", 0))
            
    if not win_rates:
        return 0
    
    return np.std(win_rates)

def calculate_expected_winrate(meta_shares, matrix_dict, all_archetypes):
    """
    Calculate target deck winrates based on expected field composition.
    meta_shares: dict {archetype: share_percentage (0-1)}
    """
    ev_results = {}
    
    for target in all_archetypes:
        expected_wr = 0
        total_share = 0
        
        for opponent, share in meta_shares.items():
            if share <= 0:
                continue
                
            cell = matrix_dict.get(target, {}).get(opponent, {})
            wr = cell.get("win_rate", 0.5) # Default to 50% if no data
            expected_wr += wr * share
            total_share += share
            
        if total_share > 0:
            ev_results[target] = expected_wr / total_share
            
    return ev_results

def get_period_comparison(data_dir, periods_dict):
    """
    Compare all archetypes across different timeframes.
    Returns a DataFrame with win rates per period.
    """
    all_data = []
    
    for display_name, internal_key in periods_dict.items():
        try:
            _, records = load_period_data(data_dir, internal_key)
            for rec in records:
                all_data.append({
                    "Archetype": rec["archetype"],
                    "Period": display_name,
                    "Win Rate": rec.get("win_rate", 0),
                    "Games": rec.get("total_matches", 0)
                })
        except Exception as e:
            print(f"Error loading {internal_key}: {e}")
            
    df = pd.DataFrame(all_data)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
        
    # Due to archetype mapping, we might have multiple entries for the same Archetype + Period.
    # We must aggregate them (e.g., sum games, weighted average for win rate).
    
    # Calculate total wins to accurately average win_rate
    df["Wins"] = df["Win Rate"] * df["Games"]
    
    grouped = df.groupby(["Archetype", "Period"]).agg({
        "Games": "sum",
        "Wins": "sum"
    }).reset_index()
    
    grouped["Win Rate"] = grouped["Wins"] / grouped["Games"]
    grouped["Win Rate"] = grouped["Win Rate"].fillna(0)
    
    pivot_df = grouped.pivot(index="Archetype", columns="Period", values="Win Rate")
    games_df = grouped.pivot(index="Archetype", columns="Period", values="Games").fillna(0)
    
    return pivot_df, games_df

# Mapping of Archetypes to Defining Cards for Visuals
DECK_CARD_MAP = {
    "Stasis": "Stasis",
    "Goblins": "Goblin Lackey",
    "Sligh": "Jackal Pup",
    "Survival": "Survival of the Fittest",
    "The Deck": "Jayemdae Tome",
    "Landstill": "Standstill",
    "Pox": "Pox",
    "Psychatog": "Psychatog",
    "Madness": "Arrogant Wurm",
    "Reanimator": "Reanimate",
    "Elves": "Llanowar Elves",
    "Burn": "Lightning Bolt",
    "Oath": "Oath of Druids",
    "Oath Spec": "Quiet Speculation",
    "Storm": "Brain Freeze",
    "Mono Black": "Dark Ritual",
    "Fluctuator": "Fluctuator",
    "Mono Black Ponza": "Rain of Tears",
    "Delver": "Delver of Secrets",
    "Death & Taxes": "Thalia, Guardian of Thraben",
    "Miracles": "Terminus",
    "Infect": "Glistener Elf",
    "Merfolk": "Lord of Atlantis",
    "Zoo": "Wild Nacatl",
    "Control": "Counterspell",
    "Aggro": "Tarmogoyf",
    "Combo": "Dark Ritual",
    "High Tide": "High Tide",
    "Replenish": "Replenish",
    "Tinker": "Tinker",
    "Suicide Black": "Carnophage",
    "Mono White Control": "Eternal Dragon",
    "White Weenie": "Savannah Lions",
    "Tempting Rack": "Tempting Wurm",
    "Stiflenought": "Phyrexian Dreadnought"
}

def get_card_image_url(archetype_name):
    """Get the Scryfall image URL for a defining card of the archetype."""
    card_name = DECK_CARD_MAP.get(archetype_name, archetype_name)
    # Using Scryfall's direct image API: https://scryfall.com/docs/api/cards/named?format=image
    # We use format=image and version=normal
    import urllib.parse
    encoded_name = urllib.parse.quote(card_name)
    return f"https://api.scryfall.com/cards/named?exact={encoded_name}&format=image&version=normal"
