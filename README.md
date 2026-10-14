# Nástroje k zadaniu „Mapa zámerov na dotykovej obrazovke"

Všetko tu je z verejného repozitára https://github.com/SamuelZenko/kto-stoji-za-projektom
(mapa beží na https://samuelzenko.github.io/kto-stoji-za-projektom/mapa-zamerov/), plus dve
pomôcky navyše. Dáta sú verejné (register EIA, geoportál Bratislavy, OSM). Nič z toho nemusíte
použiť — je to ukážka, ako sme k tým istým problémom pristúpili my, a dáta, aby ste nemuseli nič sťahovať.

Python: skripty bežali na Python 3.13 (ArcGIS Pro env). Potrebujú: shapely, pymupdf (len parcely_test / polohy_doplnenie pri čítaní PDF).
Spúšťať z priečinka `dokumenty/`. Cesty v skriptoch sú relatívne k repu (`../mapa-zamerov/...`),
okrem `polohy_doplnenie.py`, ktorý má v premennej `DET` cestu k cache detailov EIA — nastavte ju na `../eia_detaily`.

## data/  — vstupné dáta pre zadanie
| súbor | čo je to |
|---|---|
| zamery.geojson | 988 zámerov z registra EIA s polohou, presnosťou, fázou, navrhovateľom, odkazom na spis — HLAVNÝ vstup zadania |
| mestske-casti.geojson | 17 mestských častí (polygóny), pole NAZOV_ZUJ (pozor: „Podunajské Biskupic" je v shapefile skrátené) |
| ulice.geojson | pomenované ulice Bratislavy z OSM (geometria) — na spresňovanie polohy podľa názvu ulice |
| osm_ulice_ba.json | to isté ako slovník {názov: [úseky]} , 1 859 názvov, stiahnuté z geoportálu BA (osm/Cesty_a_doprava_OSM) |
| osm-staveniska.geojson | pomenované staveniská z OSM (landuse=construction) — na párovanie podľa obchodného názvu |
| eia_detaily/ | cache detailov spisov z EIA API (`/api/eia_projects/<id>`), 2 314 JSON — zoznam dokumentov, navrhovateľ, obec |
| parcely_vsetky_vysledok.json | výsledok hľadania parciel z textu zámerov v katastri (689 zámerov) — vstup pre polohy_doplnenie.py |

## dokumenty/  — skripty (poradie, v akom dávajú zmysel)
| skript | čo robí | k čomu v zadaní |
|---|---|---|
| parcely_test.py | z PDF zámeru vytiahne parcelné čísla a k. ú., nájde ich v katastri (geoportál REST), spočíta ťažisko; bod musí ležať v Bratislave | spresnenie polohy – cesta cez parcely |
| polohy_doplnenie.py | 4 fázy pre zámery bez polohy: parcely v inom k. ú. / registri E, všetky PDF spisu, a hľadanie NÁZVOV ULÍC v texte s toleranciou na skloňovanie + križovatka dvoch ulíc; vyradí adresu úradu, zníži váhu adresy navrhovateľa; ulica dlhšia než 1,5 km = len nápoveda | spresnenie polohy – cesta cez ulice (najbližšie k úlohe A5) |
| yimba_polohy.py | zoberie súradnice projektov z yimba.sk a spáruje ich so zámermi cez odkaz na EIA v stránke (presné párovanie, nie podľa mena) | spresnenie polohy – cesta cez web |
| osm_staveniska.py | staveniská z OSM: do 30 m od bodu → obchodný názov, rovnaký názov v tej istej MČ → poloha | spresnenie polohy – cesta cez OSM |
| oprav_polohy.py | geokódovanie ulice v rámci mestskej časti (adresné body pokrývajú celé Slovensko, treba orezať) | pasca, na ktorú narazíte |
| polohy_rucne.py + polohy_rucne.json | ručne overené polohy majú najvyššiu dôveru, prepisujú automat; každý zápis nesie zdroj | ako označiť zdroj a neistotu |
| polohy_zapis2.py | zapíše len návrhy so stavom OK do geojsonu, chránené (ručné) nikdy neprepíše | oddelenie „návrh" od „zápis" |
| PLAN_POLOHY.md | plán, čo s 465 približnými polohami, po dôvodoch zlyhania, a 4 pravidlá, ktoré sa osvedčili | kontext |
| README.md | pôvodný README priečinka dokumenty (celá pipeline mapy) | kontext |

## mapa/  — hotová mapa (front-end bez build kroku)
| súbor | čo je to |
|---|---|
| index.html, app.js, ui.css | mapa zámerov v MapLibre: filtre, karta zámeru, presná/približná poloha, návrh polohy z mapy cez GitHub issue; ~3 000 riadkov vanilla JS, bez frameworku |
Beží priamo zo súborov cez `python -m http.server`. Nie je to vzor, ktorý máte kopírovať — je to to, čo porovnávame.

## panely/  — projekcia a video wall (k otázke 1 na rozhovore)
| súbor | čo je to |
|---|---|
| NAVOD_PANELY.md | ako sa dva panely Samsung VM55B-U spájajú do jedného obrazu 3 840 × 1 080 cez DisplayPort daisy chain, Video Wall nastavenia, custom rozlíšenie, záloha s dvoma oknami |

## zadanie/
| súbor | čo je to |
|---|---|
| Zadanie_2_kolo_navrh.html | text zadania s bodovaním a otázkami na rozhovor |

Pravidlá, ktoré platia v celom repe a chceme ich vidieť aj u vás:
1. každá poloha nesie zdroj (`zdroj_polohy`, `poloha_zdroj`) — bez zdroja sa nezapisuje,
2. ručná oprava má prednosť pred automatom a automat ju nikdy neprepíše,
3. mestskej časti zo zápisu EIA sa nedá veriť (býva to sídlo navrhovateľa), adresa navrhovateľa nie je miesto stavby,
4. návrh ≠ zápis: skript navrhne do JSON, do mapy ide až po kontrole.
