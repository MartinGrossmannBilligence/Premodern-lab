import sys
import os
import pandas as pd

# Add the project root to sys.path
sys.path.append(os.getcwd())

from src.analytics import load_period_data

DATA_DIR = "data"
TIMEFRAMES = {
    "9M": "mtgdecks_matrix_210_days",
    "3M": "mtgdecks_matrix_90_days"
}

def analyze():
    # Load 9M data
    _, records_9m = load_period_data(DATA_DIR, TIMEFRAMES["9M"])
    records_92_df = pd.DataFrame(records_9m)
    records_92_df = records_92_df.rename(columns={"win_rate": "WR_9M", "total_matches": "Games_9M"})
    
    # Load 3M data
    _, records_3m = load_period_data(DATA_DIR, TIMEFRAMES["3M"])
    records_33_df = pd.DataFrame(records_3m)
    records_33_df = records_33_df.rename(columns={"win_rate": "WR_3M", "total_matches": "Games_3M"})
    
    # Merge
    comparison = pd.merge(records_92_df[["archetype", "WR_9M", "Games_9M"]], 
                          records_33_df[["archetype", "WR_3M", "Games_3M"]], 
                          on="archetype", how="inner")
    
    # Calculate difference
    comparison["WR_Diff"] = comparison["WR_3M"] - comparison["WR_9M"]
    
    # Filter for decks with at least 15 games in BOTH periods to ensure significance
    MIN_GAMES = 15
    filtered = comparison[(comparison["Games_9M"] >= MIN_GAMES) & (comparison["Games_3M"] >= MIN_GAMES)].copy()
    
    # Sort
    top_jumpers = filtered.sort_values(by="WR_Diff", ascending=False)
    
    # Report top 10
    top_10 = top_jumpers.head(10)
    
    # Create a nice summary
    for i, row in top_10.iterrows():
        diff_pct = row['WR_Diff'] * 100
        wr_9m_pct = row['WR_9M'] * 100
        wr_3m_pct = row['WR_3M'] * 100
        print(f"{row['archetype']}: {wr_9m_pct:.1f}% -> {wr_3m_pct:.1f}%  (Jump: {diff_pct:+.1f}%) | Games: {int(row['Games_9M'])} / {int(row['Games_3M'])}")

if __name__ == "__main__":
    analyze()
