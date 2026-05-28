"""
Diagnose why Psychatog win rate in dashboard differs from live MTGDecks.net
"""
import json
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
HIST_DIR = os.path.join(DATA_DIR, 'historical')

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def psychatog_stats(matrix):
    p = matrix.get('Psychatog', {})
    total_w = sum(s.get('wins', 0) for s in p.values())
    total_m = sum(s.get('total_matches', 0) for s in p.values())
    wr = total_w / total_m if total_m else 0
    return total_w, total_m - total_w, total_m, wr

def rounding_error_analysis(matrix):
    """
    MTGDecks gives rounded integer % + match count.
    wins = round(matches * win_pct_integer/100)
    This can introduce systematic rounding bias.
    Max error per matchup = 0.5 wins.
    """
    p = matrix.get('Psychatog', {})
    total_ceil_bias = 0  # cases where we might have rounded up
    total_floor_bias = 0  # cases where we might have rounded down
    max_possible_wins = 0
    min_possible_wins = 0
    actual_wins = 0

    for opp, s in p.items():
        w = s.get('wins', 0)
        m = s.get('total_matches', 0)
        wr = s.get('win_rate', 0)  # this is the integer % / 100
        if m == 0:
            continue
        actual_wins += w
        # True wins could be anywhere from round(m*(wr-0.005)) to round(m*(wr+0.005))
        # since wr is rounded to nearest %
        max_w = min(m, round(m * (wr + 0.005)))
        min_w = max(0, round(m * (wr - 0.005)))
        max_possible_wins += max_w
        min_possible_wins += min_w

    total_m = sum(s.get('total_matches', 0) for s in p.values())
    return actual_wins, min_possible_wins, max_possible_wins, total_m

print("=" * 65)
print("PSYCHATOG WIN RATE ACROSS ALL TIMEFRAMES")
print("=" * 65)

files = [
    ('30d  (apr01)', os.path.join(HIST_DIR, '2026-04-01', 'mtgdecks_matrix_30_days.json')),
    ('60d  (apr01)', os.path.join(HIST_DIR, '2026-04-01', 'mtgdecks_matrix_60_days.json')),
    ('90d  (synth)', os.path.join(DATA_DIR, 'mtgdecks_matrix_90_days.json')),
    ('180d (apr01)', os.path.join(HIST_DIR, '2026-04-01', 'mtgdecks_matrix_180_days.json')),
    ('210d (synth)', os.path.join(DATA_DIR, 'mtgdecks_matrix_210_days.json')),
    ('60d  (mar01)', os.path.join(HIST_DIR, '2026-03-01', 'mtgdecks_matrix_60_days.json')),
    ('180d (mar01)', os.path.join(HIST_DIR, '2026-03-01', 'mtgdecks_matrix_180_days.json')),
]

print(f"\n{'Period':<16} {'Wins':>5} {'Losses':>7} {'Total':>7} {'WR':>7}")
print("-" * 50)
for label, path in files:
    if not os.path.exists(path):
        print(f"{label:<16} FILE NOT FOUND")
        continue
    data = load(path)
    matrix = data.get('matrix', {})
    w, l, m, wr = psychatog_stats(matrix)
    print(f"{label:<16} {w:>5} {l:>7} {m:>7} {wr:>7.1%}")

print()
print("=" * 65)
print("ROUNDING ERROR ANALYSIS (180d apr01)")
print("MTGDecks stores integer % → wins = round(matches * pct/100)")
print("This introduces ±0.5 win rounding per matchup")
print("=" * 65)

data = load(os.path.join(HIST_DIR, '2026-04-01', 'mtgdecks_matrix_180_days.json'))
w, min_w, max_w, total_m = rounding_error_analysis(data.get('matrix', {}))
print(f"\nActual computed wins:    {w}")
print(f"Min possible true wins:  {min_w}  → WR = {min_w/total_m:.1%}")
print(f"Max possible true wins:  {max_w}  → WR = {max_w/total_m:.1%}")
print(f"Total matches:           {total_m}")
print(f"\nRounding can shift WR by up to {(max_w-min_w)/total_m:.2%}")

print()
print("=" * 65)
print("WHY MTGDecks.net shows MORE matches (361 vs 315):")
print("  → Live rolling window ends TODAY (Apr 3)")
print("  → Our data scraped Apr 1 → window ends Apr 1")
print("  → Δ = 2 days of new tournament results")
print("  → If those 2 days had good Psychatog results: WR goes up")
print("=" * 65)

print()
print("MATCHUP BREAKDOWN (180d apr01) - checking for 0% anomalies:")
data = load(os.path.join(HIST_DIR, '2026-04-01', 'mtgdecks_matrix_180_days.json'))
p = data['matrix'].get('Psychatog', {})
zero_wr = [(opp, s['total_matches']) for opp, s in p.items() if s.get('win_rate', 1) == 0.0 and s.get('total_matches',0) > 0]
if zero_wr:
    print(f"  Matchups with 0% WR (drag down avg):")
    for opp, m in sorted(zero_wr, key=lambda x: -x[1]):
        print(f"    vs {opp:<30} {m} matches at 0% → {m} 'lost' wins")
    lost_wins = sum(m for _, m in zero_wr)
    total_m_p = sum(s.get('total_matches',0) for s in p.values())
    print(f"  If these were at 50% instead: +{lost_wins//2} wins → WR would be {(sum(s.get('wins',0) for s in p.values()) + lost_wins//2)/ total_m_p:.1%}")
