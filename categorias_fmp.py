"""
Utilidad compartida: saber qué competiciones hay que leer.

- Lee la lista oficial de competiciones de la FMP (todas las temporadas).
- Se queda con la temporada más reciente.
- Rellena SOLA la columna D (ID_Liga) de la pestaña Categorias_FMP
  para cada fila que tenga algo escrito en la columna A (las que sigues),
  buscando su competición por el nombre de la columna B (sin tener en cuenta
  tildes, guiones ni espacios).
- Devuelve {id_liga: nombre_resultados} y el número de temporada.

Si la web de la FMP falla, no se toca nada y se usan los números que ya
haya en la hoja.
"""
import re
import unicodedata

import requests
from bs4 import BeautifulSoup

URL_LISTADO = "https://www.server2.sidgad.es/fmp/fmp_ls_1.php"
HEADERS = {
    'User-Agent': 'Mozilla/5.0',
    'Origin': 'https://www.hockeypatines.fmp.es',
    'Referer': 'https://www.hockeypatines.fmp.es/',
}
TEMPORADA_POR_DEFECTO = "41"  # 2026/27, solo por si la web no responde


def normalizar(texto):
    """'CTO AUT  JÚNIOR' -> 'CTOAUTJUNIOR' (sin tildes, espacios ni signos)."""
    texto = unicodedata.normalize('NFKD', str(texto)).encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'[^A-Z0-9]', '', texto.upper())


def obtener_competiciones_fmp():
    """Devuelve (temporada_mas_reciente, {nombre_normalizado: id_liga})."""
    respuesta = requests.get(URL_LISTADO, headers=HEADERS, timeout=60)
    respuesta.raise_for_status()
    soup = BeautifulSoup(respuesta.text, 'html.parser')

    por_temporada = {}
    for enlace in soup.find_all('a', class_='idc_master'):
        id_liga = (enlace.get('id') or '').strip()
        clases = ' '.join(enlace.get('class', []))
        m = re.search(r'temp_(\d+)', clases)
        div_nombre = enlace.find('div', class_='nombre_competicion_listado')
        if not (id_liga.isdigit() and m and div_nombre):
            continue
        nombre = normalizar(div_nombre.get_text())
        # Si un nombre se repite en la misma temporada, nos quedamos con el primero
        por_temporada.setdefault(m.group(1), {}).setdefault(nombre, id_liga)

    if not por_temporada:
        raise ValueError("La lista de competiciones de la FMP ha llegado vacía")
    temporada = max(por_temporada, key=int)
    return temporada, por_temporada[temporada]


def leer_categorias(libro, actualizar_hoja=True):
    """
    Devuelve (categorias, temporada), donde categorias = {id_liga: nombre_resultados}
    solo para las filas con columna A rellena.
    """
    hoja = libro.worksheet("Categorias_FMP")
    filas = hoja.get_all_values()

    temporada = TEMPORADA_POR_DEFECTO
    competiciones = {}
    try:
        temporada, competiciones = obtener_competiciones_fmp()
        print(f"   -> Temporada más reciente en la FMP: {temporada} ({len(competiciones)} competiciones)")
    except Exception as e:
        print(f"   ⚠️ No se pudo leer la lista de competiciones de la FMP ({e}). Uso los números de la hoja.")

    categorias = {}
    cambios = []
    for num_fila, fila in enumerate(filas[1:], start=2):
        fila = fila + [''] * (4 - len(fila))
        nombre_resultados, nombre_directo, _, id_actual = [c.strip() for c in fila[:4]]
        if not nombre_resultados:
            continue

        id_nuevo = competiciones.get(normalizar(nombre_directo)) if nombre_directo else None
        if id_nuevo and id_nuevo != id_actual:
            print(f"   -> {nombre_resultados}: ID_Liga {id_actual or '(vacío)'} -> {id_nuevo}")
            cambios.append({'range': f'D{num_fila}', 'values': [[int(id_nuevo)]]})
            id_actual = id_nuevo
        elif competiciones and not id_nuevo:
            print(f"   ⚠️ {nombre_resultados}: no encuentro '{nombre_directo}' en la temporada {temporada}. Mantengo {id_actual or '(vacío)'}")

        if id_actual.isdigit():
            categorias[id_actual] = nombre_resultados

    if cambios and actualizar_hoja:
        try:
            hoja.batch_update(cambios, value_input_option='USER_ENTERED')
            print(f"   -> Categorias_FMP actualizada ({len(cambios)} cambios)")
        except Exception as e:
            print(f"   ⚠️ No se pudo escribir en Categorias_FMP: {e}")

    return categorias, temporada


PALABRAS_BORRAR_FASE = [
    "1ª AUTONÓMICA MASCULINA", "1ª AUTONÓMICA FEMENINA", "1ª AUTONOMICA MASCULINA", "1ª AUTONOMICA FEMENINA",
    "CTO AUT", "JÚNIOR", "JUNIOR", "1ª FEMENINA", "1ª AUT FEMENINA",
    "1ª AUT MASCULINA", "1ª AUT. FEM", "1ª AUT. MASC",
    "SUB 17", "SUB-17", "SUB17", "MASCULINA", "FEMENINA", "MASCULINO", "FEMENINO",
    "AUTONÓMICA", "AUTONOMICA",
]


def limpiar_fase(fase_cruda):
    """'CTO AUT JÚNIOR - 1ª FASE - GRUPO A' -> '1ª FASE - GRUPO A'. Sin título -> 'LIGA REGULAR'."""
    nombre_fase = (fase_cruda or "").strip().upper()
    if nombre_fase.startswith("CLASIFICACI"):  # Título genérico de las clasificaciones sin grupos
        return "LIGA REGULAR"
    for p in PALABRAS_BORRAR_FASE:
        nombre_fase = nombre_fase.replace(p, "")
    nombre_fase = re.sub(r"\s+", " ", nombre_fase).replace(" - - ", " - ").strip(" -")
    if nombre_fase in ("FINAL A", "FINAL A 4"):
        nombre_fase = "FINAL 4"
    return nombre_fase or "LIGA REGULAR"
