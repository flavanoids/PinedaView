# SPDX-License-Identifier: Apache-2.0
"""Theme palettes.

A trimmed set carried over from PinedaDisplay's ``CARD_THEMES`` — enough for the
view model to name a theme and hand the client its colours. Phase 03 extracts
the full set into ``packages/tokens`` and generates the CSS variables; this
module is the interim source of truth the API serves.
"""

from __future__ import annotations

import json
import logging
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_HEX = r"^#[0-9a-fA-F]{6}$"

# Typefaces a profile or a theme of your own can wear. Mirrors FONTS in
# packages/tokens/src/index.ts; each maps to the bundled file's stem, for the
# menu's specimens.
FONTS = {
    "google_sans_flex": "GoogleSansFlex",
    "atkinson_next": "AtkinsonHyperlegibleNext",
    "zalando_sans": "ZalandoSans",
    "geist": "Geist",
    "mona_sans": "MonaSans",
    "inter": "Inter",
    "instrument_sans": "InstrumentSans",
    "hanken_grotesk": "HankenGrotesk",
    "schibsted_grotesk": "SchibstedGrotesk",
    "host_grotesk": "HostGrotesk",
    "parkinsans": "Parkinsans",
    "funnel_display": "FunnelDisplay",
    "unbounded": "Unbounded",
    "bricolage": "BricolageGrotesque",
    "fredoka": "Fredoka",
    "instrument_serif": "InstrumentSerif",
    "young_serif": "YoungSerif",
    "playfair": "Playfair",
    "newsreader": "Newsreader",
    "geist_mono": "GeistMono",
    "caveat": "Caveat",
    "pixelify_sans": "PixelifySans",
    "jacquard_24": "Jacquard24",
    "fraunces": "Fraunces",  # the menu's headings only, not pickable
    "roboto": "Roboto",
    "aileron": "Aileron",
}
# "" goes back to the theme's own typeface.
FontSetting = Literal[
    "",
    "google_sans_flex",
    "atkinson_next",
    "zalando_sans",
    "geist",
    "mona_sans",
    "inter",
    "instrument_sans",
    "hanken_grotesk",
    "schibsted_grotesk",
    "host_grotesk",
    "parkinsans",
    "funnel_display",
    "unbounded",
    "bricolage",
    "fredoka",
    "instrument_serif",
    "young_serif",
    "playfair",
    "newsreader",
    "geist_mono",
    "caveat",
    "pixelify_sans",
    "jacquard_24",
    "roboto",
    "aileron",
]


def _shade(hex_color: str, factor: float) -> str:
    """Scale each RGB channel by ``factor`` (<1 darkens, >1 lightens)."""
    h = hex_color.lstrip("#")
    channels = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return "#" + "".join(f"{max(0, min(255, round(c * factor))):02x}" for c in channels)


class Theme(BaseModel):
    name: str
    label: str
    blurb: str
    stage: str
    on_stage: str
    accent: str
    on_card: str
    cards: dict[str, str]  # slot name -> top-of-gradient hex
    # "solid" (default) or "glass" — the client reads this to switch the card
    # surface treatment (translucency, backdrop blur, specular rim, wallpaper).
    surface: str = "solid"
    # Name of this theme's dark/night counterpart in THEMES, if it has one.
    # Driven by sun.py's sunrise/sunset check in view.py — a theme with no
    # night variant just stays as-is after dark.
    night: str | None = None
    # Made by someone in the menu (stored in the registry), not built in.
    custom: bool = False
    # A typeface the theme wears (a FONTS id). Only themes of your own set
    # one; a profile's own font still wins over it.
    font: str | None = None


def _theme(
    name: str,
    label: str,
    blurb: str,
    *,
    stage: str,
    on_stage: str,
    accent: str,
    on_card: str,
    weather: str,
    clock: str,
    affirmation: str,
    phrase: str,
    moon: str | None = None,
    surface: str = "solid",
    night: str | None = None,
) -> Theme:
    cards = {
        "weather": weather,
        "clock": clock,
        "affirmation": affirmation,
        "phrase": phrase,
        "forecast": clock,
        # A step darker than weather so the two don't read as the same tile
        # when both are on screen (weather up top, now-playing on the trailing
        # row).
        "nowPlaying": _shade(weather, 0.85),
        "countdown": clock,
    }
    if moon is not None:
        cards["moon"] = moon
    return Theme(
        name=name,
        label=label,
        blurb=blurb,
        stage=stage,
        on_stage=on_stage,
        accent=accent,
        on_card=on_card,
        cards=cards,
        surface=surface,
        night=night,
    )


