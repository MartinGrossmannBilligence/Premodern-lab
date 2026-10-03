import streamlit as st # Cache-busted
import os
import base64
from src.bg_data import BG_TOG_V10_B64

_icon_cache = {}
_circular_icon_cache = {}
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def get_icon_b64(deck_name, data_dir="data"):
    """Return base64-encoded JPEG art_crop for a deck (cached)."""
    if deck_name in _icon_cache:
        return _icon_cache[deck_name]
    slug = deck_name.lower().replace(" ", "_").replace("/", "_").replace("'", "")
    path = os.path.join(_PROJECT_ROOT, "assets", "deck_icons", f"{slug}.jpg")
    if os.path.exists(path):
        with open(path, "rb") as f:
            _icon_cache[deck_name] = base64.b64encode(f.read()).decode()
    else:
        # st.write(f"Icon not found: {path}") # Debug
        _icon_cache[deck_name] = None
    return _icon_cache[deck_name]

def get_circular_icon_b64(deck_name, data_dir="data", size=128):
    """Return base64-encoded PNG with circular crop for a deck (cached).
    Falls back to plain JPEG if Pillow is not available."""
    if deck_name in _circular_icon_cache:
        return _circular_icon_cache[deck_name]
    try:
        from PIL import Image, ImageDraw
        import io
        slug = deck_name.lower().replace(" ", "_").replace("/", "_").replace("'", "")
        path = os.path.join(_PROJECT_ROOT, "assets", "deck_icons", f"{slug}.jpg")
        if not os.path.exists(path):
            _circular_icon_cache[deck_name] = get_icon_b64(deck_name, data_dir)
            return _circular_icon_cache[deck_name]
        img = Image.open(path).convert("RGBA")
        # Crop to square from center, then resize
        w, h = img.size
        side = min(w, h)
        left = (w - side) // 2
        top  = (h - side) // 2
        img = img.crop((left, top, left + side, top + side)).resize((size, size), Image.LANCZOS)
        # Apply circular mask
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        img.putalpha(mask)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        _circular_icon_cache[deck_name] = base64.b64encode(buf.getvalue()).decode()
    except Exception:
        _circular_icon_cache[deck_name] = get_icon_b64(deck_name, data_dir)
    return _circular_icon_cache[deck_name]

def html_deck_table(df, columns, deck_col="Deck", wr_col="Win Rate", data_dir="data"):
    """Render a dataframe as HTML table with deck icons and colored win rates."""
    border_clr = THEME["border"]
    faint_clr  = THEME["faint"]
    muted_clr  = THEME["muted"]
    surface_clr = THEME["surface"]
    bg_clr     = THEME["bg"]
    header = ''.join(
        f'<th style="padding:6px 8px;text-align:left;border-bottom:1px solid {border_clr};'
        f'color:{faint_clr};font-size:13px;">{c}</th>'
        for c in columns
    )
    rows = ''
    for _, row in df.iterrows():
        cells = ''
        for c in columns:
            val = str(row.get(c, ''))
            if c == deck_col:
                b64 = get_icon_b64(val, data_dir)
                img = (
                    f'<img src="data:image/jpeg;base64,{b64}" alt="{val}" '
                    f'style="width:28px;height:20px;object-fit:cover;border-radius:3px;'
                    f'margin-right:6px;vertical-align:middle;border:1px solid {border_clr};">'
                ) if b64 else ''
                cells += f'<td style="padding:5px 8px;font-size:14px;">{img}{val}</td>'
            elif c == wr_col:
                try:
                    v = float(val.strip('%')) / 100
                except:
                    v = 0.5
                color = THEME['success'] if v > 0.55 else THEME['danger'] if v < 0.45 else THEME['warning'] if v < 0.50 else THEME['text']
                cells += f'<td style="padding:5px 8px;font-size:14px;color:{color};font-weight:600;">{val}</td>'
            else:
                cells += f'<td style="padding:5px 8px;font-size:14px;color:{muted_clr};">{val}</td>'
        rows += f'<tr style="border-bottom:1px solid {bg_clr};">{cells}</tr>'
    return (
        f'<table style="width:100%;border-collapse:collapse;background:{surface_clr};'
        f'border-radius:8px;overflow:hidden;">'
        f'<thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>'
    )

def html_kpi_card(label, value, color=None, help_text=None):
    """Render a colorized KPI card as HTML."""
    if color is None: color = THEME['text']
    tooltip = f' title="{help_text}" style="cursor:help;"' if help_text else ''
    return f"""
    <div{tooltip} style="
        background: {THEME['surface']};
        border: 1px solid {THEME['border']};
        border-radius: 8px;
        padding: 12px 16px;
        text-align: center;
        height: 100%;
    ">
        <div style="color: {THEME['faint']}; font-size: 12px; margin-bottom: 4px; font-family: 'IBM Plex Mono', monospace;">{label}</div>
        <div style="color: {color}; font-size: 22px; font-weight: 700;">{value}</div>
    </div>
    """

