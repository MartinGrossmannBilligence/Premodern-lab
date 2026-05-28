# MTG Premodern Lab — Claude Context

## Project Overview
Streamlit dashboard pro analýzu Premodern MTG metagame. Zobrazuje matchup matice, win rate trendy, meta share, decklists a Monte Carlo simulátor.

## Tech Stack
- **Python 3.13** (lokálně), Streamlit, Pandas, Plotly, NumPy, SciPy, BeautifulSoup, Playwright
- **Deployment**: Streamlit Cloud (repo: `MartinGrossmannBilligence/mtg-meta-dashboard`)
- **Data sources**: MTGDecks.net (primary scraping), Duress Crew (legacy exports)

## Spuštění lokálně
```bash
streamlit run app.py
```

## Struktura projektu
```
src/
  analytics.py          # Core agregace, Wilson CI, load_period_data
  mappings.py           # Normalizace názvů archetypů (Duress → MTGDecks)
  mtgdecks_scraper.py   # Scraper decklistů a matchup dat (urllib, bez Playwright)
  ui.py                 # THEME tokeny, CSS, HTML komponenty
  pages/
    meta_overview.py    # Hlavní stránka: scatter, matchup matrix, trendy
    analysis.py         # Matchup polarity, win rate historie
    matrix.py           # Standalone heatmapa
    trends.py           # Historická timeline
    simulator.py        # Monte Carlo simulátor

data/
  decklists.json                    # 103 archetypů, max 20 decklistů každý
  archetype_matrix_[period].json    # Duress layer (1Y/2Y)
  mtgdecks_matrix_[period].json     # Scrape layer (30d–2Y)
  win_loss_records_[period].json    # Záznamy W/L
  archetype_signatures.json         # Karetní signatury archetypů
  historical/
    YYYY-MM-01/                     # Měsíční snapshot (vždy 1. dne měsíce)
      mtgdecks_matrix_30_days.json
      mtgdecks_matrix_60_days.json
      mtgdecks_matrix_90_days.json  # synthesized
      mtgdecks_matrix_180_days.json
      mtgdecks_matrix_210_days.json # synthesized

scripts/
  update_data_monthly.py    # Hlavní ingestion (Playwright → Chrome CDP)
  fetch_deck_icons.py       # Stažení ikonů ze Scryfall
  encode_mana_json.py       # SVG → Base64
  resynthesize_data.py      # Přepočet syntetizovaných period

update_decklists.py         # CLI update decklists.json (urllib — vyžaduje VPN)
update_decklists_browser.py # CLI update decklists.json (Playwright — obchází Cloudflare)
test_scraper.py             # CLI test scraperu (urllib, vyžaduje VPN)

.antigravity/
  PROTOCOL.md               # Provozní pravidla agenta
  ANTIGRAVITY.md            # Long-term RAM (rozhodnutí, architektura, stav)

.agents/workflows/
  local-test.md             # Workflow pro lokální testování
```

## Datová architektura

### Data struktura (`matrix_data`)
```python
{
  "archetypes": ["Burn", "Goblins", ...],
  "tiers": {"Burn": "Tier 1", ...},
  "matrix": {
    "Burn": {
      "Goblins": {"wins": 50, "losses": 40, "win_rate": 0.543}
    }
  },
  "meta_shares": {"BURN": 0.0802, ...}  # klíče jsou UPPERCASE
}
```

### Timeframe mapping (app.py)
- `9M` → `mtgdecks_matrix_210_days`
- `6M` → `mtgdecks_matrix_180_days`
- `3M` → `mtgdecks_matrix_90_days`

### Co scraper fetchuje přímo vs. co se syntetizuje
- **Fetchováno přímo**: `30_days`, `60_days`, `180_days`
- **Syntetizováno**: `90_days` = prev_60_days + cur_30_days; `210_days` = prev_180_days + cur_30_days
- Syntéza čte z `data/historical/[předchozí měsíc]/`

### Dvě datové vrstvy
- **Duress layer**: manuální tourney exporty → `archetype_matrix_*.json`, `win_loss_records_*.json`
- **Scrape layer**: MTGDecks → `mtgdecks_matrix_*.json`
- `load_period_data()` v `analytics.py` merguje obě vrstvy přes `mappings.py`

## Klíčové gotchy
- **Oath merge**: "Oath Control" se manuálně merguje do "Oath" v `load_period_data`
- **meta_shares klíče jsou UPPERCASE**: `meta_shares.get(deck.upper(), 0.0)`
- **Icon slugs**: `name.lower().replace(" ", "_").replace("/", "_").replace("'", "")`
- **Wilson CI**: spolehlivost matchupů počítána přes Wilson score interval (95%)
- **`st.cache_data`**: při testování mimo Streamlit je nutné ho patchovat (viz `test_scraper.py`)
- **403 bez VPN**: `mtgdecks_scraper.py` (urllib) vrací 403 bez VPN; `update_decklists_browser.py` (Playwright) obchází Cloudflare přes existující Chrome session

## Workflow pro měsíční update (vždy 1. dne měsíce)
1. **Zapnout VPN**
2. Spustit Chrome s CDP portem:
   ```bash
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\Temp\ChromeDebug"
   ```
3. Otevřít `mtgdecks.net`, proklikat Cloudflare CAPTCHU
4. Spustit matrix update:
   ```bash
   python scripts/update_data_monthly.py
   ```
5. (Volitelně) Update decklists přes browser:
   ```bash
   python update_decklists_browser.py
   ```
6. Otestovat lokálně: `streamlit run app.py`
7. Commitnout + pushnout po user approval

## Workflow pravidla
1. **Localhost first** — vždy otestovat lokálně před pushnutím na GitHub
2. **Čekej na user approval** před `git push`
3. **VPN zapnout** před jakýmkoliv scrapováním (MTGDecks blokuje IP)
4. **Backup dat** před bulk modifikacemi (`data_backups/`)

## Co vyžaduje souhlas uživatele (HITL)
- Změny v `src/mappings.py` nebo `src/analytics.py` core logice
- Modifikace scraperů ovlivňující integritu dat
- Přidání nových závislostí do `requirements.txt`
- Bulk smazání nebo velký refaktor
