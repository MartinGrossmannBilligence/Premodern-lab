import streamlit as st
import re
import math
import time
import urllib.request
import urllib.parse
import json
import base64
import os
from src.ui import THEME, html_kpi_card

COLORS = ["W", "U", "B", "R", "G"]
COLOR_NAMES = {"W": "White", "U": "Blue", "B": "Black", "R": "Red", "G": "Green"}

# ── Mana symbol images (base64) ───────────────────────────────────────────────
_ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "assets", "mana_symbols")

def _load_symbol_b64(color: str) -> str:
    for ext in ("webp", "png"):
        path = os.path.join(_ASSETS, f"mana_{color}_128.{ext}")
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f"data:image/{ext};base64,{base64.b64encode(f.read()).decode()}"
    return ""

_MANA_B64: dict[str, str] = {c: _load_symbol_b64(c) for c in COLORS}

def mana_img(color: str, size: int = 18) -> str:
    """Return an inline <img> tag for a mana pip symbol."""
    src = _MANA_B64.get(color, "")
    if not src:
        return f"<span style='font-size:{size}px;'>{color}</span>"
    return (
        f"<img src='{src}' width='{size}' height='{size}' "
        f"style='vertical-align:middle;margin:0 1px;' alt='{color}'/>"
    )

def mana_cost_html(pips: dict, size: int = 16) -> str:
    """'{W':1, 'U':1} → two inline pip images."""
    parts = []
    for c in COLORS:
        count = int(math.ceil(pips.get(c, 0)))
        parts.extend([mana_img(c, size)] * count)
    return "".join(parts) or "—"

# Frank Karsten: cheap cantrips allow playing fewer lands (~0.28 each).
# Premodern-legal only (Brainstorm is banned in Premodern; Ponder/Preordain/Serum
# Visions are post-2003 sets but kept for non-Premodern decks).
CANTRIP_SAVINGS = {
    "brainstorm": 0.28,          # banned in Premodern, legal in Legacy/Vintage
    "portent": 0.28,
    "opt": 0.28,
    "sleight of hand": 0.28,
    "impulse": 0.28,
    "peek": 0.28,                # Premodern (Onslaught)
    "serum visions": 0.28,       # post-Premodern
    "ponder": 0.28,              # post-Premodern
    "preordain": 0.28,           # post-Premodern
    "careful study": 0.14,
    "accumulated knowledge": 0.14,
    "telling time": 0.14,
    "scroll rack": 0.14,
    "lat-nam's legacy": 0.14,
    "predict": 0.14,             # Premodern (Odyssey)
    "foreshadow": 0.14,          # Premodern (Onslaught)
}

# Alternate-cost cards: when the "use alternate costs" toggle is on, override
# the face-mana-cost probability with a resource-availability check.
# Types:
#   land_in_play  — need N copies of `land` in play (e.g. Gush bouncing 2 Islands)
#   land_in_hand  — need N copies of `land` in hand, beyond what you've land-dropped
#                   (e.g. Foil discarding Island + card; Thwart pitching 3 Islands)
#   pitch_color   — need a card of `color` in hand to pitch (Misdirection, Unmask)
#   conditional   — situational (Submerge needs opponent's Forest); shown as such
ALT_COST_HANDLERS: dict[str, dict] = {
    # Pitch / bounce blue
    "gush":         {"label": "return 2 Islands", "type": "land_in_play", "land": "island", "count": 2, "turn": 3},
    "foil":         {"label": "discard Island + card", "type": "land_in_hand", "land": "island", "count": 1, "turn": 2},
    "daze":         {"label": "return Island", "type": "land_in_play", "land": "island", "count": 1, "turn": 1},
    "thwart":       {"label": "pitch 3 Islands", "type": "land_in_hand", "land": "island", "count": 3, "turn": 3},
    "misdirection": {"label": "pitch a blue spell", "type": "pitch_color", "color": "U", "turn": 3},
    # Pitch black
    "snuff out":    {"label": "4 life + pitch Swamp", "type": "land_in_hand", "land": "swamp", "count": 1, "turn": 1},
    "unmask":       {"label": "pitch a black card", "type": "pitch_color", "color": "B", "turn": 2},
    "contagion":    {"label": "pitch 2 black cards", "type": "pitch_color", "color": "B", "count": 2, "turn": 2},
    # Conditional
    "submerge":     {"label": "U if opp controls Forest", "type": "conditional", "color": "U", "turn": 1},
    # Free if no lands in hand
    "land grant":   {"label": "reveal hand if no lands", "type": "free_if_no_land", "turn": 1},
}

# Cards that are essentially never cast from hand in the deck's normal game plan.
# When the alt-cost toggle is on, these are flagged "discard fodder / never cast"
# and excluded from the casting probability table.
NEVER_CAST: set[str] = {
    "squee, goblin nabob",       # recurs from graveyard; only discarded, never cast
    "krovikan horror",           # similar recursion role
    "genesis",                    # recurring graveyard creature, rarely hard-cast
}

