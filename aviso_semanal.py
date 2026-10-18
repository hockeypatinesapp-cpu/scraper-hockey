"""
AVISO SEMANAL (lunes 9:00, lo lanza el Despertador de la hoja)

Envía una notificación por móvil suscrito con los partidos de Las Rozas de
sus categorías desde HOY (lunes) hasta el LUNES SIGUIENTE incluido.
Quien no tenga partidos en ese periodo no recibe nada.

MODO=prueba  -> no envía nada; solo calcula y lo anota en Despertador_Log
MODO=enviar  -> envía las notificaciones
"""
import os
import json
import unicodedata
from datetime import datetime, timedelta

import gspread
import pytz

ZONA = pytz.timezone('Europe/Madrid')
PALABRAS_EQUIPO = ["ROZAS", "ROZ"]
DIAS = ['Lun', 'Mar', 'Mié', 'Jue', 'Vie', 'Sáb', 'Dom']
URL_APP = 'https://la-azul.web.app/'   # al tocar el aviso se abre la app (pestaña Inicio)
MODO = os.environ.get('MODO', 'prueba').strip().lower()


def normalizar_texto(texto):
    texto = str(texto or '')
    sin_acentos = ''.join(c for c in unicodedata.normalize('NFD', texto) if unicodedata.category(c) != 'Mn')
    return sin_acentos.upper().strip()


def clave_categoria(texto):
    """'Sub17' / 'SUB-17 FEM' -> 'SUB17'; 'AutMas' / '1ª AUT. MASC' -> 'AUTMAS'; ..."""
    n = ''.join(ch for ch in normalizar_texto(texto) if ch.isalnum())
    if not n:
        return ""
    if "SUB17" in n: return "SUB17"
    if "JUNIOR" in n: return "JUNIOR"
    if "FEM" in n: return "AUTFEM"
    if "MAS" in n: return "AUTMAS"
    return n


def parse_fecha(fecha):
    """'7/11/2026' o '07/11/2026' -> date"""
    try:
        d, m, a = [int(x) for x in str(fecha).strip().split('/')[:3]]
        return datetime(a, m, d).date()
    except Exception:
        return None


def ventana(hoy):
    """Desde hoy (si es lunes) / el lunes de esta semana, hasta el lunes siguiente incluido."""
    lunes = hoy - timedelta(days=hoy.weekday())
    return lunes, lunes + timedelta(days=7)


def partidos_semana(filas_resultados, categorias, desde, hasta):
    """Partidos de Las Rozas de las categorías seguidas (columna A de Categorias_FMP)."""
    out = []
    for f in filas_resultados[1:]:
        f = f + [''] * (15 - len(f))
        cat = f[0].strip()
        info = categorias.get(normalizar_texto(cat))
        if not info:
            continue
        loc_col, vis_col = f[6].upper(), f[10].upper()
        loc_ab, vis_ab = f[7].strip().upper(), f[11].strip().upper()
        juega = any(p in loc_col or p in vis_col or p == loc_ab or p == vis_ab for p in PALABRAS_EQUIPO)
        if not juega:
            continue
        dia = parse_fecha(f[3])
        if not dia or not (desde <= dia <= hasta):
            continue
        hora = f[4].strip()[:5]
        out.append({
            'clave': info['clave'], 'abrev': info['abrev'], 'dia': dia, 'hora': hora,
            'local': f[7].strip() or f[6].strip(), 'visitante': f[11].strip() or f[10].strip(),
        })
    out.sort(key=lambda p: (p['dia'], p['hora'] or '99:99'))
    return out


def linea(p):
    hora = p['hora'] if p['hora'] else 'hora por confirmar'
    return f"{p['abrev']} · {DIAS[p['dia'].weekday()]} {p['dia'].day}, {hora} · {p['local']} – {p['visitante']}"


def construir_avisos(filas_suscripciones, partidos):
    """{token: [líneas]} solo para móviles con partidos de sus categorías."""
    avisos = {}
    for f in filas_suscripciones[1:]:
        if len(f) < 2 or not f[0].strip():
            continue
        token = f[0].strip()
        claves = {clave_categoria(c) for c in f[1].split(',') if c.strip()}
        lineas = [linea(p) for p in partidos if p['clave'] in claves]
        if lineas:
            avisos[token] = lineas   # si un token se repite, vale la última fila
    return avisos


def main():
    credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
    libro = gspread.service_account_from_dict(credenciales).open_by_key(os.environ['SHEET_ID'])

    categorias = {}
    for f in libro.worksheet('Categorias_FMP').get_all_values()[1:]:
        f = f + [''] * (3 - len(f))
        if f[0].strip():
            categorias[normalizar_texto(f[0])] = {
                'clave': clave_categoria(f[1] or f[0]),
                'abrev': f[2].strip() or f[0].strip(),
            }

    hoy = datetime.now(ZONA).date()
    desde, hasta = ventana(hoy)
    partidos = partidos_semana(libro.worksheet('Resultados_FMP').get_all_values(), categorias, desde, hasta)
    avisos = construir_avisos(libro.worksheet('Suscripciones_App').get_all_values(), partidos)

    titulo = '📅 Partidos de esta semana'
    print(f"Semana {desde:%d/%m} – {hasta:%d/%m}: {len(partidos)} partidos de Las Rozas; {len(avisos)} móviles con aviso")
    for p in partidos:
        print('  ', linea(p))

    enviados = fallidos = 0
    if MODO == 'enviar' and avisos:
        import firebase_admin
        from firebase_admin import credentials, messaging
        if not firebase_admin._apps:
            firebase_admin.initialize_app(credentials.Certificate(json.loads(os.environ['FIREBASE_JSON'])))
        mensajes = [
            messaging.Message(notification=messaging.Notification(title=titulo, body='\n'.join(lineas)), token=token,
                              webpush=messaging.WebpushConfig(fcm_options=messaging.WebpushFCMOptions(link=URL_APP)))
            for token, lineas in avisos.items()
        ]
        for i in range(0, len(mensajes), 500):
            r = messaging.send_each(mensajes[i:i + 500])
            enviados += r.success_count
            fallidos += r.failure_count
        print(f"Enviados: {enviados} · fallidos (móviles dados de baja o tokens caducados): {fallidos}")

    if MODO == 'enviar':
        resumen = f"📅 Aviso semanal: {len(partidos)} partidos · enviado a {enviados} móviles ({fallidos} fallidos)"
    else:
        resumen = (f"🧪 Prueba aviso semanal ({desde:%d/%m}–{hasta:%d/%m}): {len(partidos)} partidos, "
                   f"{len(avisos)} móviles. " + ' | '.join(linea(p) for p in partidos[:6]))
    try:
        log = libro.worksheet('Despertador_Log')
        log.insert_row([datetime.now(ZONA).strftime('%d/%m/%Y %H:%M:%S'), resumen[:480]], 1)
    except Exception as e:
        print(f"No se pudo anotar en Despertador_Log: {e}")


if __name__ == '__main__':
    main()
