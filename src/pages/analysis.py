import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.analytics import load_period_data, wilson_score_interval, calculate_polarity
from src.ui import THEME, style_winrate, get_icon_b64
import os
import json

def _wr_color_str(wr_str):
    """Return CSS color for a formatted win rate string like '55.0%'."""
    try:
        v = float(wr_str.strip('%')) / 100
    except:
        return THEME['text']
    if v > 0.55: return THEME['success']
    if v < 0.45: return THEME['danger']
    if v < 0.50: return THEME['warning']
    return THEME['text']

def _html_matchup_table(df, columns, data_dir="data"):
    """Render a matchup dataframe as an HTML table with deck icons."""
    border_clr  = THEME["border"]
    faint_clr   = THEME["faint"]
    muted_clr   = THEME["muted"]
    surface_clr = THEME["surface"]
    bg_clr      = THEME["bg"]
    header = ''.join(
        f'<th style="padding:6px 8px; text-align:left; border-bottom:1px solid {border_clr};'
        f' color:{faint_clr}; font-size:13px;">{c}</th>'
        for c in columns
    )
    rows_html = ''
    for _, row in df.iterrows():
        cells = ''
        for c in columns:
            val = str(row.get(c, ''))
            if c == 'Opponent':
                b64 = get_icon_b64(val, data_dir)
                img = (
                    f'<img src="data:image/jpeg;base64,{b64}" alt="{val}" '
                    f'style="width:28px;height:20px;object-fit:cover;border-radius:3px;'
                    f'margin-right:6px;vertical-align:middle;border:1px solid {border_clr};">'
                ) if b64 else ''
                cells += f'<td style="padding:5px 8px; font-size:14px;">{img}{val}</td>'
            elif c == 'Win Rate':
                color = _wr_color_str(val)
                cells += f'<td style="padding:5px 8px; font-size:14px; color:{color}; font-weight:600;">{val}</td>'
            else:
                cells += f'<td style="padding:5px 8px; font-size:14px; color:{muted_clr};">{val}</td>'
        rows_html += f'<tr style="border-bottom:1px solid {bg_clr};">{cells}</tr>'
    return (
        f'<table style="width:100%; border-collapse:collapse; background:{surface_clr};'
        f' border-radius:8px; overflow:hidden;">'
        f'<thead><tr>{header}</tr></thead><tbody>{rows_html}</tbody></table>'
    )

def _quality_badge(games):
    """Return a sample quality label. High ≥50 games, Avg ≥20, Low <20."""
    if games >= 50: return "High ✓"
    if games >= 20: return "Avg"
    return "Low ⚠"

def _style_wr_col(df, col="Win Rate"):
    """Safely apply win rate coloring compatible with both old and new pandas."""
    try:
        return df.style.map(style_winrate, subset=[col])
    except AttributeError:
        return df.style.applymap(style_winrate, subset=[col])