# DURESS MONO Design Tokens
THEME = {
    "bg":          "#181818",
    "surface":     "#1F1F1F",
    "surface2":    "#252525",
    "border":      "#2E2E2E",
    "text":        "#F5F5F5",
    "muted":       "#B8B8B8",
    "faint":       "#8A8A8A",
    "invertBg":    "#F5F5F5",
    "invertText":  "#181818",
    "focus":       "#8EA7B6",
    # Data viz (muted)
    "success":     "#6BC78E",
    "danger":      "#C76B6B",
    "warning":     "#C7B36B",
}

def apply_custom_css():
    st.markdown(f"""
        <style>
        /* ── Global & Typography ─────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600;700&family=Inter:wght@400;500;600;700&display=swap');

        * {{
            font-variant-numeric: tabular-nums;
        }}

        html, body, [data-testid="stAppViewContainer"] {{
            font-family: 'Inter', sans-serif !important;
        }}

        .block-container {{
            padding-top: 24px !important;
            padding-bottom: 48px !important;
            max-width: 1400px;
            background-color: transparent;
        }}

        /* ── Background color ─────────────────────────────────────────────── */
        [data-testid="stApp"] {{
            background-image: url("data:image/jpeg;base64,{BG_TOG_V10_B64}");
            background-size: cover;
            background-position: top center;
            background-attachment: fixed;
            background-repeat: no-repeat;
            background-color: #181818;
        }}
        /* Ensure intermediate container is transparent so we see the stApp background */
        [data-testid="stAppViewContainer"] {{
            background-color: transparent;
        }}
        [data-testid="stApp"]::before {{
            content: "";
            position: fixed;
            inset: 0;
            background-color: rgba(24, 24, 24, 0.65);
            pointer-events: none;
            z-index: 0;
        }}
        /* Make header completely see-through to reveal background underneath */
        [data-testid="stHeader"] {{
            background-color: transparent !important;
        }}

        /* ── Typography hierarchy ─────────────────────────────────────────── */
        h1 {{
            font-family: 'Inter', sans-serif !important;
            font-size: 36px !important;
            font-weight: 500 !important;
            line-height: 1.1 !important;
            margin-bottom: 4px !important;
            margin-top: 0 !important;
            color: {THEME['text']} !important;
            letter-spacing: -1px !important;
        }}

        /* ── Page-level title (smaller than h1, used on each page) ───────── */
        h1.page-title {{
            font-size: 24px !important;
            font-weight: 500 !important;
            margin-bottom: 12px !important;
            letter-spacing: -0.5px !important;
        }}
        h2 {{
            font-family: 'Inter', sans-serif !important;
            font-size: 24px !important;
            font-weight: 600 !important;
            color: {THEME['text']} !important;
            margin-top: 0 !important;
            margin-bottom: 8px !important;
        }}
        h3 {{
            font-family: 'Inter', sans-serif !important;
            font-size: 18px !important;
            font-weight: 500 !important;
            color: {THEME['text']} !important;
            margin-top: 0 !important;
            margin-bottom: 8px !important;
        }}

        /* ── Dividers ─────────────────────────────────────────────────────── */
        hr {{
            margin-top: 12px !important;
            margin-bottom: 12px !important;
            border-color: {THEME['border']} !important;
        }}
        div[data-testid="stVerticalBlock"] > div {{
            padding-bottom: 0.1rem;
        }}

        /* ── Hide Streamlit footer & main menu ────────────────────────────── */
        #MainMenu {{ visibility: hidden; }}
        footer {{ visibility: hidden; }}
        
        /* ── Sidebar shell ────────────────────────────────────────────────── */
        [data-testid="stSidebar"] {{
            background-color: {THEME['surface']};
            border-right: 1px solid {THEME['border']};
        }}
        /* Target ONLY specific text in sidebar. Avoid generic tags like 'span' or 'p' to prevent breaking icons. */
        [data-testid="stSidebar"] [data-testid="stSidebarNav"] span,
        [data-testid="stSidebar"] .stMarkdown p,
        [data-testid="stSidebar"] .stMarkdown span,
        [data-testid="stSidebar"] .stSegmentedControl label,
        [data-testid="stSidebar"] .source-pill {{
            font-family: 'IBM Plex Mono', monospace !important;
        }}
        /* Explicitly force icons back to default if they were caught by any rule */
        [data-testid="stSidebar"] span[data-testid="stIcon"],
        [data-testid="stSidebar"] i,
        [data-testid="stSidebar"] svg {{
            font-family: inherit !important;
        }}

        /* ── Sidebar Nav: title injected via ::before ─────────────────────── */
        [data-testid="stSidebarNav"] {{
            padding-top: 72px;
            position: relative;
        }}
        [data-testid="stSidebarNav"]::before {{
            content: "MTG Premodern Lab";
            display: block;
            position: absolute;
            top: 16px;
            left: 16px;
            right: 16px;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 18px;
            font-weight: 600;
            color: {THEME['text']};
            letter-spacing: -0.3px;
            line-height: 1.2;
            white-space: nowrap;
        }}

        [data-testid="stSidebarNav"] ul {{
            padding-left: 0;
            margin: 0;
        }}
        [data-testid="stSidebarNav"] li {{
            margin-bottom: 2px;
            list-style: none;
        }}
        [data-testid="stSidebarNav"] a,
        [data-testid="stSidebarNav"] span {{
            background-color: transparent !important;
            color: {THEME['muted']} !important;
            border-radius: 10px !important;
            padding: 7px 12px !important;
            font-family: 'IBM Plex Mono', monospace;
            font-size: 14px;
            display: block;
            transition: background 0.15s, color 0.15s;
        }}
        [data-testid="stSidebarNav"] a:hover {{
            background-color: {THEME['surface2']} !important;
            color: {THEME['text']} !important;
        }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background-color: #2A2A2A !important;
            color: {THEME['text']} !important;
            border-left: 2px solid {THEME['text']};
            padding-left: 10px !important;
            font-weight: 600 !important;
        }}

        /* ── Sidebar widgets (Timeframe etc.) – tighten gap after nav ──────── */
        [data-testid="stSidebarContent"] {{
            display: flex;
            flex-direction: column;
        }}
        
        /* Timeframe label */
        [data-testid="stSidebar"] .stSelectbox label {{
            font-family: 'IBM Plex Mono', monospace;
            font-size: 11px;
            color: {THEME['faint']} !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}

        /* ── KPI / Metric cards ───────────────────────────────────────────── */
        [data-testid="stMetric"] {{
            background-color: {THEME['surface']} !important;
            border: 1px solid {THEME['border']} !important;
            border-radius: 10px !important;
            padding: 16px !important;
            box-shadow: none !important;
        }}
        [data-testid="stMetricLabel"] {{
            font-family: 'Inter', sans-serif !important;
            font-size: 12px !important;
            color: {THEME['faint']} !important;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }}
        [data-testid="stMetricValue"] {{
            font-family: 'Inter', sans-serif !important;
            font-size: 22px !important;
            font-weight: 700 !important;
            color: {THEME['text']} !important;
        }}

        /* ── DataFrames / Tables ──────────────────────────────────────────── */
        [data-testid="stDataFrame"] {{
            background-color: {THEME['surface']} !important;
            border: 1px solid {THEME['border']} !important;
            border-radius: 10px !important;
            padding: 0 !important;
            box-shadow: none !important;
        }}
        [data-testid="stDataFrame"] table {{
            border-collapse: collapse;
        }}
        [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {{
            border-bottom: 1px solid {THEME['border']} !important;
            padding: 8px 12px !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 13px !important;
        }}
        [data-testid="stDataFrame"] th {{
            color: {THEME['muted']} !important;
            font-size: 11px !important;
            text-transform: uppercase;
            letter-spacing: 0.06em;
            background-color: {THEME['surface2']} !important;
        }}

        /* ── Plotly chart wrapper card ────────────────────────────────────── */
        [data-testid="stPlotlyChart"] {{
            background-color: {THEME['bg']} !important;
            border-radius: 10px !important;
            box-shadow: inset 0 0 0 1px {THEME['border']} !important;
            overflow: hidden !important;
        }}

        /* ── Buttons ──────────────────────────────────────────────────────── */
        .stButton > button {{
            background: transparent !important;
            border: 1px solid {THEME['border']} !important;
            color: {THEME['text']} !important;
            border-radius: 10px !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            padding: 8px 20px !important;
            transition: all 0.15s ease;
        }}
        .stButton > button:hover {{
            background: {THEME['invertBg']} !important;
            color: {THEME['invertText']} !important;
            border-color: {THEME['invertBg']} !important;
        }}
        .stButton > button:focus {{
            outline: 2px solid {THEME['focus']} !important;
            outline-offset: 2px !important;
        }}

        /* ── Selectbox / Inputs ───────────────────────────────────────────── */
        .stSelectbox div[data-baseweb="select"],
        .stMultiSelect div[data-baseweb="select"],
        .stNumberInput input {{
            background-color: {THEME['surface']} !important;
            border: 1px solid {THEME['border']} !important;
            border-radius: 10px !important;
            color: {THEME['text']} !important;
            font-family: 'Inter', sans-serif !important;
        }}
        .stSelectbox div[data-baseweb="select"] {{
            font-size: 15px !important;
            font-weight: 600 !important;
        }}

        /* Fix multiselect tags */
        [data-baseweb="tag"] {{
            background-color: {THEME['surface2']} !important;
            border: 1px solid {THEME['border']} !important;
            color: {THEME['text']} !important;
            border-radius: 6px !important;
        }}
        [data-baseweb="tag"] span {{ color: {THEME['text']} !important; }}
        [data-baseweb="tag"] [role="presentation"] {{ color: {THEME['muted']} !important; }}

        /* ── Tabs ─────────────────────────────────────────────────────────── */
        [data-testid="stTabs"] [data-baseweb="tab-list"] {{
            gap: 4px;
            border-bottom: 1px solid {THEME['border']};
            background: transparent;
        }}
        [data-testid="stTabs"] [data-baseweb="tab"] {{
            background: transparent !important;
            color: {THEME['muted']} !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 14px !important;
            border: none !important;
            border-radius: 0 !important;
            padding: 8px 16px !important;
            border-bottom: 2px solid transparent !important;
        }}
        [data-testid="stTabs"] [data-baseweb="tab"]:hover {{
            color: {THEME['text']} !important;
            background: {THEME['surface2']} !important;
        }}
        [data-testid="stTabs"] [aria-selected="true"] {{
            color: {THEME['text']} !important;
            border-bottom: 2px solid {THEME['text']} !important;
            background: transparent !important;
        }}

        /* ── Sliders ──────────────────────────────────────────────────────── */
        [data-testid="stSlider"] label {{
            font-family: 'IBM Plex Mono', monospace !important;
            font-size: 12px !important;
            color: {THEME['muted']} !important;
        }}

        /* ── Selectbox un-bold fix ────────────────────────────────────────── */
        div[data-baseweb="select"] span {{
            font-weight: 400 !important;
        }}

        /* ── Info / Warning boxes ─────────────────────────────────────────── */
        [data-testid="stInfo"], [data-testid="stWarning"] {{
            border-radius: 10px !important;
            border: 1px solid {THEME['border']} !important;
            background-color: {THEME['surface']} !important;
        }}

        /* ── Source link (small muted footer in sidebar) ──────────────────── */
        .source-pill {{
            font-size: 11px;
            color: {THEME['faint']};
            font-family: 'IBM Plex Mono', monospace;
        }}
        .source-pill a {{
            color: {THEME['faint']};
            text-decoration: underline;
            text-underline-offset: 2px;
        }}

        /* ── Center Segmented Control ─────────────────────────────────────── */
        [data-testid="stSidebar"] div.stSegmentedControl {{
            display: flex;
            justify-content: center;
        }}

        /* ── Mobile responsive tweaks (≤ 768px) ──────────────────────────── */
        @media (max-width: 768px) {{
            .block-container {{
                padding-left: 12px !important;
                padding-right: 12px !important;
                padding-top: 16px !important;
            }}
            h1.page-title {{
                font-size: 20px !important;
            }}
            /* Stack KPI metrics to 2 columns on mobile */
            [data-testid="column"] {{
                min-width: 45% !important;
            }}
            /* Decklist content grid: single column on mobile */
            .d-content {{
                grid-template-columns: 1fr !important;
            }}
            /* Decklist header/summary: hide less important cols on mobile */
            .d-header, .d-summary {{
                grid-template-columns: 60px 1fr 80px !important;
            }}
            .c-players, .c-event, .c-date, .c-spice {{
                display: none !important;
            }}
        }}
        </style>
    """, unsafe_allow_html=True)


def style_winrate(val):
    """Muted data colors for win rates."""
    if val is None or val == "-" or val == "—":
        return ""
    try:
        if isinstance(val, str) and "%" in val:
            num = float(val.split("%")[0]) / 100
        else:
            num = float(val)

        if num < 0.45:   color = THEME["danger"]
        elif num < 0.49: color = THEME["warning"]
        elif num < 0.51: return f'color: {THEME["text"]}; font-weight: bold;'
        elif num > 0.55: color = THEME["success"]
        else:            color = THEME["text"]

        return f'color: {color}; font-weight: bold;'
    except:
        return ""
