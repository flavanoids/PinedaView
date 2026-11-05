# SPDX-License-Identifier: Apache-2.0
"""The recipe box: kept by Antigua, listed and changed from the phone menu."""

from __future__ import annotations

import json
from typing import Any

import httpx

from pinedaview.runtime import Runtime

_PIE = {
    "id": "0123456789",
    "title": "Classic Apple Pie",
    "source": "Allrecipes",
    "url": "https://www.allrecipes.com/recipe/12345/apple-pie/",
    "dish": "apple pie",
    "servings": "serves 8",
    "total_min": 90,
    "rating": 4.8,
    "rating_count": 1200,
    "image": "https://www.allrecipes.com/pie.jpg",
    "ingredients": ["6 apples", "1 pie crust"],
    "steps": ["Fill the crust.", "Bake for 50 minutes."],
    "favorite": True,
}


def _antigua(runtime: Runtime, seen: list[tuple[str, str]]) -> None:
    def handle(req: httpx.Request) -> httpx.Response:
        seen.append((req.method, req.url.path))
        if req.method == "GET":
            return httpx.Response(
                200,
                json={
                    "favorites": [{**_PIE, "added": 1.7e9}],
                    "history": [{**_PIE, "at": 1.8e9, "by": "Sam", "cooked": True}],
                },
            )
        if req.url.path.startswith("/recipes/9999999999"):
            return httpx.Response(404, json={"error": "no such recipe"})
        if req.url.path.endswith("/show"):
            return httpx.Response(200, json={"opened": "0123456789", "shown": True})
        body: dict[str, Any] = json.loads(req.content) if req.content else {}
        assert body == {}
        return httpx.Response(200, json={"id": "0123456789", "favorite": req.method == "POST"})

    runtime.settings.antigua.url = "http://antigua.test"
    runtime.http = httpx.AsyncClient(transport=httpx.MockTransport(handle))


async def test_the_menu_reaches_antigua_s_recipe_box(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    seen: list[tuple[str, str]] = []
    _antigua(runtime, seen)

    box = (await client.get("/api/recipes")).json()
    assert box["favorites"][0]["url"] == _PIE["url"] and box["favorites"][0]["added"] == 1.7e9
    visit = box["history"][0]
    assert visit["cooked"] is True and visit["by"] == "Sam" and visit["steps"][1].startswith("Bake")

    off = await client.delete("/api/recipes/0123456789/favorite")
    assert off.json() == {"id": "0123456789", "favorite": False}
    on = await client.post("/api/recipes/0123456789/favorite")
    assert on.json() == {"id": "0123456789", "favorite": True}
    shown = await client.post("/api/recipes/0123456789/show")
    assert shown.json() == {"opened": "0123456789", "shown": True}
    assert seen == [
        ("GET", "/recipes"),
        ("DELETE", "/recipes/0123456789/favorite"),
        ("POST", "/recipes/0123456789/favorite"),
        ("POST", "/recipes/0123456789/show"),
    ]

    gone = await client.post("/api/recipes/9999999999/show")
    assert gone.status_code == 404
    # Only a recipe id goes through to Antigua.
    assert (await client.post("/api/recipes/..%2Fhealth/show")).status_code in (404, 405)
    assert (await client.post("/api/recipes/ABC/favorite")).status_code == 404
    assert len(seen) == 5


async def test_without_antigua_the_box_is_unavailable(
    runtime: Runtime, client: httpx.AsyncClient
) -> None:
    runtime.settings.antigua.url = None
    res = await client.get("/api/recipes")
    assert res.status_code == 503