# Hardcoded produced_mana for all common Premodern lands.
# Keys are lowercase card names. Value: list of color symbols produced.
# This avoids Scryfall API calls for lands (which are finite and well-known).
_LT = "Land"
_BL = "Basic Land"
PREMODERN_LAND_DATA: dict[str, tuple[list[str], str]] = {
    # ── Basics ────────────────────────────────────────────────────────────────
    "plains":                    (["W"], f"{_BL} — Plains"),
    "island":                    (["U"], f"{_BL} — Island"),
    "swamp":                     (["B"], f"{_BL} — Swamp"),
    "mountain":                  (["R"], f"{_BL} — Mountain"),
    "forest":                    (["G"], f"{_BL} — Forest"),
    "snow-covered plains":       (["W"], f"{_BL} — Plains"),
    "snow-covered island":       (["U"], f"{_BL} — Island"),
    "snow-covered swamp":        (["B"], f"{_BL} — Swamp"),
    "snow-covered mountain":     (["R"], f"{_BL} — Mountain"),
    "snow-covered forest":       (["G"], f"{_BL} — Forest"),
    # ── Original Duals ────────────────────────────────────────────────────────
    "tundra":                    (["W", "U"], _LT),
    "underground sea":           (["U", "B"], _LT),
    "badlands":                  (["B", "R"], _LT),
    "taiga":                     (["R", "G"], _LT),
    "savannah":                  (["G", "W"], _LT),
    "scrubland":                 (["W", "B"], _LT),
    "volcanic island":           (["U", "R"], _LT),
    "bayou":                     (["B", "G"], _LT),
    "plateau":                   (["R", "W"], _LT),
    "tropical island":           (["G", "U"], _LT),
    # ── Onslaught Fetch Lands ─────────────────────────────────────────────────
    "flooded strand":            (["W", "U"], _LT),
    "polluted delta":            (["U", "B"], _LT),
    "bloodstained mire":         (["B", "R"], _LT),
    "wooded foothills":          (["R", "G"], _LT),
    "windswept heath":           (["G", "W"], _LT),
    # ── Mirage Fetch Lands ────────────────────────────────────────────────────
    "flood plain":               (["W", "U"], _LT),
    "bad river":                 (["U", "B"], _LT),
    "rocky tar pit":             (["B", "R"], _LT),
    "mountain valley":           (["R", "G"], _LT),
    "grasslands":                (["G", "W"], _LT),
    # ── Pain Lands ────────────────────────────────────────────────────────────
    "adarkar wastes":            (["W", "U"], _LT),
    "underground river":         (["U", "B"], _LT),
    "sulfurous springs":         (["B", "R"], _LT),
    "karplusan forest":          (["R", "G"], _LT),
    "brushland":                 (["G", "W"], _LT),
    "caves of koilos":           (["W", "B"], _LT),
    "shivan reef":               (["U", "R"], _LT),
    "llanowar wastes":           (["B", "G"], _LT),
    "battlefield forge":         (["R", "W"], _LT),
    "yavimaya coast":            (["G", "U"], _LT),
    # ── Invasion Lair Lands (tap for one of three colors) ─────────────────────
    "dromar's cavern":           (["W", "U", "B"], _LT),
    "treva's ruins":             (["G", "W", "U"], _LT),
    "darigaaz's caldera":        (["B", "R", "G"], _LT),
    "crosis's catacombs":        (["U", "B", "R"], _LT),
    "rith's grove":              (["R", "G", "W"], _LT),
    # ── Filter Lands ─────────────────────────────────────────────────────────
    "adarkar wastes":            (["W", "U"], _LT),   # duplicate key safe, last wins
    # ── 5-color / Any-color Lands ─────────────────────────────────────────────
    "city of brass":             (["W", "U", "B", "R", "G"], _LT),
    "undiscovered paradise":     (["W", "U", "B", "R", "G"], _LT),
    "gemstone mine":             (["W", "U", "B", "R", "G"], _LT),
    "reflecting pool":           (["W", "U", "B", "R", "G"], _LT),
    "grand coliseum":            (["W", "U", "B", "R", "G"], _LT),
    "forbidden orchard":         (["W", "U", "B", "R", "G"], _LT),
    "mana confluence":           (["W", "U", "B", "R", "G"], _LT),
    "chromatic lantern":         (["W", "U", "B", "R", "G"], _LT),  # not a land but harmless
    # ── Mono-color Special Lands ─────────────────────────────────────────────
    "tolarian academy":          (["U"], _LT),
    "gaea's cradle":             (["G"], _LT),
    "serra's sanctum":           (["W"], _LT),
    "phyrexian tower":           (["B"], _LT),
    "shivan gorge":              (["R"], _LT),
    "library of alexandria":     (["U"], _LT),
    "high market":               (["W"], _LT),
    "hall of the bandit lord":   (["R"], _LT),
    "den of the bugbear":        (["R"], _LT),
    "cave of koilos":            (["W", "B"], _LT),
    # ── Colorless / Utility Lands (no colored mana production) ───────────────
    "wasteland":                 ([], _LT),
    "strip mine":                ([], _LT),
    "ancient tomb":              ([], _LT),
    "city of traitors":          ([], _LT),
    "rishadan port":             ([], _LT),
    "mishra's factory":          ([], _LT),
    "urza's mine":               ([], _LT),
    "urza's tower":              ([], _LT),
    "urza's power plant":        ([], _LT),
    "maze of ith":               ([], _LT),
    "the tabernacle at pendrell vale": ([], _LT),
    "bazaar of baghdad":         ([], _LT),
    "karakas":                   (["W"], _LT),
    "kjeldoran outpost":         (["W"], _LT),
    "soldevi excavations":       (["U"], _LT),
    "kjeldoran dead":            ([], _LT),  # not a land
    "petrified field":           ([], _LT),
    "dust bowl":                 ([], _LT),
    "ghost quarter":             ([], _LT),
    "horizon canopy":            (["G", "W"], _LT),
    "murmuring bosk":            (["G", "W"], _LT),
    "sea of clouds":             (["W", "U"], _LT),
    "morphic pool":              (["U", "B"], _LT),
    "luxury suite":              (["B", "R"], _LT),
    "spire garden":              (["R", "G"], _LT),
    "bountiful promenade":       (["G", "W"], _LT),
    "tsabo's web":               ([], _LT),   # not a land
    # ── Taplands (Invasion, Apocalypse, etc.) ────────────────────────────────
    "coastal tower":             (["W", "U"], _LT),
    "urborg volcano":            (["U", "B"], _LT),
    "tainted isle":              (["U", "B"], _LT),
    "tainted field":             (["W", "B"], _LT),
    "tainted wood":              (["B", "G"], _LT),
    "tainted peak":              (["B", "R"], _LT),
    "salt marsh":                (["U", "B"], _LT),
    "elfhame palace":            (["G", "W"], _LT),
    "shivan oasis":              (["R", "G"], _LT),
    "irrigation ditch":          (["W", "U"], _LT),
    "geothermal crevice":        (["B", "R"], _LT),
    "peat bog":                  (["B"], _LT),
    "river delta":               (["U", "B"], _LT),
    "tinder farm":               (["R", "G"], _LT),
    "rushwood grove":            (["G", "W"], _LT),
    "sulfur vent":               (["B", "R"], _LT),
    "mountain stronghold":       (["R"], _LT),
    "skyshroud forest":          (["G", "U"], _LT),
}

