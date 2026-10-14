# -*- coding: utf-8 -*-
"""Doplnenie poloh zamerom, ktorym automat z parciel polohu nenasiel (PLAN_POLOHY.md).

Vstup:  parcely_vsetky_vysledok.json (689 testovanych zamerov, 340 bez polohy)
Vystup: polohy_doplnenie_vysledok.json — navrhy, mapa sa NEMENI.
        Zapis do mapy robi az polohy_zapis2.py po kontrole.

FAZA 1  „bod mimo udanej MC" (14)
        Parcely su najdene spravne, len bod nesedel s mestskou castou z EIA.
        Mestskej casti z EIA sa neveri (byva to sidlo navrhovatela — Klingerka).
        Staci, ze bod lezi v Bratislave. Presnost „presna".

FAZA 2  „parcela sa v katastri nenasla" (35)
        Hlada vo VSETKYCH bratislavskych k. u. a v registri C aj E, nie len v
        tom, co uvadza text. Rovna sa problem „Ruzinov" namiesto „Nivy".

FAZA 3  „sken bez textu" (83)
        Povodny beh cital len 3 najvacsie PDF. Tu sa skusia vsetky textove PDF
        v spise — sken zamru casto obchadza rozhodnutie alebo zaverecne
        stanovisko, ktore su textove. OCR netreba.

FAZA 4  „parcela v texte nie je" (208)
        V texte sa hladaju NAZVY ULIC z OSM (23 tisic pomenovanych useku z
        geoportalu, s toleranciou na sklonovanie: „na Kosickej" najde
        „Kosicka"). Vyberie sa ulica, ktora je v udanej mestskej casti a v
        texte je najcastejsie. Bod = tazisko useku v MC. Presnost „ulica v MC".
        Ak v texte nic, skusi sa nazov samotneho zameru.

Beh: "C:/Program Files/ArcGIS/Pro/bin/Python/envs/arcgispro-py3/python.exe" polohy_doplnenie.py [1|2|3|4]
Beh sa da kedykolvek prerusit, hotove zamery sa pri dalsom spusteni preskocia.
"""
import collections
import io
import json
import os
import re
import ssl
import sys
import time
import urllib.parse as up
import urllib.request as ur
import zipfile

import pymupdf
from shapely.geometry import shape, Polygon, LineString
from shapely.ops import unary_union

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
TU = os.path.dirname(os.path.abspath(__file__))
MAPA = os.path.join(os.path.dirname(TU), "mapa-zamerov")
SCR = (r"C:\Users\SAMUEL~1.ZEN\AppData\Local\Temp\claude"
       r"\C--Users-samuel-zenko\f9e78086-b3b2-4b0e-a0ba-588d4220313d\scratchpad")
DET = os.path.join(SCR, "eia_detaily")
ULICE_CACHE = os.path.join(SCR, "osm_ulice_ba.json")
KAND = os.path.join(SCR, "ulice_kandidati")
if not os.path.isdir(KAND):
    os.makedirs(KAND)
VYSTUP = os.path.join(TU, "polohy_doplnenie_vysledok.json")

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36 MIB-mapa/1.0")
KN = ("https://geoportal.bratislava.sk/hSite/rest/services/kataster/"
      "Kataster_nehnute%C4%BEnost%C3%AD_C_a_E/MapServer/{}/query")
CESTY = ("https://geoportal.bratislava.sk/hSite/rest/services/osm/"
         "Cesty_a_doprava_OSM/MapServer/%d/query")
MAXMB, MAX_STRAN, MAX_PARCIEL = 25, 80, 8

HLAVNY = re.compile(r"z[áa]mer|ozn[áa]menie o zmene|spr[áa]va o hodnoten|textov[áa]|sprievodn|"
                    r"rozhodnut|z[áa]vere[čc]n[éeá] stanovisk|posudok", re.I)
GRAF = re.compile(r"situ[aá]c|v[yý]kres|[sš]ir[sš]ie vz[tť]ah|koordina|mapa|z[aá]kres|vizualiz|"
                  r"p[oô]dorys|podorys|rez\b|rezy|pohľad|pohlad|ortofoto|fotodok|grafick", re.I)
