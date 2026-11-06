"""Identificación común de los robots ante la web de la FMP.

Desde noviembre de 2026 el servidor de la FMP (sidgad) rechaza con 403 el
navegador abreviado 'Mozilla/5.0': hay que presentarse como un navegador completo.
"""
NAVEGADOR = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
             '(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36')

# Cabeceras completas de un navegador real (con solo el navegador también da 403)
CABECERAS = {
    'User-Agent': NAVEGADOR,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'es-ES,es;q=0.9',
    'Origin': 'https://www.hockeypatines.fmp.es',
    'Referer': 'https://www.hockeypatines.fmp.es/',
}
