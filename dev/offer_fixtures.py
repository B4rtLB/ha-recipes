"""Invented sample pages in the shape of the four shops' offer pages (no real shop data).

Used by the golden tests (fixed day) and by e2e.py (today, served by the fixture server).
    from offer_fixtures import pages; pages("2026-11-11") -> {"jumbo.html": ..., "dirk.html": ..., ...}
"""

import html
import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def _enc(value, out, memo):
    """Nuxt/devalue style: every value gets a slot in one flat list, children are referenced by index."""
    if isinstance(value, (dict, list)) and id(value) in memo:
        return memo[id(value)]
    index = len(out)
    out.append(None)
    if isinstance(value, (dict, list)):
        memo[id(value)] = index
    if isinstance(value, dict):
        out[index] = {k: _enc(v, out, memo) for k, v in value.items()}
    elif isinstance(value, list):
        out[index] = [_enc(v, out, memo) for v in value]
    else:
        out[index] = value
    return index


def _nuxt(root) -> str:
    out: list = []
    _enc(root, out, {})
    return f'<html><head><title>Aanbiedingen</title></head><body><script type="application/json" id="__NUXT_DATA__">{json.dumps(out)}</script></body></html>'


def _d(today: str, plus: int) -> str:
    return (date.fromisoformat(today) + timedelta(days=plus)).isoformat()


def jumbo(today: str) -> str:
    def promo(pid, title, subtitle, tag, start, end):
        return {
            "active": True, "hidden": False, "id": pid, "title": title, "subtitle": subtitle, "group": "Week",
            "start": {"iso": f"{start}T00:01:00+01:00"}, "end": {"iso": f"{end}T23:59:59+01:00"},
            "durationTexts": {"title": "Geldig"}, "tags": [{"text": tag, "inverse": False}, {"text": "Online", "inverse": True}],
        }

    chicken = promo("j1", "Alle verse kipfilet", "Schaal 400 gram", "2 voor 7,99", today, _d(today, 6))
    groups = [
        {"id": "g0", "title": "Nu in de aanbieding", "promotions": [chicken]},
        {"id": "g1", "title": "Vlees, vis en vega", "promotions": [chicken, promo("j5", "Oude aanbieding", "", "voor 1,00", _d(today, -10), _d(today, -3))]},
        {"id": "g2", "title": "Aardappelen, groente en fruit", "promotions": [promo("j2", "Jumbo broccoli", "Per stuk", "voor 0,99", today, _d(today, 6))]},
        {"id": "g3", "title": "Zuivel, boter en eieren", "promotions": [promo("j3", "Biologische eieren", "Doos 10 stuks", "1+1 gratis", _d(today, -1), _d(today, 5))]},
        {"id": "g4", "title": "Drogisterij en gezondheid", "promotions": [promo("j4", "Shampoo Merk", "Fles 250 ml", "voor 2,49", today, _d(today, 6))]},
    ]
    hidden = promo("j6", "Verborgen", "", "voor 1,00", today, _d(today, 6))
    hidden["hidden"] = True
    return _nuxt({"groups": groups, "extra": [hidden]})


def dirk(today: str) -> str:
    def offer(oid, name, pack, price, was, dept, start, end):
        products = [{"productId": oid, "productInformation": {"department": dept}}] if dept else [None]
        return {"offerId": oid, "headerText": name, "packaging": pack, "offerPrice": price, "normalPrice": was,
                "startDate": f"{start}T00:00:00.000Z", "endDate": f"{end}T23:59:00.000Z", "products": products}

    return _nuxt({"offers": [
        offer(1, "1 de Beste Verse frites", "Zak 1 kilo.", 1.99, 2.39, "Aardappelen, groente & fruit", today, _d(today, 4)),
        offer(2, "Kipfilet", "Schaal 500 gram.", 4.49, 5.99, "Vlees", _d(today, -2), _d(today, 5)),
        offer(3, "Blauwe bessen", "Bak 300 gram.", 3.99, 0, None, today, _d(today, 4)),
        offer(4, "Wasmiddel", "Fles 1 liter", 3.99, 4.99, "Huishouden", today, _d(today, 6)),
        offer(5, "Kippendijfilet", "Schaal 600 gram.", 5.49, 6.99, "Vlees", today, _d(today, 4)),
    ]})