PARC = re.compile(
    r"parc\w*\.?\s*(?:reg\w*\.?\s*[„\"'“]?\s*[CE]\s*[„\"'”]?\s*(?:KN)?\s*)?"
    r"(?:[čc]\.|[čc][ií]sl\w*)?\s*:?\s*"
    r"((?:\d{1,5}\s*/\s*\d{1,4}|\d{2,5})(?:\s*[,;]\s*(?:a\s+)?(?:\d{1,5}\s*/\s*\d{1,4}|\d{2,5}))*)",
    re.I)
KU = re.compile(r"(?:(?<![a-záäčďéíĺľňóôšťúýž])k\.\s?[úu]\.|katastr[áa]ln\w{1,4}\s+[úu]zem\w+)\s*:?\s*"
                r"([A-ZÁÄČĎÉÍĹĽŇÓÔŠŤÚÝŽ][a-záäčďéíĺľňóôšťúýž]+(?:\s+[A-ZÁÄČĎÉÍĹĽŇÓÔŠŤÚÝŽ][a-záäčďéíĺľňóôšťúýž]+)?)")
KU_ZNAME = ["Staré Mesto", "Nivy", "Ružinov", "Trnávka", "Nové Mesto", "Vinohrady", "Rača", "Vajnory",
            "Karlova Ves", "Dúbravka", "Lamač", "Devín", "Devínska Nová Ves", "Záhorská Bystrica",
            "Petržalka", "Jarovce", "Rusovce", "Čunovo", "Podunajské Biskupice", "Vrakuňa"]
# vety, ktore v texte uvadzaju miesto — zmienka ulice v ich okoli vazi viac
MIESTO = re.compile(r"miest\w+\s+(?:realiz|stavby|uskuto|[úu]zemi)|umiestnen|lokalit|adres", re.I)
# slovo „ulica" a spol. v okoli zmienky: to je dokaz, ze ide naozaj o ulicu
CUE = re.compile(r"ul\.|ulic|n[áa]mest|n[áa]brez|cest[aey]|triede|triedy", re.I)
# jednoslovne nazvy, ktore su v slovencine bezne pridavne mena — „na dopravnej ceste",
# „priemyselna zona", „druha etapa". Tie sa pocitaju LEN ked je v okoli slovo ulica.
SLABE = set("""doprav druh priemyseln technick hlavn dunajsk mestsk spolocensk kulturn parceln
rozvodn geologick hranicn such nov star dlh kratk poln luzn hradn zahradn slnecn skolsk sportov
vysok nizk siroka uzk prv tret stvrt piat hlbok cist tich ostr biel cern zelen modr cervena
severn juzn vychodn zapadn stredn vnutorn vonkajs obchodn vyrobn skladov zdravotn socialn
vodn plynov tepeln elektricka elektrick zeleznicn pristavn""".split())
# slova, ktore sa v OSM volaju ako ulica, ale v texte znamenaju takmer vzdy nieco ine
ZAKAZ = set(["bratislava", "most", "park", "namestie", "centrum", "pristav", "letisko",
             "nabrezie", "juh", "sever", "zapad", "vychod", "cesta", "ulica"])


_DIA = "áäčďéěíĺľňóôöŕřšťúůüýžÁÄČĎÉÍĹĽŇÓÔÖŔŘŠŤÚÜÝŽ"
_BEZ = "aacdeeillnooorrstuuuyzAACDEILLNOOORRSTUUYZ"


def bdc(s):
    """Odstrani diakritiku, VELKE PISMENA zachova — rozlisenie „Dopravna" (ulica)
    od „dopravna" (pridavne meno) je pri hladani ulic v texte to najdolezitejsie."""
    return "".join(_BEZ[_DIA.index(c)] if c in _DIA else c for c in (s or ""))


def bd(s):
    return bdc(s).lower()


def log(s):
    print(s)
    sys.stdout.flush()


def web(u, timeout=90, ref=None):
    h = {"User-Agent": UA}
    if ref:
        h["Referer"] = ref
    return ur.urlopen(ur.Request(u, headers=h), timeout=timeout, context=CTX).read()


def stiahni(u):
    data = web(u, 180, "https://www.enviroportal.sk/")
    if data[:4] == b"PK\x03\x04":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            v = [x for x in z.namelist() if x.lower().endswith(".pdf")]
            if not v:
                return None
            data = z.read(v[0])
    return data if data[:5] == b"%PDF-" else None


def text_pdf(data):
    d = pymupdf.open(stream=data, filetype="pdf")
    t = "".join(d.load_page(i).get_text() for i in range(min(MAX_STRAN, d.page_count)))
    d.close()
    return t


