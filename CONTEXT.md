# CONTEXT: mtg-meta-dashboard
_Čti tento soubor při každém spuštění session pro projekt mtg-meta-dashboard._

## Co je mtg-meta-dashboard
Streamlit aplikace pro analýzu MTG (Magic: The Gathering) meta. Zobrazuje matchup matice, win rates, tier listy a simulace turnajů. Deploy na Streamlit Cloud.

## Tech stack
- **Python** 3.10+, **Streamlit**, **Pandas**, **NumPy**, **Plotly**
- **Deploy:** Streamlit Cloud (GitHub `main` branch)
- **Datové zdroje:** MTGDecks.net (primární), Duress Crew (legacy/historická data)
- **Assets:** Scryfall Art Crops (ikony), Base64 Mana Symbols (SVG)

## Architektura dat
### Timeframe klíče (interní)
| UI label | Data klíč |
|----------|-----------|
| 9M | `mtgdecks_matrix_210_days` |
| 6M | `mtgdecks_matrix_180_days` |
| 3M | `mtgdecks_matrix_90_days` |

### Struktura `matrix_data`
```python
{
  "archetypes": ["Burn", "Goblins", ...],
  "tiers": {"Burn": "Tier 1", ...},
  "matrix": {"Burn": {"Goblins": {"wins": 50, "losses": 40, "win_rate": 0.543}}},
  "meta_shares": {"BURN": 0.0802, ...}  # Keys jsou UPPERCASE
}
```

### Datové vrstvy
- **Duress Layer:** Manuální tournament exporty. `archetype_matrix_[period].json`, `win_loss_records_[period].json`. Baseline pro 1Y/2Y/All Time.
- **Scrape Layer:** Automatizovaná MTGDecks extrakce. `mtgdecks_matrix_[period].json`. Real-time shares, tiers, decklists.
- Merge v `load_period_data()` — normalizace názvů přes `mappings.py`.

## Klíčové "gotchas"
- **Oath Merge:** "Oath Control" se ručně merguje do "Oath" v `load_period_data` kvůli nekonzistenci zdrojů
- **Wilson Confidence:** Matchup reliabilita = Wilson score interval (95% confidence)
- **Icon slugs:** `deck_name.lower().replace(" ", "_").replace("/", "_").replace("'", "")`
- **Asset loading:** Ikony jako base64 přes `src/ui.py → get_icon_b64` (kvůli Streamlit Cloud path issues)

## Struktura projektu
```
src/
  mappings.py        # centrální normalizace archetype názvů
  analytics.py       # DECK_CARD_MAP, matchup logika
  ui.py              # asset loading, base64 ikony
  pages/
    analysis.py      # matchup polarity, win rate history
    simulator.py     # Monte Carlo simulace

scripts/
  update_data_monthly.py   # hlavní ingestion
  scrape_decklists.py      # decklist refresh
  fetch_deck_icons.py      # Scryfall icon downloader
  encode_mana_json.py      # SVG-to-Base64 encoder
```

## Aktuální stav (k 2026-04-09)
- [x] Bootstrap Antigravity Agentic Blueprint v1.1
- [x] `.antigravity/` struktura inicializována
- [ ] Verifikace `load_period_data` integrity
- [ ] Pytest suite (pokud aplikovatelné)

## Pravidla deploymentu
**Localhost-first:** Vždy testovat lokálně → User verifikace → Git push na `main`
Nikdy nepushovat přímo bez lokálního testu.

## Konvence kódu
- CSV exporty: **UTF-8 with BOM (`utf-8-sig`)** — kvůli kompatibilitě s Excelem
- Caching: `st.cache_data(ttl=3600)` v `app.py`