THEMES: dict[str, Theme] = {
    t.name: t
    for t in (
        _theme(
            "quiet_canvas",
            "Quiet Canvas",
            "Cloud Dancer minimalism — warm graphite on black.",
            stage="#000000",
            on_stage="#f4efe5",
            accent="#e7a34a",
            on_card="#f4efe5",
            weather="#3a3732",
            clock="#282622",
            affirmation="#645e54",
            phrase="#544e44",
        ),
        _theme(
            "warm",
            "Warm",
            "Sage, hot pink and lavender on warm paper.",
            stage="#f5f0e8",
            on_stage="#2a2622",
            accent="#e7a34a",
            on_card="#ffffff",
            weather="#d84882",
            clock="#305a22",
            affirmation="#a888c4",
            phrase="#7aa862",
            night="warm_night",
        ),
        _theme(
            "blush",
            "Blush",
            "Dusty rose and tea rose, monochrome and quiet — no green, no gold.",
            # Every hue stays in the analogous pink/rose band (~330°-350°),
            # varying only lightness/saturation for contrast between cards —
            # a tonal palette rather than a multi-hue one, so nothing reads
            # as "accent color" except pink itself. Dusty rose + tea rose are
            # both 2026 soft-neutral trend picks (see the OLED theme block
            # below for the wider trend-color set this app draws from).
            stage="#faf1ef",  # warm pink-white, a blush "Cloud Dancer"
            on_stage="#4a2e36",  # deep muted plum-brown, not pure black
            accent="#c2607e",  # dusty rose — the one saturated note
            on_card="#402530",
            weather="#e8aebe",  # rose pink — the anchor card
            clock="#f3d9d2",  # tea rose — warm, pale, neutral-leaning
            affirmation="#e3c6d6",  # soft mauve pink
            phrase="#edd3de",  # pale pink-mauve, lighter kin of affirmation
            moon="#d6b8c4",  # dustier mauve-rose for the night card
            night="blush_night",
        ),
        _theme(
            "blush_night",
            "Blush (Night)",
            "The same dusty rose and tea rose, deepened for after dark.",
            # Same analogous pink/rose hue band as "blush", just pushed to low
            # lightness/high-ish saturation instead of pale/desaturated — a
            # dark duotone twin, not a different palette. Text flips light
            # (on_stage/on_card) since the cards are now the dark element.
            stage="#241820",  # near-black rose, not pure black — keeps hue
            on_stage="#f3dbe3",  # pale warm pink text
            accent="#e6789c",  # brighter dusty rose so it still pops at night
            on_card="#f6e0e8",
            weather="#7a3b52",  # deep rose — the anchor card
            clock="#5c3038",  # deep tea-rose brown-red
            affirmation="#6e4258",  # deep mauve
            phrase="#5e3648",  # deep pink-mauve, kin of affirmation
            moon="#4a2c3c",  # deepest mauve for the night card
        ),
        _theme(
            "ocean",
            "Ocean",
            "Cool blues on a pale tide.",
            stage="#e8f0f5",
            on_stage="#12303f",
            accent="#e7a34a",
            on_card="#ffffff",
            weather="#2a8aaf",
            clock="#145870",
            affirmation="#87b4c3",
            phrase="#3a738a",
            night="ocean_night",
        ),
        _theme(
            "cocoa_ember",
            "Cocoa Ember",
            "Cocoa Powder and Muskmelon on black.",
            stage="#000000",
            on_stage="#f0e2d6",
            accent="#e8874a",
            on_card="#f0e2d6",
            weather="#4a2e20",
            clock="#362014",
            affirmation="#563428",
            phrase="#603a18",
        ),
        _theme(
            "forest",
            "Forest",
            "Moss and pine on a green-tinted stage.",
            stage="#ebf2e8",
            on_stage="#1a3312",
            accent="#e7a34a",
            on_card="#ffffff",
            weather="#488e58",
            clock="#264a1a",
            affirmation="#91af82",
            phrase="#587d48",
            night="forest_night",
        ),
        _theme(
            "liquid_glass",
            "Liquid Glass",
            "Frosted panes floating over a dawn sky — SF type, iOS depth.",
            stage="#aab6de",
            on_stage="#232a44",
            accent="#0a6cdb",
            on_card="#1b2036",
            weather="#5b7fc7",
            clock="#7d84b8",
            affirmation="#b98fb0",
            phrase="#7fa8c4",
            moon="#3d4a86",
            surface="glass",
            night="liquid_glass_night",
        ),
        _theme(
            "material",
            "Material",
            "Android-style tonal surfaces, flat and light.",
            stage="#f5f2f7",
            on_stage="#1c1b1f",
            accent="#7a5cff",
            on_card="#1c1b1f",
            weather="#e7deff",
            clock="#dbe7ff",
            affirmation="#ffd8ea",
            phrase="#d7f0dc",
            night="material_night",
        ),
        _theme(
            "halloween",
            "Halloween",
            "Pumpkin, slime green, candy corn and violet on bone paper — Bricolage Grotesque type.",
            # "groovy" re-dyed slot for slot, so type (tokens.css shares its
            # Bricolage Grotesque block) and structure are unchanged: rust ->
            # pumpkin, olive -> slime green, mustard -> candy corn, chocolate
            # -> violet, dark teal moon -> aubergine. Each card's contrast
            # with the cream on_card text matches or beats groovy's.
            stage="#f3e8d6",  # bone / old parchment
            on_stage="#2a1a26",  # near-black with a purple cast
            accent="#ff7a1a",  # jack-o'-lantern orange
            on_card="#fff6e6",
            weather="#d0561a",  # pumpkin — the anchor card
            clock="#5a7328",  # slime green
            affirmation="#e0a020",  # candy corn
            phrase="#7a4f9e",  # witchy violet
            moon="#3b2248",  # aubergine night
            night="halloween_night",
        ),
        _theme(
            "groovy",
            "Groovy",
            "Burnt orange, olive and mustard on warm paper — Bricolage Grotesque type.",
            # A 70s palette (rust, avocado, harvest gold, chocolate) kept from
            # tipping into pastiche by a punchier, more saturated accent than
            # the era actually used and a genuinely modern grotesque for type
            # (see tokens.css's [data-theme="groovy"] block) instead of a
            # script or slab face — "groovy" in hue, not in lettering.
            stage="#f6ead2",
            on_stage="#3b2314",
            accent="#ff6b35",
            on_card="#fff6e6",
            weather="#d94f2b",
            clock="#586b34",
            affirmation="#dba233",
            phrase="#8a4b2e",
            moon="#2e3b3a",
            night="groovy_night",
        ),
    )
}

