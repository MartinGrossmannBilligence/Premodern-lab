"""
Resynthesize 90_days and 210_days JSON files from existing historical backups
using match-count-weighted meta shares (instead of the old month-count weighting).
"""
import json
import os
import sys

# Add project root to path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.update_data_monthly import merge_matrices, merge_meta_shares

DATA_DIR = os.path.join(BASE_DIR, 'data')
HIST_DIR = os.path.join(DATA_DIR, 'historical')

def load(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save(data, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
    print(f"  Saved: {path}")

def total_matches(matrix):
    return sum(
        stats.get('total_matches', 0)
        for arch in matrix.values()
        for stats in arch.values()
    )

# ── Identify the most recent backup (2026-04-01) and previous (2026-03-01) ──
apr = os.path.join(HIST_DIR, '2026-04-01')
mar = os.path.join(HIST_DIR, '2026-03-01')

apr_30  = load(os.path.join(apr, 'mtgdecks_matrix_30_days.json'))
apr_60  = load(os.path.join(apr, 'mtgdecks_matrix_60_days.json'))
apr_180 = load(os.path.join(apr, 'mtgdecks_matrix_180_days.json'))

# ─────────────────────────────────────────────
# Re-synthesize 90_days = prev_60 (march) + cur_30 (april)
# ─────────────────────────────────────────────
mar_60 = load(os.path.join(mar, 'mtgdecks_matrix_60_days.json'))

m_mar60 = total_matches(mar_60.get('matrix', {}))
m_apr30 = total_matches(apr_30.get('matrix', {}))

print(f"\n90_days synthesis:")
print(f"  mar_60 matches: {m_mar60:,}  weight: {m_mar60/(m_mar60+m_apr30):.1%}")
print(f"  apr_30 matches: {m_apr30:,}  weight: {m_apr30/(m_mar60+m_apr30):.1%}")
print(f"  (old weighting was 2:1 = 66.7%/33.3% by months)")

merged_matrix_90 = merge_matrices(mar_60.get('matrix', {}), apr_30.get('matrix', {}))
merged_meta_90   = merge_meta_shares(
    [mar_60.get('meta_shares', {}), apr_30.get('meta_shares', {})],
    [mar_60.get('matrix', {}),      apr_30.get('matrix', {})]
)

data_90 = {
    "time_frame": "90_days",
    "end_date": apr_30.get('end_date', '2026-04-01'),
    "archetypes": sorted(set(mar_60.get('archetypes', []) + apr_30.get('archetypes', []))),
    "tiers": apr_30.get('tiers', {}),
    "matrix": merged_matrix_90,
    "meta_shares": merged_meta_90
}

save(data_90, os.path.join(DATA_DIR, 'mtgdecks_matrix_90_days.json'))
save(data_90, os.path.join(apr, 'mtgdecks_matrix_90_days.json'))

# ─────────────────────────────────────────────
# Re-synthesize 210_days = prev_180 (march) + cur_30 (april)
# ─────────────────────────────────────────────
mar_180 = load(os.path.join(mar, 'mtgdecks_matrix_180_days.json'))

m_mar180 = total_matches(mar_180.get('matrix', {}))

print(f"\n210_days synthesis:")
print(f"  mar_180 matches: {m_mar180:,}  weight: {m_mar180/(m_mar180+m_apr30):.1%}")
print(f"  apr_30  matches: {m_apr30:,}  weight: {m_apr30/(m_mar180+m_apr30):.1%}")
print(f"  (old weighting was 6:1 = 85.7%/14.3% by months)")

merged_matrix_210 = merge_matrices(mar_180.get('matrix', {}), apr_30.get('matrix', {}))
merged_meta_210   = merge_meta_shares(
    [mar_180.get('meta_shares', {}), apr_30.get('meta_shares', {})],
    [mar_180.get('matrix', {}),      apr_30.get('matrix', {})]
)

data_210 = {
    "time_frame": "210_days",
    "end_date": apr_30.get('end_date', '2026-04-01'),
    "archetypes": sorted(set(mar_180.get('archetypes', []) + apr_30.get('archetypes', []))),
    "tiers": apr_30.get('tiers', {}),
    "matrix": merged_matrix_210,
    "meta_shares": merged_meta_210
}

save(data_210, os.path.join(DATA_DIR, 'mtgdecks_matrix_210_days.json'))
save(data_210, os.path.join(apr, 'mtgdecks_matrix_210_days.json'))

print("\nDone! Both 90_days and 210_days files re-synthesized with match-count weighting.")