def parcely_z_textu(t):
    von = []
    for m in PARC.finditer(t):
        for c in re.findall(r"\d{1,5}\s*/\s*\d{1,4}|\d{2,5}", m.group(1)):
            c = re.sub(r"\s+", "", c)
            if c not in von and not (c.isdigit() and int(c) < 10):
                von.append(c)
        if len(von) >= MAX_PARCIEL:
            break
    return von[:MAX_PARCIEL]


def ku_z_textu(t):
    for m in KU.finditer(t):
        k = bd(m.group(1))
        for z in sorted(KU_ZNAME, key=len, reverse=True):
            if k.startswith(bd(z)) or (len(k) >= 8 and bd(z).startswith(k)):
                return z
    return None


# ---------- mestske casti ----------
_mc = json.load(io.open(os.path.join(MAPA, "mestske-casti.geojson"), encoding="utf-8"))
MC = {}
for f in _mc["features"]:
    a = f.get("properties") or {}
    MC[a.get("NAZOV_ZUJ") or ""] = shape(f["geometry"]).buffer(0)
BA = unary_union(list(MC.values())).buffer(0)


def mc_poly(obec):
    """NAZOV_ZUJ je v shapefile skrateny na 30 znakov („Podunajske Biskupic"), preto aj prefix.
    Najprv presne, potom NAJDLHSI prefix — inak „Devinska Nova Ves" sadne na „Devin"."""
    if not obec:
        return None, None
    o = bd(obec)
    naj = None
    for k, g in MC.items():
        kb = bd(k)
        if kb == o:
            return k, g
        if o.startswith(kb) or kb.startswith(o):
            if naj is None or len(kb) > len(bd(naj[0])):
                naj = (k, g)
    return naj if naj else (None, None)


def kde_je(bod):
    for k, g in MC.items():
        if g.contains(bod):
            return k
    return "?"


# ---------- kataster ----------
_kn = {}


def parcela_kn(cpa, register=0):
    kl = (cpa, register)
    if kl in _kn:
        return _kn[kl]
    pole = "register_c_202411.CPA" if register == 0 else "register_E_202412.CPA"
    try:
        r = json.loads(web(KN.format(register) + "?" + up.urlencode({
            "where": "%s = '%s'" % (pole, cpa), "outFields": "*", "returnGeometry": "true",
            "outSR": "4326", "f": "json"})).decode("utf-8"))
    except Exception:
        r = {}
    von = []
    for f in r.get("features", []):
        a = {k.split(".")[-1]: v for k, v in f["attributes"].items()}
        try:
            g = Polygon(f["geometry"]["rings"][0])
        except Exception:
            continue
        von.append((a.get("KU"), g))
    _kn[kl] = von
    time.sleep(0.2)
    return von


KU_BA = set(bd(x) for x in KU_ZNAME)


def bod_z_parciel(parc, ku, obec=None):
    """Tazisko parciel.

    1. kolo hlada len v k. u. udanom v texte. Tam mestskej casti z EIA neveri —
       byva to sidlo navrhovatela (Klingerka).
    2. kolo (ked parcela v udanom k. u. nie je) hlada vo vsetkych bratislavskych
       k. u. Tu uz ale nie je nic, co by vyber potvrdilo, a cisla parciel sa
       medzi k. u. opakuju — Westend v Lamaci by skoncil v Podunajskych
       Biskupiciach. Preto musi bod padnut do mestskej casti z EIA, inak sa
       vracia ako neisty na rucnu kontrolu.

    Vracia (bod, k_u, pozn) alebo (None, None, dovod); pri neistom (None, bod, dovod)."""
    neisty = None
    for kolo in (0, 1):
        tvary, kus = [], collections.Counter()
        for c in parc:
            # v 2. kole chyba potvrdenie k. u., takze cisla ako „19" alebo „20" su
            # na slepe hladanie prilis caste — beru len parcely s lomkou alebo >= 100
            if kolo == 1 and "/" not in c and (not c.isdigit() or int(c) < 100):
                continue
            for reg in (0, 1):
                for k, g in parcela_kn(c, reg):
                    kb = bd(k or "")
                    if kolo == 0 and ku and kb != bd(ku):
                        continue
                    if kb not in KU_BA:
                        continue
                    tvary.append(g)
                    kus[k] += 1
        if not tvary:
            if kolo == 0 and ku:
                continue
            break
        c = unary_union([g.buffer(0) for g in tvary]).centroid
        if not BA.buffer(0.002).contains(c):
            return None, None, "tazisko parciel lezi mimo Bratislavy"
        bod = [round(c.x, 6), round(c.y, 6)]
        ku_naj = kus.most_common(1)[0][0] if kus else None
        if kolo == 0:
            return bod, ku_naj, "bod v %s" % kde_je(c)
        mcn, mcg = mc_poly(obec)
        if mcg is not None and not mcg.contains(c):
            neisty = (bod, ku_naj,
                      "NEISTE: parcela %s najdena v k. u. %s, ale bod lezi v %s a EIA uvadza %s"
                      % (", ".join(parc[:4]), ku_naj or "?", kde_je(c), obec))
            break
        return bod, ku_naj, "bod v %s, parcela najdena v k. u. %s (v texte bolo %s)" % (
            kde_je(c), ku_naj or "?", ku or "nic")
    if neisty:
        return None, neisty, neisty[2]
    return None, None, "parcela sa nenasla ani v ostatnych k. u. a registri E"