# ── Night twins ─────────────────────────────────────────────────────────────
# Each light theme's after-dark counterpart, swapped in at sunset and back at
# sunrise (view._resolve_theme_name + sun.SunScheduler). Same recipe as
# blush_night: keep every hue, drop the stage to a near-black tinted with the
# theme's own colour, deepen the cards until light text sits on them, and lift
# the accent a step so it still reads. quiet_canvas and cocoa_ember are already
# dark-stage themes, so they stay as they are.
_NIGHTS = (
    _theme(
        "warm_night",
        "Warm (Night)",
        "Sage, hot pink and lavender, deepened for after dark.",
        stage="#1b1713",  # warm espresso, not black
        on_stage="#f2e9dc",
        accent="#f0b560",
        on_card="#f7efe6",
        weather="#7c2a4c",  # deep hot pink
        clock="#1f3a17",  # deep sage
        affirmation="#4e3d63",  # deep lavender
        phrase="#3b5430",
    ),
    _theme(
        "ocean_night",
        "Ocean (Night)",
        "The same blues at low tide after dark.",
        stage="#0a141b",
        on_stage="#d6e7f0",
        accent="#f0b560",
        on_card="#e6f2f8",
        weather="#175066",
        clock="#0c3242",
        affirmation="#2c5462",
        phrase="#1e4454",
        moon="#15233a",
    ),
    _theme(
        "forest_night",
        "Forest (Night)",
        "Moss and pine under a dark canopy.",
        stage="#0d140c",
        on_stage="#dbe8d4",
        accent="#f0b560",
        on_card="#eef5ea",
        weather="#2a5434",
        clock="#16290f",
        affirmation="#3e5535",
        phrase="#2d4526",
        moon="#1a2a26",
    ),
    _theme(
        "liquid_glass_night",
        "Liquid Glass (Night)",
        "Frosted panes over a dusk-to-midnight sky.",
        stage="#141a33",
        on_stage="#e3e8fa",
        accent="#5aa2ff",
        on_card="#eef1fb",
        weather="#34518f",
        clock="#3f4478",
        affirmation="#6b4a6a",
        phrase="#335878",
        moon="#1e2552",
        surface="glass",
    ),
    _theme(
        "material_night",
        "Material (Night)",
        "Android's dark tonal surfaces.",
        # Material 3's dark scheme: the pastel containers become their deep
        # tonal counterparts and the text flips light.
        stage="#141218",
        on_stage="#e6e0e9",
        accent="#cfbcff",
        on_card="#ece6f0",
        weather="#3e3561",
        clock="#2c3a5a",
        affirmation="#5a3346",
        phrase="#2e4a37",
    ),
    _theme(
        "halloween_night",
        "Halloween (Night)",
        "Pumpkin, slime and candy corn glowing in the dark.",
        stage="#150d17",  # aubergine black
        on_stage="#f3e3cf",
        accent="#ff8a2a",  # lit jack-o'-lantern
        on_card="#fff1dc",
        weather="#7a2e0c",  # ember pumpkin
        clock="#34451a",  # deep slime
        affirmation="#7a5210",  # burnt candy corn
        phrase="#45285e",  # deep violet
        moon="#23132e",
    ),
    _theme(
        "groovy_night",
        "Groovy (Night)",
        "Rust, olive and mustard in a dim 70s den.",
        stage="#1a120b",  # walnut panelling
        on_stage="#f2e2c8",
        accent="#ff7d4d",
        on_card="#fbecd6",
        weather="#7e2c16",
        clock="#36421f",
        affirmation="#7a5a1a",
        phrase="#4f2a19",
        moon="#1d2726",
    ),
)
THEMES.update({t.name: t for t in _NIGHTS})