# Karsten 90%-consistency source minimums: (pip_count, target_turn) → sources needed
# Based on 60-card deck, on the play
KARSTEN_SOURCES = {
    (1, 1): 14, (1, 2): 13, (1, 3): 12, (1, 4): 11,
    (2, 2): 21, (2, 3): 18, (2, 4): 16,
    (3, 3): 23, (3, 4): 20,
}


@st.cache_data(ttl=604800, show_spinner=False)  # 7-day cache, shared across sessions on Cloud
def _scryfall_fetch(card_name: str) -> dict | None:
    """Fetch card data from Scryfall. Retries once on 429 rate-limit."""
    # Check hardcoded land data first — never hits the API for known lands
    key = card_name.lower().strip()
    if key in PREMODERN_LAND_DATA:
        produced, type_line = PREMODERN_LAND_DATA[key]
        return {"object": "card", "name": card_name, "type_line": type_line,
                "mana_cost": "", "produced_mana": produced}

    url = f"https://api.scryfall.com/cards/named?fuzzy={urllib.parse.quote(card_name)}"
    headers = {"User-Agent": "PremodernLab/1.0", "Accept": "application/json"}

    for attempt in range(2):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=8) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt == 0:
                time.sleep(2.0)  # back off and retry once
                continue
            return None  # 404 not found or other error
        except Exception:
            return None
    return None