# ---------- OSM ulice ----------
def stem(w):
    w = re.sub(r"[^a-z]", "", bd(w))
    return w[:-2] if len(w) >= 7 else (w[:-1] if len(w) >= 5 else w)


def nacitaj_ulice():
    """Vsetky pomenovane cestne useky Bratislavy z geoportalu, raz a do cache."""
    if os.path.exists(ULICE_CACHE):
        d = json.load(io.open(ULICE_CACHE, encoding="utf-8"))
        log("   ulice z cache: %d nazvov" % len(d))
        return d
    log("   stahujem nazvy ulic z geoportalu (raz, do cache)...")
    naz = collections.defaultdict(list)
    for lay in (7, 8, 9):
        off = 0
        while True:
            try:
                r = json.loads(web(CESTY % lay + "?" + up.urlencode({
                    "where": "NAME IS NOT NULL", "outFields": "NAME", "returnGeometry": "true",
                    "outSR": "4326", "f": "json", "resultOffset": off,
                    "resultRecordCount": 2000}), 180).decode("utf-8"))
            except Exception as e:
                log("      L%d off=%d chyba %s" % (lay, off, str(e)[:60]))
                break
            fs = r.get("features") or []
            for f in fs:
                n = (f["attributes"].get("NAME") or "").strip()
                if not n:
                    continue
                for p in f.get("geometry", {}).get("paths") or []:
                    if len(p) > 1:
                        naz[n].append([[round(x, 6), round(y, 6)] for x, y in p])
            off += len(fs)
            if len(fs) < 2000 or not r.get("exceededTransferLimit"):
                break
        log("      L%d hotovo, nazvov doteraz %d" % (lay, len(naz)))
    json.dump(naz, io.open(ULICE_CACHE, "w", encoding="utf-8"), ensure_ascii=False)
    log("   ulic: %d nazvov" % len(naz))
    return naz


ULICE = None
UL_RE = {}


def priprav_ulice():
    """Pre kazdy nazov: lacny kluc do textu + regex tolerantny na sklonovanie.

    Regex je CITLIVY na velke pismena: prve slovo nazvu musi byt v texte s velkym
    zaciatocnym pismenom, inak by „dopravna infrastruktura" bola ulica Dopravna.
    Koncovka sa necha volna, aby „na Kosickej" naslo ulicu „Kosicka"."""
    global ULICE
    ULICE = nacitaj_ulice()
    for n in ULICE:
        slova = [w for w in re.split(r"\s+", n) if re.search(r"[A-Za-zÁ-Žá-ž]", w)]
        if not slova:
            continue
        s0 = stem(slova[0])
        if len(s0) < 4 or s0 in ZAKAZ:
            continue
        cast = []
        for i, w in enumerate(slova):
            s = stem(w)
            if len(s) >= 4:
                sc = bdc(w)[:len(s)]           # kmen so zachovanym velkym pismenom
                if i == 0:
                    sc = sc[0].upper() + sc[1:].lower()
                cast.append(re.escape(sc) + r"[a-z]{0,4}")
            else:
                cast.append(re.escape(bdc(w)))
        UL_RE[n] = (s0, re.compile(r"\b" + r"\s+".join(cast) + r"\b"),
                    len(slova) == 1 and s0 in SLABE)
    log("   pouzitelnych nazvov ulic: %d (z toho slabych: %d)"
        % (len(UL_RE), sum(1 for v in UL_RE.values() if v[2])))