DEFAULT_THEME = "blush"

# Themes people made in the menu, loaded from the registry at startup and kept
# in step as they're saved. The revision bumps on every change so live screens
# know to fetch the colours again.
_custom: dict[str, Theme] = {}
_custom_rev = 0

# Declarative theme files loaded from disk (.toml or .json).
_file_themes: dict[str, Theme] = {}


def set_custom_themes(themes: list[Theme]) -> None:
    global _custom_rev
    _custom.clear()
    _custom.update({t.name: t for t in themes})
    _custom_rev += 1


def set_file_themes(themes: list[Theme]) -> None:
    _file_themes.clear()
    _file_themes.update({t.name: t for t in themes})


def custom_rev() -> int:
    return _custom_rev


def all_themes() -> list[Theme]:
    return [*THEMES.values(), *_file_themes.values(), *_custom.values()]


def find_theme(name: str) -> Theme | None:
    return THEMES.get(name) or _file_themes.get(name) or _custom.get(name)


def get_theme(name: str) -> Theme:
    return find_theme(name) or THEMES[DEFAULT_THEME]


def parse_theme_dict(data: dict[str, Any], default_name: str = "") -> list[Theme]:
    """Parse a theme dictionary from a .toml or .json file.

    Supports single theme definitions, full slot definitions, or an optional
    [night] table which automatically registers the paired night twin.
    """
    name = (data.get("name") or default_name).strip()
    if not name:
        return []
    label = (data.get("label") or name.replace("_", " ").title()).strip()
    blurb = (data.get("blurb") or "A custom theme from file.").strip()
    stage = str(data.get("stage", "#000000")).lower()
    accent = str(data.get("accent", "#e7a34a")).lower()
    surface = str(data.get("surface", "solid"))
    font = data.get("font") or None

    cards_input = data.get("cards")
    if isinstance(cards_input, dict):
        card_map = {str(k): str(v).lower() for k, v in cards_input.items()}
    else:
        weather = str(data.get("weather", "#3a3732")).lower()
        clock = str(data.get("clock", "#282622")).lower()
        affirmation = str(data.get("affirmation", "#645e54")).lower()
        phrase = str(data.get("phrase") or affirmation).lower()
        card_map = {
            "weather": weather,
            "clock": clock,
            "affirmation": affirmation,
            "phrase": phrase,
            "forecast": clock,
            "nowPlaying": _shade(weather, 0.85),
            "countdown": clock,
        }
        if "moon" in data:
            card_map["moon"] = str(data["moon"]).lower()

    on_stage = str(data.get("on_stage") or ink_for(stage))
    on_card = str(data.get("on_card") or ink_for(*(card_map.values())))

    night_val = data.get("night")
    night_theme_name: str | None = None
    night_theme_obj: Theme | None = None

    if isinstance(night_val, dict):
        night_theme_name = f"{name}_night"
        n_stage = str(night_val.get("stage", "#121015")).lower()
        n_accent = str(night_val.get("accent", accent)).lower()
        n_cards_input = night_val.get("cards")
        if isinstance(n_cards_input, dict):
            n_card_map = {str(k): str(v).lower() for k, v in n_cards_input.items()}
        else:
            default_nw = _shade(card_map.get("weather", "#3a3732"), 0.5)
            nw = str(night_val.get("weather", default_nw)).lower()
            default_nc = _shade(card_map.get("clock", "#282622"), 0.5)
            nc = str(night_val.get("clock", default_nc)).lower()
            default_na = _shade(card_map.get("affirmation", "#645e54"), 0.5)
            na = str(night_val.get("affirmation", default_na)).lower()
            np = str(night_val.get("phrase") or na).lower()
            n_card_map = {
                "weather": nw,
                "clock": nc,
                "affirmation": na,
                "phrase": np,
                "forecast": nc,
                "nowPlaying": _shade(nw, 0.85),
                "countdown": nc,
            }
        night_theme_obj = Theme(
            name=night_theme_name,
            label=str(night_val.get("label") or f"{label} (Night)"),
            blurb=str(night_val.get("blurb") or f"{label}, deepened for after dark."),
            stage=n_stage,
            on_stage=str(night_val.get("on_stage") or ink_for(n_stage)),
            accent=n_accent,
            on_card=str(night_val.get("on_card") or ink_for(*(n_card_map.values()))),
            cards=n_card_map,
            surface=str(night_val.get("surface", surface)),
            custom=True,
            font=font,
        )
    elif isinstance(night_val, str) and night_val.strip():
        night_theme_name = night_val.strip()

    main_theme = Theme(
        name=name,
        label=label,
        blurb=blurb,
        stage=stage,
        on_stage=on_stage,
        accent=accent,
        on_card=on_card,
        cards=card_map,
        surface=surface,
        night=night_theme_name,
        custom=True,
        font=font,
    )

    if night_theme_obj is not None:
        return [main_theme, night_theme_obj]
    return [main_theme]


