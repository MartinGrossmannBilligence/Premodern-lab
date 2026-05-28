# PLAN.md

## Current Objective
Příprava na měsíční data update 2026-05-01.

## Status
- [x] Streamlit běží lokálně (port 8502)
- [x] plotly nainstalován
- [x] CLAUDE.md aktualizován
- [x] Historical backup 2026-04-01 připraven (60_days + 180_days pro syntézu)
- [ ] Nezkomitované změny commitnout před 1. 5.
- [ ] Měsíční update spustit 1. 5. (viz workflow v CLAUDE.md)

## Poznámky
- `.antigravity/` se dále aktivně neudržuje — vše jede přes CLAUDE.md + Claude auto-memory
- Pro update dat použít `scripts/update_data_monthly.py` (Playwright)
- Pro decklists použít `update_decklists_browser.py` (Playwright, Cloudflare bypass)