def ulice_v_texte(t):
    """Counter nazov -> vaha.

    vaha 5  zmienka so slovom „ulica/cesta/namestie" v okoli alebo s cislom domu
    vaha 3  zmienka vo vete o mieste realizacie
    vaha 1  obycajna zmienka s velkym pismenom
    Slabe nazvy (bezne pridavne mena) sa pocitaju len z prvych dvoch — inak by
    „priemyselna zona" vyhrala nad skutocnou ulicou."""
    tc = bdc(t)
    nt = tc.lower()
    von = collections.Counter()
    okolia = [(m.start() - 120, m.start() + 320) for m in MIESTO.finditer(nt)]
    for n, (s0, rx, slabe) in UL_RE.items():
        if s0 not in nt:
            continue
        v = 0
        for m in rx.finditer(tc):
            okolie = nt[max(0, m.start() - 35):m.end() + 35]
            cislo = re.match(r"\s*(?:[cč]\.\s*)?\d{1,4}\b", tc[m.end():m.end() + 10])
            vmieste = any(a <= m.start() <= b for a, b in okolia)
            if CUE.search(okolie) or cislo:
                v += 5
            elif vmieste:
                v += 3
            elif not slabe:
                v += 1
        if v:
            von[n] = v
    return von


def geom_ulice(n, mcg):
    """Useky ulice orezane na mestsku cast; None ak tam ulica nie je."""
    useky = [LineString(p) for p in ULICE.get(n, [])]
    if mcg is not None:
        useky = [u for u in useky if mcg.intersects(u)]
        if not useky:
            return None
        g = unary_union([mcg.intersection(u) for u in useky])
    else:
        g = unary_union(useky)
    return None if g.is_empty else g


def bod_z_ulice(kand, obec):
    """Vracia (popis, vaha, bod, dlzka_m, presne_li).

    Stred ulice je slaby udaj — Vajnorska ma v Novom Meste pres tri kilometre.
    Ked text spomina dve ulice a tie sa v mestskej casti pretinaju, beriem
    krizovatku: to je uz konkretne miesto, nie priemer celej ulice."""
    mcn, mcg = mc_poly(obec)
    silne = [(n, w) for n, w in kand.most_common(25) if w >= 3]
    geom = {}
    for n, w in silne:
        g = geom_ulice(n, mcg)
        if g is not None and BA.buffer(0.002).contains(g.centroid):
            geom[n] = g
    if not geom:
        return None
    poradie = [n for n, _ in silne if n in geom]
    # krizovatka dvoch najsilnejsie spominanych ulic, ktore sa naozaj stretavaju
    for i, a in enumerate(poradie[:6]):
        for b in poradie[i + 1:7]:
            spolu = geom[a].intersection(geom[b].buffer(0.0004))  # ~30 m tolerancia
            if spolu.is_empty:
                continue
            c = spolu.centroid
            if not BA.buffer(0.002).contains(c):
                continue
            return ("križovatka ulíc „%s“ a „%s“" % (a, b), kand[a] + kand[b],
                    [round(c.x, 6), round(c.y, 6)], spolu.length * 111000, True)
    n = poradie[0]
    g = geom[n]
    c = g.centroid
    dl = g.length * 111000
    return ("ulica „%s“" % n, kand[n], [round(c.x, 6), round(c.y, 6)], dl, dl <= 1500)


# ---------- spis ----------
def cely_spis(zid):
    p = os.path.join(DET, zid + ".json")
    if not os.path.exists(p):
        for f in os.listdir(DET):
            if f.startswith(zid[:40]):
                p = os.path.join(DET, f)
                break
    try:
        d = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return []
    dk = d.get("dokumenty")
    if not isinstance(dk, dict):
        return []
    von = []
    for k in dk.get("data") or []:
        for sk in k.get("items") or []:
            if not isinstance(sk, dict):
                continue
            for it in sk.get("items") or []:
                if isinstance(it, dict) and it.get("url"):
                    von.append({"p": str(it.get("label") or ""),
                                "u": "https://www.enviroportal.sk" + it["url"],
                                "v": int(it.get("filesize") or 0),
                                "t": str(it.get("type") or "").upper(),
                                "sk": str(sk.get("title") or "")})
    return von


