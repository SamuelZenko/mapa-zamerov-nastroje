# Pripojenie panelov Samsung VM55B-U k maketе

Prehrávač: `http://127.0.0.1:8765/prehravac.html` (lokálny server v priečinku `app`, spustenie ak nebeží:
`& "C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe" -m http.server 8765 --bind 127.0.0.1 --directory "C:\Users\samuel.zenko\Documents\SvetelnaBA\mobilny_model\app"`)

- `?displej=0` = ľavý panel, `?displej=1` = pravý panel, bez parametra = celý obraz 3840 × 1080
- dvojklik v okne = celá obrazovka, ovládač: `ovladac.html` (rovnaký prehliadač alebo iPad)
- Chrome zoom 100 % (Ctrl+0) – inak nie je pixel na pixel

## A) Jeden panel (vývoj) – HDMI

1. HDMI notebook → panel `HDMI IN 1`; na ovládači panelu `Source` → HDMI 1.
2. Windows: Win+P → **Rozšíriť**. Nastavenia → Obrazovka: panel 1920 × 1080, 60 Hz, mierka **100 %**.
3. Chrome: `http://127.0.0.1:8765/prehravac.html?displej=0`, okno presunúť na panel (Win+Shift+šípka), dvojklik.
4. Menu panelu: Picture Mode *Calibrated* (žiadny Dynamic/Shop), Dynamic Contrast Off, Picture Size **16:9** (nie Zoom), ideálne Color Tone *Standard*, Gamma 2.2. Jedna zmena naraz a pozerať, čo robí s tenkými čiarami.

## B) Dva panely – cieľový stav: video wall cez DisplayPort

Notebook (Legion 83F5, RTX 5080 + USB4) → **USB-C/Thunderbolt → DisplayPort** kábel → panel 1 `DP IN`; panel 1 `DP OUT` → panel 2 `DP IN` (krátky DP–DP kábel, býva v balení).

1. Na oboch paneloch: Menu → *Picture / Video Wall*:
   - Video Wall **On**, Horizontal **2**, Vertical **1**
   - Screen Position: panel 1 = **1**, panel 2 = **2** (ľavý = 1 pri pohľade od dlhej strany stola, kde stojí divák)
   - Format *Full* (nie Natural – Natural by uberal pixely za spoj)
2. Panel 1: DP loop out zapnutý (býva default pri DP vstupe), oba na Source **DisplayPort**.
3. Windows: v NVIDIA Control Panel → *Change resolution* → **Customize → Create Custom Resolution: 3840 × 1080, 60 Hz** (progressive, timing Automatic). Ak NVIDIA výstup na USB-C nevidí, to isté v Intel Graphics Command Center → Display → Custom Resolutions. Potom Nastavenia → Obrazovka: panel ako jeden monitor 3840 × 1080, Rozšíriť, mierka 100 %.
4. Chrome: `http://127.0.0.1:8765/prehravac.html` (bez parametra), okno na panel, dvojklik. Obraz sa sám rozdelí: ľavá polovica panel 1, pravá panel 2.
5. Kontrola spoja: v štúdiu (`index.html`) zapnúť Ostré a pozrieť, či línie cez spoj nadväzujú. Ak sú posunuté, zmerať skutočnú šírku spoja (rám + rám, mm) a upraviť `HW.gap` v `core.js` / `display-transform.json` (predpoklad 3,5 mm).

Ak Windows 3840 × 1080 odmietne (ovládač/IT politika), panel dostane 1920 × 1080 a rozdelí to na 2 × 960 → rozmazané. Vtedy → C.

## C) Dva panely – záloha: dve okná

Dva výstupy z notebooku (HDMI + USB-C → HDMI/DP). Windows Rozšíriť, oba 1920 × 1080, v náhľade obrazoviek vedľa seba v správnom poradí. Video Wall na paneloch **Off**. Dve okná Chrome: `?displej=0` na ľavom, `?displej=1` na pravom, každé fullscreen. Stav (scéna, výber, čas) zdieľajú automaticky – ovládač riadi obe.

## D) Výstava bez notebooku – SBB box

SBB sa zasunie do slotu na zadnej strane panelu 1, druhý panel cez DP daisy-chain ako v B. Windows SBB: beží ten istý prehrávač (server + Chrome kiosk). Tizen SBB: URL launcher na prehrávač, alebo MP4 slučka 3840 × 1080 (riadok 6.3 v Dátach). Model SBB určí, ktorá cesta.

## Tipy

- Kábel DP, nie HDMI: cez HDMI panel signál ďalej neposiela.
- Po každom prepnutí Source/rozlíšenia Chrome okno znova dvojklik (fullscreen sa stratí).
- Panel „nahor": IR prijímač je na spodnej hrane – ovládač mieriť zboku, alebo pripojiť externý IR senzor do `IR IN`.
- Šetrič obrazovky Windows a uspávanie vypnúť (príkaz `awake`).
