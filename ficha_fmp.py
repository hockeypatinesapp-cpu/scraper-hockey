"""
FICHA EN DIRECTO DE UN PARTIDO (la que abre la web de la FMP al pulsar un partido)

    https://www.server2.sidgad.es/fmp/fmp_gr_<idp>_1.php

De ahí sacamos lo que el marcador general no trae:
  - el reloj del periodo (cuenta hacia ATRÁS: "04:25" = quedan 4:25), que la mesa
    actualiza cada vez que anota una jugada (no avanza segundo a segundo);
  - la lista de goles con su autor.
"""
import re
import requests
from bs4 import BeautifulSoup

URL_FICHA = "https://www.server2.sidgad.es/fmp/fmp_gr_{idp}_1.php"
HEADERS = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}


def _texto(nodo):
    return re.sub(r'\s+', ' ', nodo.get_text(' ')).strip() if nodo else ''


def nombre_jugador(enlace):
    """<a>ESPINOSA BURKE <span>NOA</span></a> -> 'Noa Espinosa Burke'"""
    if not enlace:
        return ''
    span = enlace.find('span')
    nombre = _texto(span)
    if span:
        span.extract()
    apellidos = _texto(enlace)
    completo = f"{nombre} {apellidos}".strip()
    return ' '.join(p.capitalize() for p in completo.split())


def periodo_legible(texto):
    """'PERIODO 1' -> '1ª parte'; 'PERIODO 2' -> '2ª parte'; otros -> tal cual en minúsculas."""
    t = (texto or '').strip().upper()
    m = re.match(r'PERIODO\s*(\d)', t)
    if m:
        return f"{m.group(1)}ª parte" if m.group(1) in ('1', '2') else f"prórroga {int(m.group(1)) - 2}"
    return t.capitalize() if t else ''


def normalizar_marcador(texto):
    """'2:0' / '2 - 0' -> '2-0'"""
    m = re.search(r'(\d+)\s*[-:]\s*(\d+)', texto or '')
    return f"{m.group(1)}-{m.group(2)}" if m else ''


def parsear_ficha(html):
    """-> {'periodo', 'reloj', 'marcador', 'goles': [{periodo, reloj, equipo, marcador, jugador}] (más reciente primero)}"""
    soup = BeautifulSoup(html, 'html.parser')
    reloj = _texto(soup.find(id='game_time'))
    if not re.fullmatch(r'\d{1,2}:\d{2}', reloj):
        reloj = ''
    local, visit = _texto(soup.find(id='home_score')), _texto(soup.find(id='away_score'))
    goles = []
    tabla = soup.find(id='game_report_inicidencias')
    for fila in (tabla.find_all('tr') if tabla else []):
        if not fila.find('img', src=lambda s: s and 'icon_gol' in s):
            continue
        goles.append({
            'periodo': _texto(fila.find(class_='game_view_indcidencias_period')),
            'reloj': _texto(fila.find(class_='game_view_incidencias_time')),
            'equipo': _texto(fila.find(class_='texto_gris_11')),
            'marcador': normalizar_marcador(_texto(fila.find(class_='game_view_incidencias_result'))),
            'jugador': nombre_jugador(fila.find('a', class_='nombre_ficha_jugador_plus')),
        })
    return {
        'periodo': _texto(soup.find(id='game_period')),
        'reloj': reloj,
        'marcador': f"{local}-{visit}" if local.isdigit() and visit.isdigit() else '',
        'goles': goles,
    }


def leer_ficha(idp, timeout=8):
    """Descarga y lee la ficha; None si falla (nunca debe romper el Vigilante)."""
    if not idp or not str(idp).isdigit():
        return None
    try:
        r = requests.post(URL_FICHA.format(idp=idp), headers=HEADERS, timeout=timeout)
        if r.status_code != 200 or 'game_score' not in r.text:
            return None
        return parsear_ficha(r.text)
    except Exception:
        return None


def gol_con_marcador(ficha, marcador):
    """El gol de la ficha que dejó el partido con ese marcador ('2:0' o '2-0'), o None."""
    objetivo = normalizar_marcador(marcador)
    for g in (ficha or {}).get('goles', []):
        if objetivo and g['marcador'] == objetivo:
            return g
    return None


def quien_marca(marcador_viejo, marcador_nuevo):
    """'2:0' -> '3:0' = 'local'; '2:0' -> '2:1' = 'visitante'; otro caso (corrección, dos goles a la vez...) = None"""
    a, b = normalizar_marcador(marcador_viejo) or '0-0', normalizar_marcador(marcador_nuevo)
    if not a or not b:
        return None
    (l1, v1), (l2, v2) = [tuple(int(x) for x in m.split('-')) for m in (a, b)]
    if l2 > l1 and v2 == v1:
        return 'local'
    if v2 > v1 and l2 == l1:
        return 'visitante'
    return None


def detalle_gol(gol):
    """-> '🏑 Noa Espinosa Burke · 1ª parte, quedaban 07:12' (o '' si no hay datos)"""
    if not gol:
        return ''
    partes = []
    if gol.get('jugador'):
        partes.append(f"🏑 {gol['jugador']}")
    per = periodo_legible(f"PERIODO {gol['periodo'][1:]}" if re.fullmatch(r'P\d', gol.get('periodo', '')) else gol.get('periodo', ''))
    cuando = ', '.join(x for x in [per, f"quedaban {gol['reloj']}" if gol.get('reloj') else ''] if x)
    if cuando:
        partes.append(cuando)
    return ' · '.join(partes)