def detail(zid):
    p = os.path.join(DET, zid + ".json")
    if not os.path.exists(p):
        for f in os.listdir(DET):
            if f.startswith(zid[:40]):
                p = os.path.join(DET, f)
                break
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


def ulice_uradov(zid):
    """(tvrdo vyradit, znizit vahu).

    Adresa uradu nie je nikdy miesto stavby (Tomasikova 46 je okresny urad), tak ide von.
    Adresa navrhovatela sa len znizi — niekedy to miesto stavby JE: Slovnaft ma sidlo
    na Vlcom hrdle a stavia tam, takze uplne vyradenie by polohu posunulo o 5 km."""
    d = detail(zid)
    urad = re.sub(r"<[^>]+>", " ", " ".join([
        (d.get("prislusnyOrgan") or {}).get("name") or "",
        (d.get("prislusnyOrgan") or {}).get("address") or "",
        d.get("povolujuciOrgan") or "", d.get("schvalujuciOrgan") or ""]))
    navrh = (d.get("navrhovatel") or {}).get("name") or ""
    return set(ulice_v_texte(urad)), set(ulice_v_texte(navrh))


def pdfka(zid, graf_naposled=True):
    v = [d for d in cely_spis(zid) if d["t"] == "PDF" and 5e4 < d["v"] <= MAXMB * 1e6]
    v.sort(key=lambda d: (0 if HLAVNY.search(d["p"] + " " + d["sk"]) else 1,
                          (1 if GRAF.search(d["p"]) else 0) if graf_naposled else 0,
                          -d["v"]))
    return v


# ---------- beh ----------
vysl = {}
if os.path.exists(VYSTUP):
    for z in json.load(io.open(VYSTUP, encoding="utf-8")):
        vysl[z["id"]] = z
    log("pokracujem, hotovych uz %d" % len(vysl))

test = json.load(io.open(os.path.join(TU, "parcely_vsetky_vysledok.json"), encoding="utf-8"))
podla_stavu = collections.defaultdict(list)
for z in test:
    podla_stavu[z.get("stav")].append(z)

FAZY = [("1", "bod mimo udanej MC", "parcely su, mestskej casti z EIA sa neveri"),
        ("2", "parcela sa v katastri nenasla", "register C aj E, vsetky k. u. Bratislavy"),
        ("3", "sken bez textu", "skusit vsetky textove PDF v spise"),
        ("4", "parcela v texte nie je", "nazvy OSM ulic v texte, orezane na MC")]
chce = sys.argv[1] if len(sys.argv) > 1 else None


