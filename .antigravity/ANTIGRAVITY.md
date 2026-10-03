# ANTIGRAVITY.md (Long-Term RAM)

## 1. Context Monitor (Current Status)
*   **Status**: Active — projekt funkční, připraven na měsíční update 2026-05-01.
*   **Date**: 2026-04-29
*   **Recent Changes**: Streamlit funkční lokálně (port 8502), plotly doinstalován, CLAUDE.md aktualizován.
*   **Open Blockers**: Nezkomitované změny na `main` (viz git status) — je třeba commitnout před 1. 5.

## 2. Tech Stack & Dependencies
*   **Python**: 3.13 (lokálně)
*   **Framework**: Streamlit
*   **Data Analysis**: Pandas, NumPy, SciPy
*   **Visualizations**: Plotly (Heatmaps, Scatter Plots)
*   **Scraping**: BeautifulSoup, Playwright (pro Cloudflare bypass)
*   **Deployment**: Streamlit Cloud (GitHub `main` branch)
*   **Data Sources**: MTGDecks.net (Primary), Duress Crew (Legacy/Historic)
*   **Assets**: Scryfall Art Crops (Icons), Base64 Mana Symbols

## 3. Decision Log

### 2026-02-27: Data Architecture (v1.0)
*   **Source Fusion**: Decided to merge Duress Crew (win rate tables) with MTGDecks (meta share & tiers).
*   **Normalization**: Centralized mapping logic in `src/mappings.py` to resolve inconsistent archetype names.
*   **Caching**: Implemented `st.cache_data(ttl=3600)` in `app.py` for performance.

### 2026-04-09: Agentic Blueprint (v1.1)
*   **Bootstrap**: Initialized the Antigravity Agentic Blueprint.
*   **Deployment Protocol**: Established MANDATORY Localhost-First rule.

### 2026-04-29: Pre-May Update Audit
*   **Playwright scraper**: `update_decklists_browser.py` je primární nástroj pro decklists update (obchází Cloudflare). `update_decklists.py` (urllib) funguje pouze s VPN.
*   **Syntéza dat**: 90_days a 210_days se syntetizují z historical backupů — dubnový backup (`data/historical/2026-04-01/`) je připraven a obsahuje `60_days` + `180_days`.
*   **plotly**: Chyběl v lokálním prostředí, doinstalován (`pip install plotly`).

## 4. Key Architectural Knowledge (CRITICAL)

### Timeframe Mapping
Internal data keys for `app.py`:
*   `9M` → `mtgdecks_matrix_210_days`
*   `6M` → `mtgdecks_matrix_180_days`
*   `3M` → `mtgdecks_matrix_90_days`

### Co se fetchuje vs. syntetizuje
*   **Přímo fetchováno**: `30_days`, `60_days`, `180_days`
*   **Syntetizováno**: `90_days` = prev_60_days + cur_30_days; `210_days` = prev_180_days + cur_30_days
*   Syntéza čte z `data/historical/[předchozí měsíc]/`

### Data Structure (`matrix_data`)
```python
{
  "archetypes": ["Burn", "Goblins", ...],
  "tiers": {"Burn": "Tier 1", ...},
  "matrix": {
    "Burn": {
      "Goblins": {"wins": 50, "losses": 40, "win_rate": 0.543}
    }
  },
  "meta_shares": {"BURN": 0.0802, ...} # Keys are UPPERCASE
}
```

### Specific Logic & "Gotchas"
*   **Oath Merge**: "Oath Control" is manually merged into "Oath" in `load_period_data`.
*   **Wilson Confidence**: Matchup reliability = Wilson score interval (95% confidence).
*   **403 bez VPN**: urllib scraper vrací 403 — pro Cloudflare bypass použít `update_decklists_browser.py` (Playwright).
*   **Card Mapping**: `DECK_CARD_MAP` in `src/analytics.py` defines which MTG card represents which archetype.

### Data Layer Reference
*   **Duress Layer**: Manual tournament exports. Files: `archetype_matrix_[period].json`, `win_loss_records_[period].json`.
*   **Scrape Layer**: Automated MTGDecks extraction. Files: `mtgdecks_matrix_[period].json`.
*   **Composition**: `load_period_data` merges these layers, normalizing names via `mappings.py`.

### Script Inventory
*   `scripts/update_data_monthly.py`: Hlavní měsíční ingestion (Playwright/Chrome CDP).
*   `update_decklists_browser.py`: Decklists update přes Playwright (preferovaný).
*   `update_decklists.py`: Decklists update přes urllib (vyžaduje VPN).
*   `test_scraper.py`: CLI test scraperu (vyžaduje VPN).
*   `scripts/fetch_deck_icons.py`: Scryfall icon downloader.
*   `scripts/encode_mana_json.py`: SVG-to-Base64 encoder.
*   `scripts/resynthesize_data.py`: Přepočet syntetizovaných period.

## 5. Historical Experience & Patterns

### Technical Standards
*   **CSV Encoding**: Always use **UTF-8 with BOM (`utf-8-sig`)** for CSV exports.
*   **Asset Sourcing**: Base64-encoded SVG icons for mana symbols; Scryfall API for card art.
*   **Atomic saves**: `update_decklists.py` používá `.tmp` + `os.replace()` pro atomic rename.

### Interaction Style
*   **Localhost First**: Never push directly to GitHub. Deploy → User Verification → Git Push.
*   **Adversarial Collaboration**: User values challenging inefficient proposals.
*   **HITL gate**: Changes to `mappings.py`, `analytics.py` core, scrapers, requirements.txt = approval needed.

## 6. 40% Rule Tracker
*   Current Session Interaction Count: 1 (Post-Reset)
*   Next Reset Target: ~15 Interactions

---
*Stay Deterministic. Stay Antigravity.*
