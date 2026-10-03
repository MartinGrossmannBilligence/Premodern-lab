import json
import os

def get_parfait_data(file_path):
    if not os.path.exists(file_path):
        return None
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    meta_shares = data.get('meta_shares', {})
    parfait_share = meta_shares.get('PARFAIT', 0)
    
    matrix = data.get('matrix', {})
    parfait_matches = matrix.get('Parfait', {})
    
    total_wins = 0
    total_matches = 0
    matchups = []
    
    for opponent, stats in parfait_matches.items():
        if opponent == 'Parfait': continue
        wins = stats.get('wins', 0)
        losses = stats.get('losses', 0)
        total = stats.get('total_matches', 0)
        if total > 0:
            total_wins += wins
            total_matches += total
            matchups.append({
                'opponent': opponent,
                'wins': wins,
                'losses': losses,
                'total': total,
                'wr': wins / total
            })
            
    # Sort matchups by total games
    matchups.sort(key=lambda x: x['total'], reverse=True)
    
    return {
        'share': parfait_share,
        'total_wins': total_wins,
        'total_matches': total_matches,
        'wr': total_wins / total_matches if total_matches > 0 else 0,
        'matchups': matchups[:10] # Top 10 matchups
    }

print("--- 6 Months (180 Days) ---")
data_6m = get_parfait_data('data/mtgdecks_matrix_180_days.json')
if data_6m:
    print(f"Meta Share: {data_6m['share']:.2%}")
    print(f"Overall Win Rate: {data_6m['wr']:.1%} ({data_6m['total_wins']}W - {data_6m['total_matches'] - data_6m['total_wins']}L)")
    print("Top Matchups:")
    for m in data_6m['matchups']:
        print(f"  vs {m['opponent']}: {m['wr']:.1%} ({m['wins']}W - {m['losses']}L, {m['total']} games)")
else:
    print("No data found.")

print("\n--- 3 Months (90 Days) ---")
data_3m = get_parfait_data('data/mtgdecks_matrix_90_days.json')
if data_3m:
    print(f"Meta Share: {data_3m['share']:.2%}")
    print(f"Overall Win Rate: {data_3m['wr']:.1%} ({data_3m['total_wins']}W - {data_3m['total_matches'] - data_3m['total_wins']}L)")
    print("Top Matchups:")
    for m in data_3m['matchups']:
        print(f"  vs {m['opponent']}: {m['wr']:.1%} ({m['wins']}W - {m['losses']}L, {m['total']} games)")
else:
    print("No data found.")