def _moxfield_fetch(url: str) -> tuple[str, str] | tuple[None, str]:
    """Fetch a Moxfield deck and return (decklist_text, deck_name).
    On error returns (None, error_message).
    Accepts URLs like https://moxfield.com/decks/<id> or just the id."""
    import re as _re
    m = _re.search(r"(?:moxfield\.com/decks/)?([A-Za-z0-9_-]{10,})", url.strip())
    if not m:
        return None, "Could not parse Moxfield URL or deck ID."
    deck_id = m.group(1)
    api_url = f"https://api2.moxfield.com/v3/decks/all/{deck_id}"
    req = urllib.request.Request(api_url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
    except urllib.error.HTTPError as e:
        return None, f"Moxfield returned HTTP {e.code} (deck private or not found?)."
    except Exception as e:
        return None, f"Moxfield fetch failed: {type(e).__name__}: {e}"

    deck_name = data.get("name", deck_id)
    boards = data.get("boards", {}) or {}
    lines: list[str] = []
    for slug, entry in (boards.get("mainboard", {}) or {}).get("cards", {}).items():
        qty = entry.get("quantity", 0)
        card = entry.get("card", {}) or {}
        name = card.get("name", slug)
        if qty > 0:
            lines.append(f"{qty} {name}")
    sb = (boards.get("sideboard", {}) or {}).get("cards", {})
    if sb:
        lines.append("")
        lines.append("SIDEBOARD:")
        for slug, entry in sb.items():
            qty = entry.get("quantity", 0)
            card = entry.get("card", {}) or {}
            name = card.get("name", slug)
            if qty > 0:
                lines.append(f"SB: {qty} {name}")
    if not lines:
        return None, f"Deck '{deck_name}' has no cards (private?)."
    return "\n".join(lines), deck_name


def _parse_decklist(text: str) -> list[tuple[int, str]]:
    cards = []
    for line in text.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("//") or line.startswith("#"):
            continue
        if re.match(r'^SB:', line, re.IGNORECASE):
            continue
        m = re.match(r'^(\d+)x?\s+(.+)$', line)
        if m:
            cards.append((int(m.group(1)), m.group(2).strip()))
    return cards


def _parse_mana_cost(mc: str) -> dict:
    """'{2}{W}{U}' → {'cmc': 4, 'pips': {'W':1,'U':1,...}}"""
    pips = {c: 0 for c in COLORS}
    cmc = 0
    for token in re.findall(r'\{([^}]+)\}', mc.upper()):
        if token.isdigit():
            cmc += int(token)
        elif token in COLORS:
            pips[token] += 1
            cmc += 1
        elif "/" in token:
            # Hybrid mana e.g. {W/U} — counts as 1 CMC, adds 0.5 to each color
            parts = [p for p in token.split("/") if p in COLORS]
            for p in parts:
                pips[p] += 0.5
            cmc += 1
        elif token == "X":
            pass  # X spells: ignore for CMC
        elif token not in ("S", "C", "T"):
            try:
                cmc += int(token)
            except ValueError:
                pass
    return {"cmc": cmc, "pips": pips}


def _hypergeom_at_least(N: int, K: int, n: int, k: int) -> float:
    """P(X >= k) for X ~ Hypergeometric(N, K, n). Draws without replacement."""
    if k <= 0:
        return 1.0
    if K < k:
        return 0.0
    n = min(n, N)
    total = math.comb(N, n)
    if total == 0:
        return 0.0
    prob = sum(
        math.comb(K, i) * math.comb(max(0, N - K), max(0, n - i))
        for i in range(k, min(K, n) + 1)
    ) / total
    return min(1.0, max(0.0, prob))


def show_mana_check():
    st.markdown('<h1 class="page-title">Mana Base Calculator</h1>', unsafe_allow_html=True)
    st.caption(
        "Paste your decklist to get recommended land count, color source checks, "
        "and per-spell casting probability on curve."
    )

    col_input, col_settings = st.columns([0.62, 0.38])

    with col_settings:
        st.subheader("Settings")
        on_draw = st.toggle(
            "On the draw",
            value=False,
            help="On the draw you see 1 extra card — slightly improves consistency.",
        )
        target_pct = st.slider("Target consistency", 50, 99, 90, format="%d%%")
        manual_cantrips = st.toggle(
            "Set cantrip count manually",
            value=False,
            help=(
                "By default, cantrips (Brainstorm, Portent, Opt, Sleight of Hand, Impulse…) "
                "are auto-detected from your decklist. Toggle this on to enter the count yourself."
            ),
        )
        cantrip_manual_value = 0
        if manual_cantrips:
            cantrip_manual_value = st.number_input(
                "Cantrip count",
                min_value=0, max_value=40, value=0, step=1,
                help="Total copies of cheap draw/filter spells that reduce your land requirement by ~0.28 each.",
            )
        use_alt_costs = st.toggle(
            "Use alternate costs",
            value=False,
            help=(
                "Evaluates pitch/bounce alt costs for cards like Gush (return 2 Islands), "
                "Foil (discard Island + card), Daze, Snuff Out, Misdirection, Thwart. "
                "Cards listed as discard fodder (Squee) are excluded from casting probability."
            ),
        )

    with col_input:
        st.subheader("Decklist")
        # ── Moxfield import ──────────────────────────────────────────────
        with st.expander("📥 Import from Moxfield", expanded=False):
            mox_col1, mox_col2 = st.columns([0.75, 0.25])
            with mox_col1:
                mox_url = st.text_input(
                    "Moxfield URL or deck ID",
                    placeholder="https://moxfield.com/decks/Zxt1Lmdx50Sq5NVPsTDnQQ",
                    label_visibility="collapsed",
                )
            with mox_col2:
                mox_btn = st.button("Import", use_container_width=True)
            if mox_btn and mox_url.strip():
                with st.spinner("Fetching from Moxfield…"):
                    imported_text, info = _moxfield_fetch(mox_url)
                if imported_text:
                    st.session_state["mana_check_decklist"] = imported_text
                    st.success(f"Loaded: **{info}** ({imported_text.count(chr(10)) + 1} lines)")
                else:
                    st.error(info)

        st.caption("One card per line: `4 Dark Ritual`  ·  SB: lines are ignored.")
        st.markdown(
            """
            <style>
            div[data-testid="stTextArea"] textarea {
                font-size: 12px !important;
                line-height: 1.35 !important;
                font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        decklist_text = st.text_area(
            "Decklist",
            height=170,
            key="mana_check_decklist",
            placeholder=(
                "4 Dark Ritual\n"
                "4 Hypnotic Specter\n"
                "4 Nevinyrral's Disk\n"
                "4 Brainstorm\n"
                "...\n"
                "20 Swamp"
            ),
            label_visibility="collapsed",
        )
        st.markdown(
            """
            <style>
            div.stButton > button[kind="primary"] {
                background: linear-gradient(135deg, #16a34a 0%, #15803d 100%);
                color: #ffffff;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 2px;
                text-transform: uppercase;
                padding: 14px 28px;
                border: none;
                border-radius: 8px;
                width: 100%;
                box-shadow: 0 4px 14px rgba(22, 163, 74, 0.35);
                transition: all 0.15s ease;
            }
            div.stButton > button[kind="primary"]:hover {
                background: linear-gradient(135deg, #15803d 0%, #166534 100%);
                box-shadow: 0 6px 20px rgba(22, 163, 74, 0.5);
                transform: translateY(-1px);
            }
            div.stButton > button[kind="primary"]:active {
                transform: translateY(0);
                box-shadow: 0 2px 8px rgba(22, 163, 74, 0.4);
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        analyze_btn = st.button("⚡ Analyze Mana", type="primary")

    if not analyze_btn or not decklist_text.strip():
        _how_it_works()
        return

    # ── Parse ─────────────────────────────────────────────────────────────────
    raw_cards = _parse_decklist(decklist_text)
    if not raw_cards:
        st.error("Could not parse decklist. Each line must start with a number: `4 Card Name`.")
        return

    # Deck size = total cards in maindeck (sideboard is excluded by the parser)
    deck_size = sum(q for q, _ in raw_cards)
    if deck_size < 40:
        st.warning(f"Decklist has only {deck_size} cards — minimum legal deck size is 60 (Constructed) or 40 (Limited).")

    # ── Scryfall lookups ──────────────────────────────────────────────────────
    unique_names = list({name for _, name in raw_cards})
    card_data: dict[str, dict] = {}
    not_found: list[str] = []

    prog = st.progress(0, text="Looking up cards on Scryfall…")
    for idx, name in enumerate(unique_names):
        data = _scryfall_fetch(name)
        if data and data.get("object") == "card":
            card_data[name] = data
        else:
            not_found.append(name)
        time.sleep(0.1)  # 100ms between requests — Scryfall recommends ≥50ms
        prog.progress((idx + 1) / len(unique_names), text=f"Scryfall: {name}")
    prog.empty()

    if not_found:
        st.warning(f"Not found on Scryfall (check spelling): {', '.join(not_found)}")

    # ── Classify cards ────────────────────────────────────────────────────────
    lands: list[tuple[int, str, list[str]]] = []       # (qty, name, produced_colors)
    spells: list[tuple[int, str, float, dict]] = []     # (qty, name, cmc, pips)
    mana_perms: list[tuple[int, str, list[str]]] = []   # non-land mana permanents (Mox, dorks…)
    auto_cantrip_adj = 0.0
    auto_cantrip_count = 0
    auto_cantrip_list: list[tuple[int, str, float]] = []  # (qty, name, savings_per_copy)

    for qty, name in raw_cards:
        d = card_data.get(name)
        if d is None:
            continue
        type_line = d.get("type_line", "")

        if "Land" in type_line:
            produced = [c for c in d.get("produced_mana", []) if c in COLORS]
            lands.append((qty, name, produced))
        else:
            # Handle split/MDFC cards — take first face mana cost
            mc = d.get("mana_cost") or ""
            if not mc and "card_faces" in d:
                mc = d["card_faces"][0].get("mana_cost", "")
            parsed = _parse_mana_cost(mc)
            spells.append((qty, name, parsed["cmc"], parsed["pips"]))
            if name.lower() in CANTRIP_SAVINGS:
                savings_per_copy = CANTRIP_SAVINGS[name.lower()]
                auto_cantrip_adj += qty * savings_per_copy
                auto_cantrip_count += qty
                auto_cantrip_list.append((qty, name, savings_per_copy))
            # Non-land permanents that produce colored mana count as sources
            # (Mox Diamond, Birds of Paradise, Chrome Mox, etc.)
            # Exclude Instants and Sorceries (Dark Ritual is one-shot, not a permanent source)
            if "Instant" not in type_line and "Sorcery" not in type_line:
                produced = [c for c in d.get("produced_mana", []) if c in COLORS]
                if produced:
                    mana_perms.append((qty, name, produced))

    # Use manual cantrip count if toggle is on, otherwise use auto-detected
    if manual_cantrips:
        cantrip_adj = cantrip_manual_value * 0.28
    else:
        cantrip_adj = auto_cantrip_adj

    # ── Aggregate ─────────────────────────────────────────────────────────────
    total_lands = sum(q for q, _, _ in lands)
    sources: dict[str, int] = {c: 0 for c in COLORS}
    for qty, _, produced in lands:
        for c in produced:
            sources[c] += qty
    # Add mana-producing non-land permanents to colored sources
    for qty, _, produced in mana_perms:
        for c in produced:
            sources[c] += qty

    # Total mana sources = lands + mana permanents (Moxen etc. also pay generic mana)
    total_mana_sources = total_lands + sum(q for q, _, _ in mana_perms)

    # Count basic lands separately — needed for alt-cost checks
    # (Gush bouncing Islands, Foil pitching Island, Snuff Out pitching Swamp, etc.)
    basic_lands = {"plains": 0, "island": 0, "swamp": 0, "mountain": 0, "forest": 0}
    for qty, name, _ in lands:
        key = name.lower().strip().replace("snow-covered ", "")
        if key in basic_lands:
            basic_lands[key] += qty

    # Pre-compute count of spells per color, used by pitch-color alt costs
    color_spell_count = {c: 0 for c in COLORS}
    for q, _, _, p in spells:
        for c in COLORS:
            if p.get(c, 0) >= 0.5:
                color_spell_count[c] += q

    spell_qty = sum(q for q, _, _, _ in spells)
    avg_cmc = sum(q * cmc for q, _, cmc, _ in spells) / spell_qty if spell_qty else 0

    recommended_raw = 19.59 + 1.90 * avg_cmc - cantrip_adj
    recommended = max(14, min(28, round(recommended_raw)))

    # ── KPI row ───────────────────────────────────────────────────────────────
    st.divider()
    k1, k2, k3, k4, k5 = st.columns(5)

    delta = total_lands - recommended
    if abs(delta) <= 1:
        land_color = THEME["success"]
        delta_str = f" (+{delta})" if delta > 0 else " (✓)"
    elif abs(delta) <= 2:
        land_color = THEME["warning"]
        delta_str = f" ({'+' if delta > 0 else ''}{delta})"
    else:
        land_color = THEME["danger"]
        delta_str = f" ({'+' if delta > 0 else ''}{delta})"

    with k1:
        st.markdown(html_kpi_card("Total Cards", str(sum(q for q, _ in raw_cards))), unsafe_allow_html=True)
    with k2:
        st.markdown(html_kpi_card("Lands in Deck", f"{total_lands}{delta_str}", color=land_color), unsafe_allow_html=True)
    with k3:
        st.markdown(html_kpi_card("Recommended Lands", str(recommended)), unsafe_allow_html=True)
    with k4:
        st.markdown(html_kpi_card("Avg CMC (spells)", f"{avg_cmc:.2f}"), unsafe_allow_html=True)
    if manual_cantrips:
        cantrip_label = "Cantrip Savings"
        cantrip_value = f"−{cantrip_adj:.1f} ({cantrip_manual_value} cards · manual)"
    else:
        cantrip_label = "Cantrip Savings"
        cantrip_value = f"−{cantrip_adj:.1f} ({auto_cantrip_count} cards)"
    with k5:
        st.markdown(html_kpi_card(cantrip_label, cantrip_value), unsafe_allow_html=True)

    if not manual_cantrips and auto_cantrip_list:
        with st.expander(f"Detected cantrips ({auto_cantrip_count} copies, −{cantrip_adj:.2f} lands)"):
            rows = "".join(
                f"<tr><td style='padding:4px 10px;font-size:13px;'>{q}× {n}</td>"
                f"<td style='padding:4px 10px;font-size:13px;color:{THEME['muted']};text-align:right;'>"
                f"−{q*sv:.2f} lands ({sv} per copy)</td></tr>"
                for q, n, sv in sorted(auto_cantrip_list, key=lambda x: -x[0]*x[2])
            )
            st.markdown(
                f"<table style='width:100%;border-collapse:collapse;'>{rows}</table>",
                unsafe_allow_html=True,
            )

    # ── Color source check ────────────────────────────────────────────────────
    used_colors = [c for c in COLORS if any(p.get(c, 0) >= 0.5 for _, _, _, p in spells)]

    if used_colors:
        st.markdown("### Color Source Check")
        caption = "Karsten minimums for 90% consistency on the play, 60 cards. Green = threshold met · Red = below threshold."
        if mana_perms:
            perm_names = ", ".join(f"{q}× {n}" for q, n, _ in mana_perms)
            caption += f"  ·  Sources include mana-producing permanents: {perm_names}."
        st.caption(caption)

        _bg     = THEME["surface"]
        _border = THEME["border"]
        _faint  = THEME["faint"]
        _muted  = THEME["muted"]
        _ok     = THEME["success"]
        _bad    = THEME["danger"]

        cols = st.columns(len(used_colors))
        for col, c in zip(cols, used_colors):
            actual = sources[c]
            relevant: set[tuple[int, int]] = set()
            for _, _, cmc, pips in spells:
                pip_f = pips.get(c, 0)
                if pip_f >= 0.5:
                    pip_i = min(3, max(1, int(math.ceil(pip_f))))
                    turn_i = min(4, max(1, int(cmc)))
                    relevant.add((pip_i, turn_i))

            with col:
                rows_html = ""
                for pip_i, turn_i in sorted(relevant):
                    needed = KARSTEN_SOURCES.get((pip_i, turn_i))
                    if needed is None:
                        continue
                    ok = actual >= needed
                    clr = _ok if ok else _bad
                    pips_imgs = "".join(mana_img(c, 16) for _ in range(pip_i))
                    icon = "✓" if ok else "✗"
                    rows_html += (
                        f"<div style='display:grid;grid-template-columns:18px 32px 1fr auto;"
                        f"align-items:center;gap:6px;padding:5px 0;"
                        f"border-bottom:1px solid {_border};'>"
                        # check icon
                        f"<span style='font-size:14px;color:{clr};font-weight:700;'>{icon}</span>"
                        # turn badge
                        f"<span style='font-size:11px;color:{_faint};font-family:monospace;"
                        f"background:{_border};border-radius:4px;padding:1px 5px;'>T{turn_i}</span>"
                        # pip symbols
                        f"<span style='display:flex;align-items:center;gap:2px;'>{pips_imgs}</span>"
                        # need / have
                        f"<span style='font-size:12px;white-space:nowrap;'>"
                        f"<span style='color:{_faint};'>need </span>"
                        f"<span style='color:{_muted};font-weight:600;'>{needed}</span>"
                        f"<span style='color:{_faint};'>  have </span>"
                        f"<span style='color:{clr};font-weight:700;'>{actual}</span>"
                        f"</span>"
                        f"</div>"
                    )

                sym = mana_img(c, 22)
                st.markdown(
                    f"<div style='background:{_bg};border:1px solid {_border};"
                    f"border-radius:8px;padding:14px 16px;'>"
                    f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px;'>"
                    f"{sym}"
                    f"<span style='font-size:13px;color:{_faint};'>{COLOR_NAMES[c]} sources</span>"
                    f"<span style='font-size:24px;font-weight:700;margin-left:auto;'>{actual}</span>"
                    f"</div>"
                    f"{rows_html}</div>",
                    unsafe_allow_html=True,
                )

    # ── Spell probability table ───────────────────────────────────────────────
    st.markdown("### Casting Probability on Curve")
    st.caption(
        f"P(can cast) on turn = CMC, {'on the draw' if on_draw else 'on the play'}. "
        f"Target: {target_pct}%."
    )

    _t   = THEME["text"]
    _mut = THEME["muted"]
    _fnt = THEME["faint"]
    _brd = THEME["border"]
    _sur = THEME["surface"]
    _bg2 = THEME["bg"]
    _tgt = target_pct / 100

    table_rows = ""
    never_cast_rows = ""
    for qty, name, cmc, pips in sorted(spells, key=lambda x: (x[2], x[1])):
        cmc_int = int(cmc)
        mc_html = mana_cost_html(pips, 15)
        key = name.lower().strip()

        # ── Alt-cost / never-cast branches (only when toggle is on) ─────────────
        if use_alt_costs and key in NEVER_CAST:
            never_cast_rows += (
                f"<tr style='border-bottom:1px solid {_bg2};opacity:0.55;'>"
                f"<td style='padding:6px 10px;font-size:14px;'>{qty}× {name}</td>"
                f"<td style='padding:6px 10px;font-size:13px;color:{_mut};text-align:center;'>{cmc_int}</td>"
                f"<td style='padding:6px 10px;'>{mc_html}</td>"
                f"<td style='padding:6px 10px;font-size:13px;color:{_mut};font-style:italic;'>"
                f"discard fodder</td>"
                f"<td style='padding:6px 10px;font-size:12px;color:{_fnt};'>never cast</td>"
                f"</tr>"
            )
            continue

        if use_alt_costs and key in ALT_COST_HANDLERS:
            handler = ALT_COST_HANDLERS[key]
            alt_turn = handler.get("turn", max(1, cmc_int))
            alt_cards_seen = min(7 + (alt_turn if on_draw else alt_turn - 1), int(deck_size))
            alt_prob = 0.0
            htype = handler["type"]

            if htype == "land_in_play":
                # Need N copies of the basic land in play by alt_turn.
                K = basic_lands.get(handler["land"], 0)
                alt_prob = _hypergeom_at_least(int(deck_size), K, alt_cards_seen, handler["count"])
            elif htype == "land_in_hand":
                # Need N copies in hand (beyond what you've played as land).
                # Approximation: drew at least N + (alt_turn - 1) of that land — i.e. one
                # extra survives in hand after each turn's natural land drop.
                K = basic_lands.get(handler["land"], 0)
                need = handler["count"] + max(0, alt_turn - 1)
                alt_prob = _hypergeom_at_least(int(deck_size), K, alt_cards_seen, need)
            elif htype == "pitch_color":
                # Need a card of `color` in hand (other than this card itself).
                # Approximation: at least N+1 cards of that color drawn (one is this spell).
                color = handler["color"]
                pip_qty = handler.get("count", 1) + qty  # +qty roughly for "self exclusion"
                K = max(0, color_spell_count.get(color, 0))
                alt_prob = _hypergeom_at_least(int(deck_size), K, alt_cards_seen, handler.get("count", 1) + 1)
            elif htype == "free_if_no_land":
                # Land Grant: free if no lands in hand. Approximation: P(0 lands in 7).
                alt_prob = 1.0 - _hypergeom_at_least(int(deck_size), total_lands, 7, 1)
            elif htype == "conditional":
                # Submerge etc. — situational. Show as "depends".
                alt_prob = float("nan")

            label = handler["label"]
            if alt_prob != alt_prob:  # NaN
                prob_color, prob_text, bn = _mut, "depends", f"alt: {label}"
            else:
                prob_color = (THEME["success"] if alt_prob >= _tgt
                              else THEME["warning"] if alt_prob >= _tgt - 0.10
                              else THEME["danger"])
                prob_text = f"{alt_prob:.1%}"
                bn = f"alt: {label} (T{alt_turn})"

            table_rows += (
                f"<tr style='border-bottom:1px solid {_bg2};'>"
                f"<td style='padding:6px 10px;font-size:14px;'>{qty}× {name}</td>"
                f"<td style='padding:6px 10px;font-size:13px;color:{_mut};text-align:center;'>{cmc_int}</td>"
                f"<td style='padding:6px 10px;'>{mc_html}</td>"
                f"<td style='padding:6px 10px;font-size:15px;font-weight:700;color:{prob_color};'>"
                f"{prob_text}</td>"
                f"<td style='padding:6px 10px;font-size:12px;color:{_mut};'>{bn}</td>"
                f"</tr>"
            )
            continue

        if cmc == 0:
            table_rows += (
                f"<tr style='border-bottom:1px solid {_bg2};'>"
                f"<td style='padding:6px 10px;font-size:14px;'>{qty}× {name}</td>"
                f"<td style='padding:6px 10px;font-size:13px;color:{_mut};text-align:center;'>0</td>"
                f"<td style='padding:6px 10px;'>{mc_html}</td>"
                f"<td style='padding:6px 10px;font-size:14px;font-weight:600;"
                f"color:{THEME['success']};'>100%</td>"
                f"<td style='padding:6px 10px;font-size:13px;color:{_mut};'>—</td>"
                f"</tr>"
            )
            continue

        turn = max(1, cmc_int)
        cards_seen = min(7 + (turn if on_draw else turn - 1), int(deck_size))

        # Count pips (colored mana required)
        total_pips = sum(
            max(1, int(math.ceil(pips.get(c, 0))))
            for c in COLORS if pips.get(c, 0) >= 0.5
        )
        generic_mana = max(0, cmc_int - total_pips)

        # Colored source probabilities
        color_probs: dict[str, float] = {}
        for c in COLORS:
            pip_f = pips.get(c, 0)
            if pip_f >= 0.5:
                pip_needed = max(1, int(math.ceil(pip_f)))
                color_probs[c] = _hypergeom_at_least(
                    int(deck_size), sources[c], cards_seen, pip_needed
                )

        # Generic mana check — only needed when cost has {1},{2},... beyond colored pips.
        # If CMC == total pips, colored sources ARE the mana (e.g. Island satisfies {U}
        # and the land drop simultaneously), so a separate land check would double-count
        # failures and underestimate the probability.
        if generic_mana > 0:
            land_prob = _hypergeom_at_least(
                int(deck_size), total_mana_sources, cards_seen, cmc_int
            )
        else:
            land_prob = 1.0

        combined = land_prob
        for p in color_probs.values():
            combined *= p

        # Color: green if on/above target, yellow if within 10pp below, red otherwise
        if combined >= _tgt:
            prob_color = THEME["success"]
        elif combined >= _tgt - 0.10:
            prob_color = THEME["warning"]
        else:
            prob_color = THEME["danger"]

        mana_label = "Mana sources" if mana_perms else "Lands"
        all_factors = {
            **({mana_label: land_prob} if generic_mana > 0 else {}),
            **{COLOR_NAMES[c]: p for c, p in color_probs.items()},
        }
        bottleneck = min(all_factors, key=all_factors.get) if all_factors else mana_label
        bottleneck_pct = all_factors.get(bottleneck, 1.0)
        bottleneck_html = (
            f"<span style='color:{_mut};'>{bottleneck} ({bottleneck_pct:.1%})</span>"
            if combined < _tgt else "—"
        )

        table_rows += (
            f"<tr style='border-bottom:1px solid {_bg2};'>"
            f"<td style='padding:6px 10px;font-size:14px;'>{qty}× {name}</td>"
            f"<td style='padding:6px 10px;font-size:13px;color:{_mut};text-align:center;'>{cmc_int}</td>"
            f"<td style='padding:6px 10px;'>{mc_html}</td>"
            f"<td style='padding:6px 10px;font-size:15px;font-weight:700;color:{prob_color};'>"
            f"{combined:.1%}</td>"
            f"<td style='padding:6px 10px;font-size:13px;'>{bottleneck_html}</td>"
            f"</tr>"
        )

    if table_rows:
        headers = ["Card", "CMC", "Mana Cost", "P (on curve)", "Bottleneck"]
        header_html = "".join(
            f"<th style='padding:7px 10px;text-align:left;border-bottom:1px solid {_brd};"
            f"color:{_fnt};font-size:12px;font-weight:500;'>{h}</th>"
            for h in headers
        )
        st.markdown(
            f"<table style='width:100%;border-collapse:collapse;background:{_sur};"
            f"border-radius:8px;overflow:hidden;'>"
            f"<thead><tr>{header_html}</tr></thead>"
            f"<tbody>{table_rows}{never_cast_rows}</tbody></table>",
            unsafe_allow_html=True,
        )
        if use_alt_costs and (never_cast_rows or any(
            n.lower().strip() in ALT_COST_HANDLERS for _, n, _, _ in spells
        )):
            st.caption(
                "Alt-cost rows show probability of meeting the alternate cost resource "
                "(e.g. having 2 Islands in play for Gush) by the earliest realistic turn."
            )

    # ── Methodology ───────────────────────────────────────────────────────────
    with st.expander("Methodology"):
        st.markdown(f"""
**Hypergeometric distribution** — correct model for sampling without replacement.

Cards seen by turn *N* ({'on draw' if on_draw else 'on play'}): 7 + {'N' if on_draw else 'N−1'}.

**Colored pips only (e.g. {{U}}, {{U}}{{U}}):**
P = P(draw ≥ k blue sources). No separate land check — an Island satisfies both the pip and the land drop simultaneously, so multiplying them would double-count failures.

**Generic mana in cost (e.g. {{1}}{{U}}, {{2}}):**
P = P(draw ≥ k colored sources) × P(draw ≥ CMC total mana sources).
Total mana sources = lands + mana-producing permanents (Mox Diamond etc.).

Multi-color is treated as independent per color (slight underestimate when colors share dual lands).

**Land recommendation**: `19.59 + 1.90 × avgCMC − cantrip_adjustment`
Frank Karsten 2022 regression. Cantrips: −{list(CANTRIP_SAVINGS.values())[0]} per copy.

**Source minimums** (Karsten, 90%, 60 cards, on the play):
T1 1-pip → 14  ·  T2 1-pip → 13  ·  T2 2-pip → 21  ·  T3 1-pip → 12  ·  T3 2-pip → 18  ·  T3 3-pip → 23
        """)


def _how_it_works():
    st.divider()
    st.markdown("#### How it works")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**1. Paste decklist**")
        st.caption("Standard `4 Card Name` format. Each card is looked up on Scryfall automatically to get mana cost and land color production.")
    with c2:
        st.markdown("**2. Hypergeometric math**")
        st.caption("For each spell, calculates P(have enough lands AND enough colored sources) by turn = CMC. Based on Frank Karsten's methodology.")
    with c3:
        st.markdown("**3. Karsten land formula**")
        st.caption("`19.59 + 1.90 × avgCMC` minus cantrip adjustment. Each Portent / Brainstorm / Opt in your list saves ~0.28 lands.")
