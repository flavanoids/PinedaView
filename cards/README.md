# cards/

Each subfolder is one card. A card declares what it needs; the server wires it up
or greys it in the picker with the reason.

```
cards/<id>/
  card.json       manifest — needs, provides, slots, settings, tier, permissions
  provider.py     optional — Provider.poll(ctx), only if the card fetches its own data
  <Name>.svelte   the view — receives a ctx
  ...             card-owned assets travel with the card
```

Custom cards dropped into this directory are loaded additively alongside
the built-in cards shipped in `core/src/pinedaview/cards/builtin/` (and can
override a built-in by ID).

To scaffold a new card:
```bash
scripts/new-card.sh <id> "<Name>"
```

Full details:
- Card authoring guide: [`../docs/CARD_SDK.md`](../docs/CARD_SDK.md)
- `card.json` schema reference: [`../docs/CARD_MANIFEST.md`](../docs/CARD_MANIFEST.md)