def load_file_themes(themes_dir: Path | str | None) -> list[Theme]:
    """Load declarative theme definitions (.toml or .json) from a directory."""
    if not themes_dir:
        return []
    p = Path(themes_dir)
    if not p.is_dir():
        return []
    loaded: list[Theme] = []
    for file in sorted(p.iterdir()):
        if not file.is_file():
            continue
        suffix = file.suffix.lower()
        if suffix == ".toml":
            try:
                with file.open("rb") as f:
                    data = tomllib.load(f)
                loaded.extend(parse_theme_dict(data, default_name=file.stem))
            except Exception as e:
                logger.warning("failed to load theme from %s: %s", file, e)
        elif suffix == ".json":
            try:
                with file.open(encoding="utf-8") as f:
                    data = json.load(f)
                loaded.extend(parse_theme_dict(data, default_name=file.stem))
            except Exception as e:
                logger.warning("failed to load theme from %s: %s", file, e)
    return loaded


class CustomColours(BaseModel):
    """What the menu's theme maker asks for: a background, an accent, the
    main card colours and, optionally, a typeface. Text colours are worked
    out from these. Most cards borrow the weather colour; the retired phrase
    card's defaults to the quote card's."""

    label: str = Field(min_length=1, max_length=40)
    stage: str = Field(pattern=_HEX)
    accent: str = Field(pattern=_HEX)
    weather: str = Field(pattern=_HEX)
    clock: str = Field(pattern=_HEX)
    affirmation: str = Field(pattern=_HEX)
    phrase: str | None = Field(default=None, pattern=_HEX)
    font: FontSetting | None = None
    """A typeface that comes with the theme, or ""/None for the usual."""


def _luminance(hex_color: str) -> float:
    """WCAG relative luminance, 0 (black) to 1 (white)."""
    h = hex_color.lstrip("#")

    def lin(c: int) -> float:
        v = c / 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (lin(int(h[i : i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


_LIGHT_INK = "#f7f2ea"
_DARK_INK = "#221d1a"


def ink_for(*backgrounds: str) -> str:
    """Light or dark text, whichever reads better on these backgrounds on
    average (contrast against the mean luminance)."""
    lum = sum(_luminance(b) for b in backgrounds) / len(backgrounds)
    on_light = (lum + 0.05) / (_luminance(_DARK_INK) + 0.05)
    on_dark = (_luminance(_LIGHT_INK) + 0.05) / (lum + 0.05)
    return _DARK_INK if on_light > on_dark else _LIGHT_INK


def custom_theme(name: str, colours: CustomColours) -> Theme:
    c = colours
    phrase = c.phrase or c.affirmation
    cards = (c.weather, c.clock, c.affirmation)
    return _theme(
        name,
        c.label.strip(),
        "Your own colours.",
        stage=c.stage.lower(),
        on_stage=ink_for(c.stage),
        accent=c.accent.lower(),
        on_card=ink_for(*cards),
        weather=c.weather.lower(),
        clock=c.clock.lower(),
        affirmation=c.affirmation.lower(),
        phrase=phrase.lower(),
    ).model_copy(update={"custom": True, "font": c.font or None})