def show_analysis(matrix_dict, all_archetypes, records_data, data_dir, timeframes):
    st.markdown('<h1 class="page-title">Deck Analysis</h1>', unsafe_allow_html=True)

    # Preserve deck selection across timeframe changes
    try:
        default_deck = next(x for x in all_archetypes if "stiflenought" in x.lower() or "dreadnought" in x.lower())
    except StopIteration:
        default_deck = all_archetypes[0] if all_archetypes else ""

    saved_deck = st.session_state.get("analysis_saved_deck", default_deck)
    if saved_deck not in all_archetypes:
        saved_deck = default_deck

    try:
        current_idx = all_archetypes.index(saved_deck)
    except ValueError:
        current_idx = 0

    # Icon + selectbox side by side
    col_icon, col_select, col_slider = st.columns([0.08, 0.62, 0.3])
    with col_select:
        target_deck = st.selectbox(
            "Select Deck", 
            all_archetypes, 
            index=current_idx
        )
    with col_slider:
        stats_min_games = st.slider(
            "Min. games per matchup", 0, 100, 5, key="analysis_min_games",
            help="Filtruje matchupy s malým vzorkem. Doporučeno ≥20 pro spolehlivé výsledky."
        )
            
    st.session_state["analysis_saved_deck"] = target_deck

    with col_icon:
        b64 = get_icon_b64(target_deck, data_dir)
        if b64:
            _icon_border = THEME["border"]
            st.markdown(
                f'<div style="margin-top:24px;">'
                f'<img src="data:image/jpeg;base64,{b64}" alt="{target_deck}" '
                f'style="width:56px; height:42px; object-fit:cover; border-radius:6px; border:1px solid {_icon_border};">'
                f'</div>',
                unsafe_allow_html=True,
            )

    matchups_matrix = matrix_dict.get("matrix", {})
    row_data        = matchups_matrix.get(target_deck, {})
    deck_record = next((r for r in records_data if r["archetype"] == target_deck), {})
    overall_wr  = deck_record.get("win_rate", 0)
    total_games = deck_record.get("total_matches", 0)

    # Matchup rows with confidence intervals
    prof_rows = []
    for other in all_archetypes:
        if other == target_deck:
            continue
        cell  = row_data.get(other, {})
        total = cell.get("total_matches", 0)
        if total > 0:
            wins = cell.get("wins", 0)
            wr   = cell.get("win_rate", 0.5)
            lo, hi = wilson_score_interval(wins, total)
            prof_rows.append({
                "Opponent": other,
                "WR":       wr,
                "95% CI":   f"{lo:.1%} – {hi:.1%}",
                "Record":   f"{wins}W – {cell.get('losses', 0)}L",
                "Games":    total,
                "Sample":   _quality_badge(total),
            })

    df_prof = pd.DataFrame(prof_rows).sort_values("WR", ascending=False) if prof_rows else pd.DataFrame()
    if not df_prof.empty:
        df_prof = df_prof[df_prof["Opponent"] != "Unknown"]

    # Polarity percentile — must use inner matchups_matrix, not the full matrix_dict
    matchups_matrix_for_polarity = matrix_dict.get("matrix", matrix_dict)
    all_polarities = [calculate_polarity(a, matchups_matrix_for_polarity, all_archetypes) for a in all_archetypes]
    polarity       = calculate_polarity(target_deck, matchups_matrix_for_polarity, all_archetypes)
    pct_rank       = int(100 * sum(p <= polarity for p in all_polarities) / max(len(all_polarities), 1))
    pct_label      = (
        "high polarity — strong matchup spread (rock-paper-scissors)" if pct_rank > 66
        else "average polarity" if pct_rank > 33
        else "stable — consistent matchup profile across the field"
    )

    tab_stats, tab_decks = st.tabs(["Statistics", "Top Decklists"])

    with tab_stats:

        if not df_prof.empty:
            df_prof = df_prof[df_prof["Games"] >= stats_min_games]
            
        # matrix_dict is now the full matrix_data object
        matchups_matrix = matrix_dict.get("matrix", matrix_dict)
        meta_shares     = matrix_dict.get("meta_shares", {})
        share = meta_shares.get(target_deck.upper())
        share_display = f"{share:.1%}" if share is not None else "N/A"

        # --- KPI ROW (5 columns) ---
        c1, c2, c3, c4, c5 = st.columns(5)
        
        with c1:
            st.metric("Overall Win Rate", f"{overall_wr:.1%}")
        with c2:
            st.metric("Total Games", f"{total_games:,}")
        with c3:
            st.metric("Meta Share", share_display)
        with c4:
            if not df_prof.empty:
                df_prof["Bracket"] = pd.cut(
                    df_prof["WR"],
                    bins=[0, 0.45, 0.55, 1.0],
                    labels=["Unfavoured (<45%)", "Even (45-55%)", "Favoured (>55%)"],
                )
                counts = df_prof["Bracket"].value_counts()
                bad_n  = int(counts.get("Unfavoured (<45%)", 0))
                even_n = int(counts.get("Even (45-55%)", 0))
                good_n = int(counts.get("Favoured (>55%)", 0))

                st.metric(
                    "Matchup Distribution",
                    f"{good_n}↑  {even_n}~  {bad_n}↓",
                    help=f"{good_n} favoured (>55%) · {even_n} even (45–55%) · {bad_n} unfavoured (<45%)"
                )
        with c5:
            st.metric(
                "Polarity Index",
                f"{polarity * 100:.1f}%",
                help=f"Spread of matchup win rates. {pct_rank}th percentile — {pct_label}.",
            )

        st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

        st.markdown(
            "<h3>Win Rate &amp; Meta Share Trend "
            "<span title='Each point shows the overall win rate and metagame share across all recorded matches in that time window.' "
            "style='cursor:help; font-size:16px; color:#8A8A8A; opacity:0.8;'>&#9432;</span></h3>",
            unsafe_allow_html=True,
        )
    


        history_rows = []
        # Current data for the current period comes from matrix_data / records_data
        # We also want to show historical snapshots if available
        for period_label, period_key in timeframes.items():
            try:
                mdata, rdata = load_period_data(data_dir, period_key)
                rec = next((r for r in rdata if r["archetype"] == target_deck), None)
                if rec:
                    ms = mdata.get("meta_shares", {})
                    share = ms.get(target_deck.upper())
                    history_rows.append({
                        "Period":      period_label,
                        "Win Rate":    rec["win_rate"],
                        "Meta Share":  share,
                        "Games":       rec["total_matches"],
                    })
            except Exception as e:
                st.sidebar.warning(f"Could not load data for {period_label}: {e}")

        if history_rows:
            df_hist = pd.DataFrame(history_rows)

            def _wr_color(v):
                if v > 0.55: return THEME["success"]
                if v < 0.45: return THEME["danger"]
                if v < 0.50: return THEME["warning"]
                return THEME["text"]

            # ── Combined chart: Win Rate + Meta Share, shared left y-axis ──────
            ms_vals = df_hist["Meta Share"].tolist()
            has_meta = any(v is not None for v in ms_vals)

            fig_hist = go.Figure()
            
            # Simple colors for the line and markers to avoid list-based color mapping errors in some environments
            wr_color_base = "#E8E8E8"
            
            fig_hist.add_trace(go.Scatter(
                x=df_hist["Period"], y=df_hist["Win Rate"],
                name="Win Rate",
                mode="lines+markers+text",
                text=[f"{v:.1%}" for v in df_hist["Win Rate"]],
                textposition="top center",
                textfont=dict(size=12, color="#CCC"),
                line=dict(color=wr_color_base, width=3, dash="dot"),
                marker=dict(size=8, color="#00CC96", line=dict(width=0)), # Constant color for robustness
            ))

            if has_meta:
                ms_display = [v if v is not None else None for v in ms_vals]
                fig_hist.add_trace(go.Scatter(
                    x=df_hist["Period"], y=ms_display,
                    name="Meta Share",
                    mode="lines+markers+text",
                    text=[f"{v:.1%}" if v is not None else "" for v in ms_display],
                    textposition="top center",
                    textfont=dict(size=12, color="rgba(190, 220, 240, 0.85)"),
                    line=dict(color="rgba(190, 220, 240, 0.75)", width=2, dash="dash"),
                    marker=dict(size=6, color="rgba(190, 220, 240, 0.85)"),
                    connectgaps=False,
                ))


            # Add inline label at the last point of each line
            last_period = df_hist["Period"].iloc[-1]
            last_wr     = df_hist["Win Rate"].iloc[-1]
            fig_hist.add_annotation(
                x=last_period, y=last_wr,
                text="Win Rate", showarrow=False,
                xanchor="left", yanchor="middle", xshift=10,
                font=dict(size=13, color=THEME["muted"]),
            )
            if has_meta:
                last_ms = next((v for v in reversed(ms_display) if v is not None), None)
                last_ms_period = df_hist["Period"].iloc[
                    max(i for i, v in enumerate(ms_display) if v is not None)
                ]
                if last_ms is not None:
                    fig_hist.add_annotation(
                        x=last_ms_period, y=last_ms,
                        text="Meta Share", showarrow=False,
                        xanchor="left", yanchor="middle", xshift=10,
                        font=dict(size=13, color="rgba(190, 220, 240, 0.85)"),
                    )

            fig_hist.update_layout(
                height=210,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=THEME["muted"], font_family="IBM Plex Mono",
                margin=dict(l=35, r=90, t=28, b=0),
                yaxis=dict(
                    tickformat=".0%", range=[0, 0.7], tickfont=dict(size=11), 
                    showgrid=True, dtick=0.2, gridcolor="rgba(255, 255, 255, 0.1)",
                    fixedrange=True
                ),
                xaxis=dict(tickfont=dict(size=12), fixedrange=True, categoryorder='array', categoryarray=list(timeframes.keys())),
                xaxis_title="",
                showlegend=False,
                hovermode="x unified",
            )
            st.plotly_chart(fig_hist, use_container_width=True, key="deck_trend_combined", config={'displayModeBar': False})

        st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

        # --- TOP 5 / WORST 5 ---
        col_best, col_worst = st.columns(2)

        def _prep(df_slice):
            d = df_slice[["Opponent", "WR", "Games", "Record"]].copy()
            d = d.rename(columns={"WR": "Win Rate"})
            d["Win Rate"] = d["Win Rate"].map(lambda x: f"{x:.1%}")
            return d

        with col_best:
            col_best.markdown("<h3>Best Matchups</h3>", unsafe_allow_html=True)
        
        if not df_prof.empty:
            best_matchups = df_prof.sort_values("WR", ascending=False).head(5)
            worst_matchups = df_prof.sort_values("WR", ascending=True).head(5)
        else:
            best_matchups = pd.DataFrame()
            worst_matchups = pd.DataFrame()

        if not best_matchups.empty:
            col_best.markdown(_html_matchup_table(_prep(best_matchups), ["Opponent", "Win Rate", "Games", "Record"], data_dir), unsafe_allow_html=True)

        col_worst.markdown("<h3>Worst Matchups</h3>", unsafe_allow_html=True)
        if not worst_matchups.empty:
            col_worst.markdown(_html_matchup_table(_prep(worst_matchups), ["Opponent", "Win Rate", "Games", "Record"], data_dir), unsafe_allow_html=True)

        st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

        # --- FULL MATCHUP TABLE ---
        st.subheader("All Matchups")
        if not df_prof.empty:
            df_display = df_prof[["Opponent", "WR", "95% CI", "Record", "Games", "Sample"]].copy()
            df_display = df_display.rename(columns={"WR": "Win Rate", "95% CI": "Confidence Interval", "Sample": "Sample Size"})
            df_display["Win Rate"] = df_display["Win Rate"].map(lambda x: f"{x:.1%}")
            st.markdown(
                _html_matchup_table(df_display, ["Opponent", "Win Rate", "Confidence Interval", "Record", "Games", "Sample Size"], data_dir),
                unsafe_allow_html=True,
            )



    with tab_decks:

        decklists_file = os.path.join(data_dir, "decklists.json")
        decks = []
        if os.path.exists(decklists_file):
            with open(decklists_file, 'r', encoding='utf-8') as f:
                try:
                    all_decklists = json.load(f)
                    decks = all_decklists.get(target_deck, [])
                except Exception as e:
                    pass
                    
        if not decks:
            st.info("No recent decklists found.")
        else:
            # Load Official Mana Symbols (Base64)
            MANA_MAP = {}
            try:
                mana_json_path = os.path.join(data_dir, "mana_symbols.json")
                with open(mana_json_path, "r", encoding="utf-8") as f:
                    MANA_MAP = json.load(f)
            except:
                MANA_MAP = {'W': '☀️', 'U': '💧', 'B': '💀', 'R': '🔥', 'G': '🌲', 'C': '💎'}
            
            # --- FILTERING & SORTING UI ---
            col_search, col_sort = st.columns([0.7, 0.3])
            with col_search:
                search_q = st.text_input("🔍 Search by cards", "", placeholder="Seperate cards by ;")
            with col_sort:
                sort_option = st.selectbox("Sort by", ["Date", "Size", "Rank", "Spice"], index=0)

            # --- SORTING LOGIC ---
            def _rank_val(r):
                r = str(r).upper().strip()
                if "1ST" in r: return 1
                if "2ND" in r: return 2
                if "TOP4" in r: return 4
                if "TOP8" in r: return 8
                if "TOP16" in r: return 16
                return 100

            if sort_option == "Rank":
                decks = sorted(decks, key=lambda x: _rank_val(x.get('rank', '??')))
            elif sort_option == "Size":
                decks = sorted(decks, key=lambda x: int(str(x.get('players', 0))) if str(x.get('players',0)).isdigit() else 0, reverse=True)
            elif sort_option == "Spice":
                decks = sorted(decks, key=lambda x: x.get('spice', 0), reverse=True)
            else: # Date
                decks = sorted(decks, key=lambda x: str(x.get('date', '')), reverse=True)

            st.markdown('<p style="color:#888; font-size:12px; margin-top:-15px; margin-bottom:0px;">💡 <i>Click rows to see decklists</i></p>', unsafe_allow_html=True)

            # Filtering
            if search_q:
                qs = [q.strip().lower() for q in search_q.split(';') if q.strip()]
                decks = [d for d in decks if all(any(q in c.get('name','').lower() for c in d.get('cards', [])) for q in qs)]

            if not decks:
                st.info("No decklists match your filters.")
            else:
                # --- CSS (Unified Style) ---
                st.markdown(f"""
                    <style>
                    .d-table {{
                        width: 100%;
                        background: #1A1A1A;
                        border: 1px solid rgba(255,255,255,0.05);
                        border-radius: 6px;
                        overflow: hidden;
                        font-family: 'Inter', system-ui, sans-serif;
                    }}
                    .d-header {{
                        display: grid;
                        grid-template-columns: 65px 75px 200px 90px 75px 1fr 110px;
                        background: #262626;
                        padding: 12px 16px;
                        border-bottom: 2px solid #333;
                        color: #8A8A8A;
                        font-size: 13px;
                        font-weight: 700;
                        letter-spacing: 0.5px;
                    }}
                    .d-summary {{
                        display: grid;
                        grid-template-columns: 65px 75px 200px 90px 75px 1fr 110px;
                        padding: 14px 16px;
                        cursor: pointer;
                        align-items: center;
                        border-bottom: 1px solid rgba(255,255,255,0.05);
                        list-style: none;
                        background: transparent;
                        transition: background 0.1s;
                    }}
                    .d-summary::-webkit-details-marker {{ display: none; }}
                    .d-summary:hover {{ background: #222; }}
                    .d-row[open] .d-summary {{ background: #2A2A2A; border-bottom: 1px solid rgba(255,255,255,0.1); }}

                    .c-rank {{ color: #6BC78E; font-size: 13px; }}
                    .c-players {{ color: #EEE; font-size: 13px; }}
                    .c-player {{ color: #EEE; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                    .c-spice {{ font-size: 13px; color: #FFD700; }}
                    .c-event {{ color: #AAA; font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
                    .c-date {{ color: #8A8A8A; font-size: 13px; text-align: right; }}

                    .d-content {{ padding: 24px; background: #111; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 24px; }}
                    .sect-t {{ color: #6BC78E; font-size: 13px; font-weight: bold; text-transform: uppercase; margin-bottom: 10px; border-bottom: 1px solid #333; }}
                    .card-i {{ color: #DDD; font-size: 13px; line-height: 1.6; display: flex; align-items: start; }}
                    .qty-s {{ color: #888; font-weight: bold; margin-right: 8px; min-width: 24px; display: inline-block; }}
                    </style>
                """, unsafe_allow_html=True)

                # --- RENDER TABLE ---
                # Static Header Row (HTML)
                table_html = f'<div class="d-table">'
                table_html += f'<div class="d-header">'
                table_html += '<div>Rank</div><div>Size</div><div>Player</div><div>Colors</div><div>Spice</div><div>Event</div><div style="text-align:right;">Date</div>'
                table_html += '</div>'

                # Body
                for d in decks:
                    def _mana(m_str):
                        if "![" in str(m_str):
                            import re
                            match = re.search(r'\((data:image/[^)]+)\)', str(m_str))
                            if match: return f'<img src="{match.group(1)}" style="width:14px; height:14px; margin-right:2px; vertical-align:middle; border-radius:50%;">'
                        return str(m_str)
                    
                    icons = "".join([_mana(MANA_MAP.get(c, f"[{c}]")) for c in d.get("colors", [])])
                    spice_html = f'<span class="c-spice">{d.get("spice",0)}%</span>' if d.get("spice", 0) > 0 else '—'
                    
                    c_html = '<div class="d-content">'
                    c_list = d.get('cards', [])
                    if not c_list:
                        c_html += '<div style="grid-column: span 3; color: #888;">No cards found.</div>'
                    else:
                        # Split cards into 3 categories
                        def is_land(card):
                            name = card.get("name", "").lower()
                            ctype = card.get("type", "").lower()
                            if "land" in ctype: 
                                return True
                            land_keywords = {
                                "plains", "island", "swamp", "mountain", "forest",
                                "strand", "heath", "delta", "mire", "foothills",
                                "tarn", "mesa", "rainforest", "catacombs", "marsh",
                                "tomb", "city", "mine", "port", "waste", "tower", "factory",
                                "conclave", "treetop", "village", "brushland", "karplusan", 
                                "adarkar", "underground", "volcanic", "tropical", "bayou", 
                                "scrubland", "badlands", "savannah", "taiga", "plateau",
                                "ancient tomb", "wasteland", "gemstone mine"
                            }
                            return any(kw in name for kw in land_keywords)

                        maindeck_non_land = [c for c in c_list if c.get("section") == "Maindeck" and not is_land(c)]
                        lands = [c for c in c_list if c.get("section") == "Maindeck" and is_land(c)]
                        sideboard = [c for c in c_list if c.get("section") == "Sideboard"]

                        # Column 1: Maindeck (Non-Land)
                        c_html += '<div><div class="sect-t">Maindeck</div>'
                        for c in maindeck_non_land:
                            c_html += f'<div class="card-i"><span class="qty-s">{c["qty"]}x</span> {c["name"]}</div>'
                        c_html += '</div>'

                        # Column 2: Lands
                        c_html += '<div><div class="sect-t">Lands</div>'
                        for c in lands:
                            c_html += f'<div class="card-i"><span class="qty-s">{c["qty"]}x</span> {c["name"]}</div>'
                        if not lands:
                            c_html += '<div style="color:#666; font-size:12px; font-style:italic;">No land data.</div>'
                        c_html += '</div>'

                        # Column 3: Sideboard
                        c_html += '<div><div class="sect-t">Sideboard</div>'
                        for c in sideboard:
                            c_html += f'<div class="card-i"><span class="qty-s">{c["qty"]}x</span> {c["name"]}</div>'
                        if not sideboard:
                            c_html += '<div style="color:#666; font-size:12px; font-style:italic;">No sideboard.</div>'
                        c_html += '</div>'

                        c_html += f'<div style="grid-column: span 3; border-top: 1px solid #333; padding-top: 12px; text-align: center;"><a href="{d.get("url","#")}" target="_blank" style="color: #6BC78E; text-decoration: none; font-size: 13px; font-weight: bold;">View on MTGDecks ↗</a></div>'
                    c_html += '</div>'

                    table_html += f'<details class="d-row"><summary class="d-summary"><div class="c-rank">{d.get("rank","??")}</div><div class="c-players">{d.get("players","??")}</div><div class="c-player">{d.get("player","")}</div><div>{icons}</div>{spice_html}<div class="c-event">{d.get("event","")}</div><div class="c-date">{d.get("date","")}</div></summary>{c_html}</details>'
                
                table_html += '</div>'
                st.html(table_html)