def uloz():
    json.dump(sorted(vysl.values(), key=lambda z: (z["faza"], z["id"])),
              io.open(VYSTUP, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def z_parciel(v, parc, ku, obec, poznamka=""):
    b, k, p = bod_z_parciel(parc, ku, obec)
    if b:
        v.update(bod=b, ku=k, stav="OK", presnost="presná",
                 zdroj="kataster, ťažisko parciel %s (k. ú. %s)" % (", ".join(parc[:5]), k or "?"),
                 pozn=(poznamka + "; " if poznamka else "") + p)
    elif isinstance(k, tuple):  # neisty bod, nezapisovat automaticky
        v.update(stav="neisté, skontrolovať ručne", bod_neiste=k[0], ku=k[1],
                 zdroj="kataster, ťažisko parciel %s (k. ú. %s)" % (", ".join(parc[:5]), k[1] or "?"),
                 pozn=(poznamka + "; " if poznamka else "") + p)
    else:
        v["stav"] = p
        v["pozn"] = poznamka
    return v


t0 = time.time()
if not chce or chce == "4":
    priprav_ulice()

for faza, stav, popis in FAZY:
    if chce and chce != faza:
        continue
    kand = [z for z in podla_stavu[stav] if z["id"] not in vysl]
    log("\n" + "=" * 78)
    log("FAZA %s — %s (%d zamerov, %s)" % (faza, stav, len(kand), popis))
    log("=" * 78)
    for n, z in enumerate(kand, 1):
        v = {"id": z["id"], "nazov": z["nazov"], "obec": z.get("obec"), "faza": faza,
             "povodny_stav": stav, "stav": "", "bod": None, "ku": None,
             "parcely": z.get("parcely") or [], "presnost": None, "zdroj": "", "pozn": ""}
        try:
            if faza in ("1", "2"):
                z_parciel(v, z["parcely"], z.get("ku"), z.get("obec"))

            elif faza == "3":
                parc, ku, zdroj = [], None, ""
                for d in pdfka(z["id"])[:12]:
                    try:
                        data = stiahni(d["u"])
                        if not data:
                            continue
                        t = text_pdf(data)
                    except Exception:
                        continue
                    if len(t.strip()) < 400:
                        continue
                    ku = ku_z_textu(t) or ku
                    parc = parcely_z_textu(t)
                    if parc:
                        zdroj = "text z: " + d["p"][:70]
                        break
                    time.sleep(0.2)
                if not parc:
                    v["stav"] = "ani v ostatnych PDF nie su parcely"
                else:
                    v["parcely"] = parc
                    z_parciel(v, parc, ku, z.get("obec"), zdroj)

            elif faza == "4":
                # kandidati sa cachuju, aby sa pri ladeni vyberu nemuseli PDF stahovat znova
                ck = os.path.join(KAND, z["id"][:80] + ".json")
                if os.path.exists(ck):
                    kandi = collections.Counter(json.load(io.open(ck, encoding="utf-8")))
                else:
                    kandi = collections.Counter()
                    for d in pdfka(z["id"])[:4]:
                        try:
                            data = stiahni(d["u"])
                            if not data:
                                continue
                            t = text_pdf(data)
                        except Exception:
                            continue
                        if len(t.strip()) < 400:
                            continue
                        for k, w in ulice_v_texte(t).items():
                            kandi[k] += w
                        time.sleep(0.2)
                    if not kandi:  # posledna sanca: ulica v nazve zameru
                        kandi = ulice_v_texte(z["nazov"])
                    json.dump(kandi, io.open(ck, "w", encoding="utf-8"), ensure_ascii=False)
                zle, sidlo = ulice_uradov(z["id"])
                for x in zle:
                    kandi.pop(x, None)
                for x in sidlo:
                    if x in kandi:
                        kandi[x] -= 6
                best = bod_z_ulice(kandi, z.get("obec")) if kandi else None
                if best and best[4]:
                    v.update(bod=best[2], stav="OK", presnost="ulica v MČ",
                             zdroj="OSM %s v %s" % (best[0], z.get("obec")),
                             pozn="váha zmienok %d, dĺžka %.0f m, ďalší kandidáti: %s%s"
                                  % (best[1], best[3],
                                     ", ".join(x for x, _ in kandi.most_common(4)),
                                     ("; vyradené adresy úradov: " + ", ".join(sorted(zle))) if zle else ""))
                elif best:
                    # ulica je prilis dlha, stred useku by predstieral presnost, ktoru nema
                    v.update(stav="ulica je príliš dlhá, len nápoveda", bod_neiste=best[2],
                             zdroj="OSM %s v %s" % (best[0], z.get("obec")),
                             pozn="úsek v MČ má %.0f m, stred nie je miesto stavby; kandidáti: %s"
                                  % (best[3], ", ".join(x for x, _ in kandi.most_common(4))))
                else:
                    v["stav"] = "ulica sa nenašla"
                    v["pozn"] = "kandidáti: %s" % ", ".join(x for x, _ in kandi.most_common(5))
        except Exception as e:
            v["stav"] = "chyba: %s" % str(e)[:90]
        vysl[z["id"]] = v
        log("  %3d/%-3d %-38s %-40s %s" % (
            n, len(kand), v["stav"][:38], z["nazov"][:40],
            ("%.5f,%.5f" % (v["bod"][1], v["bod"][0])) if v["bod"] else ""))
        if n % 5 == 0:
            uloz()
    uloz()

uloz()
log("\n" + "=" * 78)
log("HOTOVO za %.0f min" % ((time.time() - t0) / 60))
for faza, stav, _ in FAZY:
    v = [x for x in vysl.values() if x["faza"] == faza]
    if not v:
        continue
    log("\nFAZA %s (%s), %d zamerov:" % (faza, stav, len(v)))
    for k, c in collections.Counter(x["stav"][:46] for x in v).most_common():
        log("   %-50s %3d" % (k, c))
log("\n  s polohou spolu: %d z %d  (presna %d, ulica v MC %d)" % (
    sum(1 for v in vysl.values() if v["bod"]), len(vysl),
    sum(1 for v in vysl.values() if v.get("presnost") == "presná"),
    sum(1 for v in vysl.values() if v.get("presnost") == "ulica v MČ")))
log("\nvysledok: %s" % VYSTUP)
