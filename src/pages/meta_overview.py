import streamlit as st
import pandas as pd
import plotly.express as px
from src.analytics import get_period_comparison, wilson_score_interval
from src.ui import THEME, style_winrate, html_deck_table

# Plotly config: minimální toolbar s možností stažení jako PNG
_PLOTLY_DOWNLOAD_CONFIG = {
    "displayModeBar": True,
    "displaylogo": False,
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d", "resetScale2d",
    ],
    "toImageButtonOptions": {
        "format": "png",
        "filename": "premodern_meta",
        "height": 800,
        "width": 1400,
        "scale": 2,
    },
}
_PLOTLY_NO_TOOLBAR = {"displayModeBar": False}

def _style(df, col):
    try:
        return df.style.map(style_winrate, subset=[col])
    except AttributeError:
        return df.style.applymap(style_winrate, subset=[col])

def show_meta_overview(matrix_dict, all_archetypes, records_data, data_dir, timeframes, tiers_dict=None, show_tier_filter=True):
    if tiers_dict is None: tiers_dict = {}
    # Header with title
    st.markdown('<h1 class="page-title">Meta Overview</h1>', unsafe_allow_html=True)

    # Tier filtering UI removed per user request. Show all decks by default.
    if not all_archetypes:
        all_archetypes = ["None"]
        
    # Hardcoded default list of decks for the Matchup Matrix as requested by the user
    preferred_defaults = [
        "Replenish", "Enchantress", "Terrageddon", "Oath Ponza", "Elves",
        "Stasis", "Devourer Combo", "Stiflenought", "Burn",
        "Madness", "Survival Rock", "Gro-a-Tog", "Psychatog", "Landstill",
        "Goblins", "White Weenie", "BW Control", "Machine Head", "The Rock",
        "Deadguy Ale"
    ]
    custom_defaults = [d for d in preferred_defaults if d in all_archetypes]
    if not custom_defaults:
        custom_defaults = all_archetypes[:15]

    def _draw_trend_chart(selected_decks_list, key_suffix=""):
        st.subheader("Win Rate Trends")
        
        with st.spinner("Loading historical data..."):
            pivot_wr, games_df = get_period_comparison(data_dir, timeframes)

            if pivot_wr.empty:
                st.error("Could not load trend data.")
                return

            # Filter by sample size (total games across all periods must be > 5)
            # pivot_wr contains win rates, games_df contains game counts
            decks_with_enough_games = games_df.fillna(0).sum(axis=1) > 5
            valid_trend_decks = [d for d in selected_decks_list if d in pivot_wr.index and decks_with_enough_games.get(d, False)]

            if not valid_trend_decks:
                st.warning("No selected decks have enough historical data.")
                return

            ordered_periods = list(timeframes.keys())
            existing = [p for p in ordered_periods if p in pivot_wr.columns]
            # Calculate Trend: Last Period - First Period
            # We assume 'existing' is ordered from oldest to newest (2 Years -> 2 Months)
            first_p = existing[0]
            last_p = existing[-1]
            
            heatmap_data = pivot_wr.loc[valid_trend_decks][existing].copy()
            
            # Add Trend Column
            def get_trend_icon(deck_row):
                v1 = deck_row[first_p]
                v2 = deck_row[last_p]
                if pd.isna(v1) or pd.isna(v2): return "⚪" # Neutral if data missing
                diff = v2 - v1
                if diff > 0.02: return "🟢 ↑"
                if diff < -0.02: return "🔴 ↓"
                return "⚪ →"

            heatmap_data["Recent Trend"] = heatmap_data.apply(get_trend_icon, axis=1)
            
            # Prepare numeric data for color and text data for labels
            # Heatmap needs a numeric matrix for colors
            # We'll use the original WR values and a dummy value for the Recent Trend column
            display_data = heatmap_data[existing].copy()
            # For the Recent Trend column, we use the last period's WR as a background color base 
            # or just a neutral value. Let's use the last period value to keep color consistent.
            display_data["Recent Trend"] = display_data[last_p] 
            
            # Create text matrix for display
            text_data = heatmap_data[existing].map(lambda x: f"{x:.1%}" if pd.notna(x) else "")
            text_data["Recent Trend"] = heatmap_data["Recent Trend"]

            # Create hover text
            hover_text = []
            for deck in heatmap_data.index:
                row_hover = []
                for col in heatmap_data.columns:
                    if col == "Recent Trend":
                        v1, v2 = heatmap_data.loc[deck, first_p], heatmap_data.loc[deck, last_p]
                        diff_str = f"{(v2-v1):+.1%}" if pd.notna(v1) and pd.notna(v2) else "N/A"
                        row_hover.append(f"<b>{deck}</b><br>Recent Trend: {diff_str}<br>({first_p} → {last_p})")
                    else:
                        val = heatmap_data.loc[deck, col]
                        row_hover.append(f"<b>{deck}</b><br>Period: {col}<br>Win Rate: {val:.1%}" if pd.notna(val) else "No data")
                hover_text.append(row_hover)

            fig_t = px.imshow(
                display_data,
                labels=dict(x="Period", y="Deck", color="Win Rate"),
                x=display_data.columns,
                y=display_data.index,
                color_continuous_scale=[[0, "#C76B6B"], [0.5, "#222222"], [1, "#6BC78E"]],
                zmin=0.35, zmax=0.65,
                aspect="auto",
                template="plotly_dark",
            )
            
            # Add text labels manually to handle the Trend icons
            fig_t.update_traces(
                text=text_data.values,
                texttemplate="%{text}",
                hovertemplate="%{customdata}<extra></extra>",
                customdata=hover_text,
                hoverlabel=dict(font_size=14, font_family="IBM Plex Mono")
            )
            
            fig_t.update_layout(
                height=max(300, len(valid_trend_decks) * 35), # Scale height by number of decks
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color=THEME["text"],
                coloraxis_showscale=False,
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis={'side': 'top', 'fixedrange': True},
                yaxis={'fixedrange': True},
            )
            
            # Use columns for layout to make the chart narrower (centered)
            _, chart_col, _ = st.columns([0.2, 0.6, 0.2])
            with chart_col:
                st.plotly_chart(fig_t, use_container_width=True, key=f"trend_chart_{key_suffix}", config=_PLOTLY_NO_TOOLBAR)

    tab_stats, tab_matchups = st.tabs(["Metagame Stats", "Matchup Matrix & Trends"])

    # ─── Compute meta shares early (used by scatter + table and matchups) ─────────
    matchups_matrix = matrix_dict.get("matrix", matrix_dict) 
    meta_shares     = matrix_dict.get("meta_shares", {})

    # ─── TAB 1: METAGAME STATS ───────────────────────────────────────────────
    with tab_stats:
        # Local filter for Tab 1
        _, f_col = st.columns([0.7, 0.3])
        with f_col:
            stats_min_games = st.slider(
                "Min. games per deck", 0, 100, 30, key="stats_min_tab1",
                help="Minimální počet zaznamenaných her pro zobrazení balíčku. Výchozí hodnota 30 zajišťuje statistickou spolehlivost."
            )

        if records_data:
            df_rec = (
                pd.DataFrame(records_data)
                .rename(columns={"archetype": "Deck", "win_rate": "Win Rate", "total_matches": "Games"})
                .sort_values("Win Rate", ascending=False)
            )
            df_rec = df_rec[(df_rec["Deck"] != "Unknown") & (df_rec["Games"] >= stats_min_games)]

            # ─── Compute meta shares early (used by scatter + table) ─────────
            def _get_share_num(deck):
                return meta_shares.get(deck.upper(), 0.0)

            df_rec["Meta Share (Num)"] = df_rec["Deck"].map(_get_share_num)
            df_rec["Win Rate (Num)"]   = df_rec["Win Rate"]

            # --- SCATTER PLOT: Metagame Share vs Win Rate ---
            st.subheader("Win Rate vs Metagame Share")
            # Note: df_rec is already filtered for Games > 5
            scatter_df = df_rec[(df_rec["Meta Share (Num)"] > 0)].copy()

            if scatter_df.empty:
                st.info("Meta share data not available for this timeframe.")
            else:
                from src.ui import get_circular_icon_b64

                max_share = scatter_df["Meta Share (Num)"].max() or 0.1
                x_max = max_share * 1.18

                y_max = max(0.65, scatter_df["Win Rate (Num)"].max() + 0.03)
                y_min = min(0.35, scatter_df["Win Rate (Num)"].min() - 0.03)
                y_range = y_max - y_min
                x_range = x_max

                scatter_df["tooltip"] = scatter_df.apply(
                    lambda r: f"<b>{r['Deck']}</b><br><br>Meta Share: {r['Meta Share (Num)']:.1%}<br>Win Rate: {r['Win Rate (Num)']:.1%}<br>Games: {r['Games']}",
                    axis=1
                )

                fig_s = px.scatter(
                    scatter_df,
                    x="Meta Share (Num)",
                    y="Win Rate (Num)",
                    hover_name="tooltip",
                    template="plotly_dark"
                )
                fig_s.update_traces(
                    hovertemplate="%{hovertext}<extra></extra>",
                    hoverlabel=dict(font_size=14, font_family="IBM Plex Mono")
                )
                fig_s.add_hline(y=0.5, line_dash="dash", line_color=THEME["faint"])

                icon_sizex = x_range * 0.11
                icon_sizey = y_range * 0.132

                for _, row in scatter_df.iterrows():
                    deck  = row["Deck"]
                    x_val = row["Meta Share (Num)"]
                    y_val = row["Win Rate (Num)"]
                    b64 = get_circular_icon_b64(deck, data_dir)
                    if b64:
                        fig_s.add_layout_image(dict(
                            source=f"data:image/png;base64,{b64}",
                            xref="x", yref="y",
                            x=x_val, y=y_val,
                            sizex=icon_sizex, sizey=icon_sizey,
                            xanchor="center", yanchor="middle",
                            sizing="contain", layer="above"
                        ))
                    else:
                        fig_s.add_annotation(
                            x=x_val, y=y_val,
                            text=deck, showarrow=False,
                            font=dict(size=9, color=THEME["muted"]),
                            xanchor="center", yanchor="bottom", yshift=8
                        )

                fig_s.update_traces(
                    marker=dict(color="rgba(255,255,255,0.15)", size=22,
                                line=dict(color="rgba(255,255,255,0.3)", width=1))
                )
                fig_s.update_layout(
                    height=380,
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color=THEME["text"],
                    margin=dict(l=20, r=20, t=30, b=20),
                    xaxis_title="Metagame Share",
                    yaxis_title="Win Rate",
                    xaxis=dict(tickformat=".0%", range=[0, x_max], fixedrange=True),
                    yaxis=dict(tickformat=".0%", range=[y_min, y_max], fixedrange=True),
                    showlegend=False,
                )
                st.plotly_chart(fig_s, use_container_width=True, key="scatter_meta_winrate", config=_PLOTLY_NO_TOOLBAR)

            st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

            c_top, c_bot = st.columns(2)
            
            # Filter for meaningful sample size (e.g. >= 20 games) 
            df_reliable = df_rec # Already filtered by stats_min_games at the top
            if len(df_reliable) < 5:
                df_reliable = df_rec.sort_values("Games", ascending=False).head(10).sort_values("Win Rate", ascending=False)
                
            with c_top:
                st.markdown("<h3>Best 5 Decks <span title='Decks with fewer than 20 games are excluded to ensure statistical reliability.' style='cursor:help; font-size:14px; color:#8A8A8A; opacity:0.8;'>&#9432;</span></h3>", unsafe_allow_html=True)
                d = df_reliable.head(5)[["Deck", "Win Rate", "Meta Share (Num)", "Games"]].copy()
                d["Win Rate"] = d["Win Rate"].map(lambda x: f"{x:.1%}")
                d["Meta Share"] = d["Meta Share (Num)"].apply(lambda s: f"{s:.1%}" if s > 0 else "n/a")
                st.markdown(html_deck_table(d, ["Deck", "Win Rate", "Meta Share", "Games"], data_dir=data_dir), unsafe_allow_html=True)

            with c_bot:
                st.markdown("<h3>Worst 5 Decks <span title='Decks with fewer than 20 games are excluded to ensure statistical reliability.' style='cursor:help; font-size:14px; color:#8A8A8A; opacity:0.8;'>&#9432;</span></h3>", unsafe_allow_html=True)
                d = df_reliable.tail(5).sort_values("Win Rate", ascending=True)[["Deck", "Win Rate", "Meta Share (Num)", "Games"]].copy()
                d["Win Rate"] = d["Win Rate"].map(lambda x: f"{x:.1%}")
                d["Meta Share"] = d["Meta Share (Num)"].apply(lambda s: f"{s:.1%}" if s > 0 else "n/a")
                st.markdown(html_deck_table(d, ["Deck", "Win Rate", "Meta Share", "Games"], data_dir=data_dir), unsafe_allow_html=True)

            st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

            st.subheader("All Decks by Win Rate")
            d_all = df_rec.copy()
            d_all["Meta Share"] = d_all["Meta Share (Num)"].apply(lambda s: f"{s:.1%}" if s > 0 else "n/a")

            def _get_interval(row):
                w = row.get("wins", 0)
                t = row.get("Games", 0)
                if t == 0: return "n/a"
                l, u = wilson_score_interval(w, t)
                return f"{l:.1%} – {u:.1%}"
                
            d_all["Win Rate Confidence Interval"] = d_all.apply(_get_interval, axis=1)
            d_table = d_all[["Deck", "Win Rate (Num)", "Meta Share", "Win Rate Confidence Interval", "Games"]].copy()
            d_table = d_table.rename(columns={"Games": "Sample Size", "Win Rate (Num)": "Win Rate"})
            d_table["Win Rate"] = d_table["Win Rate"].map(lambda x: f"{x:.1%}")
            
            st.markdown(html_deck_table(d_table, ["Deck", "Win Rate", "Meta Share", "Win Rate Confidence Interval", "Sample Size"], data_dir=data_dir), unsafe_allow_html=True)




    # ─── TAB 2: MATCHUP MATRIX ───────────────────────────────────────────────
    with tab_matchups:
        # ── SHARED DECK SELECTOR & FILTERS ───────────────────────────────
        f1, f2, f3 = st.columns([2.5, 1, 1.5])
        with f1:
            selected_decks = st.multiselect(
                "Select Decks",
                all_archetypes, # Can still pick any
                default=custom_defaults,
                key="overview_deck_select",
            )
        with f2:
            sort_by = st.selectbox("Sort By", ["Win Rate", "Alphabet"], key="overview_sort")
        with f3:
            matrix_min_games = st.slider(
                "Min. games per deck", 0, 100, 5, key="stats_min_tab2",
                help="Buňky matchup matice s méně hrami než tento práh se zobrazí jako prázdné (nedostatek dat)."
            )

        if not selected_decks:
            st.warning("Select at least one deck.")
            return

        # ─── MATCHUP MATRIX ───────────────────────────────────────────────
        decks_for_matrix = list(selected_decks)
        if sort_by == "Win Rate":
            stats = [
                (d, sum(matchups_matrix.get(d, {}).get(o, {}).get("win_rate", 0.5) for o in decks_for_matrix) / len(decks_for_matrix))
                for d in decks_for_matrix
            ]
            decks_for_matrix = [x[0] for x in sorted(stats, key=lambda x: x[1], reverse=True)]

        if not decks_for_matrix:
            st.info("No decks match the current filters.")
            st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)
            _draw_trend_chart(selected_decks)
            return

        hm_data, hover_data = [], []
        for arch1 in decks_for_matrix:
            row, hover_row = [], []
            for arch2 in decks_for_matrix:
                cell  = matchups_matrix.get(arch1, {}).get(arch2, {})
                total = cell.get("total_matches", 0)
                wr    = cell.get("win_rate", 0.5)
                # Use the local filter for Tab 2
                if total >= matrix_min_games:
                    row.append(wr)
                    hover_row.append(f"Win Rate {wr:.1%}<br>{cell.get('wins',0)}W – {cell.get('losses',0)}L")
                else:
                    row.append(None)
                    hover_row.append("Insufficient data")
            hm_data.append(row)
            hover_data.append(hover_row)

        fig = px.imshow(
            hm_data,
            x=decks_for_matrix, y=decks_for_matrix,
            color_continuous_scale=[[0, "#C76B6B"], [0.5, "#222222"], [1, "#6BC78E"]],
            zmin=0.35, zmax=0.65,
            text_auto=".1%",
            aspect="auto",
        )
        fig.update_layout(
            height=700,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color=THEME["text"],
            margin=dict(l=0, r=0, t=40, b=0),
            coloraxis_showscale=False,
            xaxis={'side': 'top', 'fixedrange': True},
            yaxis={'fixedrange': True},
        )
        fig.update_traces(
            hovertemplate="<b>%{y} vs %{x}</b><br>%{customdata}<extra></extra>",
            customdata=hover_data,
            hoverlabel=dict(font_size=14, font_family="IBM Plex Mono")
        )
        st.plotly_chart(fig, use_container_width=True, config=_PLOTLY_DOWNLOAD_CONFIG)

        st.markdown(f'<div style="margin: 8px 0 12px 0; border-top: 1px solid {THEME["border"]};"></div>', unsafe_allow_html=True)

        # ─── WIN RATE TRENDS ─────────────────────────────────────────────
        _draw_trend_chart(selected_decks, key_suffix="matrix")

