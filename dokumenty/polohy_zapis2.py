# -*- coding: utf-8 -*-
"""Zapise navrhy z polohy_doplnenie.py do mapy zamerov.

Zapisuje len zaznamy so stavom OK. Stavy „neisté" a „nenasla" sa preskocia —
tie patria na rucnu kontrolu do polohy_rucne.json.

Rucne overena poloha (zdroj_polohy „ručne") sa NEPREPISUJE, ta ma najvyssiu
doveru. Rovnako sa neprepisuje poloha od redakcie.

Mapa pouziva presnost len dvojstavovo (presná / približná) a appka na vsetko
ostatne pise „poloha nie je známa", preto aj poloha z ulice dostava „presná"
a konkretnost sa odlisi v zdroj_polohy a v poloha_zdroj, ktore su vidiet v karte.

Beh: "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" polohy_zapis2.py [nanecisto]
"""
import collections
import io
import json
import os
import re
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TU = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(os.path.dirname(TU), "mapa-zamerov")
GJ = os.path.join(MAPA, "zamery.geojson")
NANECISTO = len(sys.argv) > 1 and sys.argv[1].startswith("nanecisto")

navrhy = {z["id"]: z for z in json.load(io.open(
    os.path.join(TU, "polohy_doplnenie_vysledok.json"), encoding="utf-8")) if z["stav"] == "OK"}
gj = json.load(io.open(GJ, encoding="utf-8"))

ZDROJ = {"1": "parcela", "2": "parcela", "3": "parcela", "4": "ulica v MČ"}
n, chranene, mimo = 0, 0, list(navrhy)
posuny = []
for f in gj["features"]:
    p = f["properties"]
    z = navrhy.get(p["id"])
    if not z:
        continue
    mimo.remove(p["id"])
    if p.get("zdroj_polohy") in ("ručne", "redakcia"):
        chranene += 1
        print("  chranene (%s), nechavam: %s" % (p["zdroj_polohy"], p["nazov"][:58]))
        continue
    stare = f["geometry"]["coordinates"]
    f["geometry"]["coordinates"] = [round(z["bod"][0], 6), round(z["bod"][1], 6)]
    p["presnost"] = "presná"
    p["zdroj_polohy"] = ZDROJ[z["faza"]]
    p["poloha_zdroj"] = z["zdroj"]
    if z.get("pozn"):
        p["poloha_poznamka"] = z["pozn"]
    if z["faza"] == "4":
        ul = re.findall("„(.+?)“", z["zdroj"])
        if ul:
            p["ulica"] = " / ".join(ul)
    elif z.get("parcely"):
        p["parcely"] = z["parcely"]
        if z.get("ku"):
            p["ku"] = z["ku"]
    dx = (z["bod"][0] - stare[0]) * 111320 * 0.667
    dy = (z["bod"][1] - stare[1]) * 110540
    posuny.append(((dx * dx + dy * dy) ** 0.5, z["faza"], p["nazov"]))
    n += 1

posuny.sort(reverse=True)
print("\nnajvacsie posuny (ako daleko bol bod predtym):")
for d, faza, nz in posuny[:12]:
    print("  faza %s  %6.0f m  %s" % (faza, d, nz[:60]))

if mimo:
    print("\nPOZOR, tieto id v mape nie su (%d): %s" % (len(mimo), ", ".join(mimo[:5])))

if NANECISTO:
    print("\n--- nanecisto, mapa sa nemenila ---")
else:
    json.dump(gj, io.open(GJ, "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))

presne = sum(1 for f in gj["features"] if f["properties"].get("presnost") == "presná")
print("\nzapisanych: %d   chranenych rucnych: %d" % (n, chranene))
print("zdroje poloh: %s" % dict(collections.Counter(
    f["properties"].get("zdroj_polohy") for f in gj["features"])))
print("presnych: %d z %d (priblizne: %d)" % (presne, len(gj["features"]), len(gj["features"]) - presne))
