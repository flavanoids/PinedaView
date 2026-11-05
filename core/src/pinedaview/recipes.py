# SPDX-License-Identifier: Apache-2.0
"""The recipe box for the phone menu's Recipes tab, kept by the voice assistant.

Antigua owns it: every recipe opened by voice goes into its history, and
"favorite this recipe" keeps one for good, whole (ingredients, steps, the
page it came from). The menu lists both through ``[antigua] url`` (``GET
/recipes``), sets or clears the heart (``POST/DELETE
/recipes/<id>/favorite``) and puts one on the display (``POST
/recipes/<id>/show``: Antigua opens it, ready for "Alexa, I'm ready").
"""

from __future__ import annotations

from pydantic import BaseModel


class Recipe(BaseModel):
    id: str
    title: str
    source: str = ""
    """The site: 'Allrecipes'."""
    url: str = ""
    """The recipe's own page, for the whole story and its photos."""
    dish: str = ""
    """What it was asked for as: 'apple pie'."""
    servings: str = ""
    total_min: int = 0
    rating: float = 0
    rating_count: int = 0
    image: str = ""
    """Its first photo on its page, or empty."""
    ingredients: list[str] = []
    steps: list[str] = []
    favorite: bool = False


class FavoriteRecipe(Recipe):
    added: float
    """Unix seconds."""


class RecipeVisit(Recipe):
    at: float
    """Unix seconds it was last opened."""
    by: str = ""
    """Who opened it, when the voice was known; 'menu' from here."""
    cooked: bool = False
    """Read through to the last step."""


class RecipeBox(BaseModel):
    favorites: list[FavoriteRecipe]
    """Newest first."""
    history: list[RecipeVisit]
    """Newest first, up to 100."""


class RecipeFavorite(BaseModel):
    id: str
    favorite: bool


class RecipeShown(BaseModel):
    opened: str
    shown: bool
    """False when Antigua has no display to put it on."""