def lidl(today: str) -> str:
    zone = ZoneInfo("Europe/Amsterdam")

    def stamp(day: str, end: bool) -> int:
        return int(datetime.fromisoformat(day + ("T23:59:59" if end else "T00:00:00")).replace(tzinfo=zone).timestamp())

    def tile(title, price, pack, category, start, end, discount=None):
        p = {"price": price, "packaging": {"text": pack}}
        if discount:
            p["discount"] = {"deletedPrice": discount}
        t = {"fullTitle": title, "title": title, "price": p, "category": category, "storeEndDate": stamp(end, True)}
        if start:
            t["storeStartDate"] = stamp(start, False)
        return t

    tiles = [
        tile("Verse pasta spaghetti", 1.29, "500 g", "Food", today, _d(today, 5)),
        tile("Hollandse paprika's", 1.49, "500 g", "F+V", None, _d(today, 5), 1.99),
        tile("Sokken", 3.99, "3 paar", "NonFood", today, _d(today, 5)),
        tile("Oude kaas", 2.49, "200 g", "Food", _d(today, -9), _d(today, -2)),
    ]
    divs = "".join(f'<div class="gridbox" data-grid-data="{html.escape(json.dumps(t), quote=True)}"></div>' for t in tiles)
    return f"<html><head><title>Aanbiedingen</title></head><body>{divs}</body></html>"


def ah(today: str) -> tuple[str, str]:
    def product(wid, title, size, end, **extra):
        base = {"webshopId": wid, "title": title, "salesUnitSize": size, "isBonus": True, "promotionType": "NATIONAL",
                "bonusStartDate": _d(today, -1), "bonusEndDate": end, "mainCategory": "Vlees", "currentPrice": None,
                "priceBeforeBonus": None, "bonusMechanism": None, "discountLabels": []}
        base.update(extra)
        return base

    week = _d(today, 5)
    products = [
        product(1, "AH Scharrel kipfilet", "400 g", week, bonusMechanism="2 voor 5.00", priceBeforeBonus=3.19),
        product(2, "AH Franse scharrelkipfilet", "500 g", week, currentPrice=5.24, priceBeforeBonus=6.99,
                discountLabels=[{"defaultDescription": "25% korting"}]),
        product(3, "Hak Bruine bonen 4-pack", "4 stuks", "2999-12-31", promotionType="AHONLINE", bonusMechanism="10% volume voordeel"),
        product(4, "AH Basic eieren", "10 stuks", "", promotionType="PERPETUAL"),
        product(5, "AH Rundergehakt", "500 g", week, isBonus=False),
        product(6, "AH Shampoo", "300 ml", week, mainCategory="Persoonlijke verzorging", currentPrice=2.0, priceBeforeBonus=3.0),
        product(7, "AH Oude spaghetti", "500 g", _d(today, -3), mainCategory="Pasta, rijst", currentPrice=1.0, priceBeforeBonus=1.5),
    ]
    return json.dumps({"access_token": "invented-token", "expires_in": 1}), json.dumps({"products": products, "page": {"totalElements": len(products)}})


def pages(today: str) -> dict[str, str]:
    """File name -> content, laid out like the paths the refresh fetches in test mode."""
    token, search = ah(today)
    return {"jumbo.html": jumbo(today), "dirk.html": dirk(today), "lidl.html": lidl(today), "ah/token": token, "ah/search": search}


def write(directory, today: str) -> None:
    """Write the pages below a directory (created if needed)."""
    import pathlib  # noqa: PLC0415

    root = pathlib.Path(directory)
    for name, content in pages(today).items():
        target = root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
