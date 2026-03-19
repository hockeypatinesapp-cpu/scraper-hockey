import os
import json
import time
import gspread
import requests
import firebase_admin
import subprocess
from firebase_admin import credentials, messaging
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

print("1. Despertando al Vigilante Inteligente...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja_memoria = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Memoria_Vivo")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")

print("1.5. Leyendo Categorías dinámicas...")
hoja_categorias = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Categorias_FMP")
datos_cat = hoja_categorias.get_all_values()

CATEGORIAS_OBJETIVO = []
for fila in datos_cat[1:]:
    if len(fila) >= 1 and fila[0].strip(): CATEGORIAS_OBJETIVO.append(fila[0].strip().upper())
    if len(fila) >= 2 and fila[1].strip(): CATEGORIAS_OBJETIVO.append(fila[1].strip().upper())
CATEGORIAS_OBJETIVO = list(set(CATEGORIAS_OBJETIVO))

print("1.6. Leyendo Suscripciones de la App...")
try:
    hoja_suscripciones = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Suscripciones_App")
    datos_suscripciones = hoja_suscripciones.get_all_values()
    suscripciones_tokens = {} 
    for fila in datos_suscripciones[1:]:
        if len(fila) >= 2 and fila[0].strip():
            token = fila[0].strip()
            cats_usuario = [c.strip().upper() for c in fila[1].split(',')]
            for c in cats_usuario:
                if c not in suscripciones_tokens:
                    suscripciones_tokens[c] = []
                suscripciones_tokens[c].append(token)
except Exception as e:
    print("   ⚠️ No se pudo leer Suscripciones_App (o está vacía).")
    suscripciones_tokens = {}

if not firebase_admin._apps:
    credenciales_firebase = json.loads(os.environ['FIREBASE_JSON'])
    cred = credentials.Certificate(credenciales_firebase)
    firebase_admin.initialize_app(cred)

def enviar_alerta_push(categoria_partido, titulo, cuerpo):
    tokens_destino = []
    for cat_guardada, tokens in suscripciones_tokens.items():
        if cat_guardada in categoria_partido.upper() or categoria_partido.upper() in cat_guardada:
            tokens_destino.extend(tokens)
            
    tokens_destino = list(set(tokens_destino)) 
    
    if tokens_destino:
        mensaje = messaging.MulticastMessage(
            notification=messaging.Notification(title=titulo, body=cuerpo),
            tokens=tokens_destino
        )
        try:
            response = messaging.send_multicast(mensaje)
            print(f"   📣 Push enviada con éxito a {response.success_count} dispositivos suscritos a {categoria_partido}.")
        except Exception as e:
            print(f"   ❌ Error enviando Push: {e}")
    else:
        print(f"   🔇 No hay dispositivos suscritos a {categoria_partido} para enviar la alerta.")

print("2. Leyendo Diccionario y Memoria...")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_abrev = {}
for fila in datos_dicc[1:]:
    if len(fila) >= 3 and fila[2].strip():
        diccionario_abrev[fila[2].strip().upper()] = {"oficial": fila[0].strip(), "coloquial": fila[1].strip(), "abrev": fila[2].strip()}

marcadores_viejos = {}
estados_viejos = {} 
try:
    for fila in hoja_memoria.get_all_values()[1:]:
        if len(fila) >= 14:
            marcadores_viejos[f"{fila[6]}_{fila[10]}"] = fila[13]
            estados_viejos[f"{fila[6]}_{fila[10]}"] = fila[4]
except: pass

url_vivo = "https://www.server2.sidgad.es/fmp/fmp_mc_1.php"
headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}
PALABRAS_EQUIPO_OBJETIVO = ["ROZAS", "ROZ"]
tiempo_inicio = time.time()
minutos_maximos = 13.0 

while True:
    ahora_espana = datetime.utcnow() + timedelta(hours=1)
    print(f"\n--- [Escaneo a las {ahora_espana.strftime('%H:%M:%S')}] ---")
    
    respuesta = requests.post(url_vivo, headers=headers)
    soup = BeautifulSoup(respuesta.text, 'html.parser')
    
    partidos_html = soup.find_all('a', class_=lambda c: c and 'scorer_game' in c)
    nuevos_datos = [["Categoría", "Jornada", "Fecha", "Hora", "Situación", "Local Oficial", "Local Coloquial", "Local Abrev.", "Logo Local", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Logo Visitante", "Resultado en Vivo", "Hora del aviso"]]
    
    hay_objetivos_en_juego = False
    hay_objetivos_en_descanso = False
    hay_objetivos_en_calentamiento = False 

    for partido in partidos_html:
        try:
            left_div = partido.find('div', class_='scorer_team_left')
            right_div = partido.find('div', class_='scorer_team_right')
            if not left_div or not right_div: continue
            
            local_abrev = left_div.text.strip()
            visitante_abrev = right_div.text.strip()
            
            if not local_abrev or not visitante_abrev or "DESCANSO" in local_abrev.upper() or "DESCANSO" in visitante_abrev.upper(): 
                continue

            cat_div = partido.find('div', class_='scorer_liga')
            cat = cat_div.text.strip() if cat_div else "Sin Categoría"
            
            score_div = partido.find('div', class_='scorer_score')
            resultado = score_div.text.strip().replace('\n', ' ') if score_div else ""
            
            sit_div = partido.find('div', class_='scorer_bot_center')
            situacion = sit_div.text.strip().upper() if sit_div else ""
                
            datos_loc = diccionario_abrev.get(local_abrev.upper(), {"oficial": local_abrev, "coloquial": local_abrev, "abrev": local_abrev})
            datos_vis = diccionario_abrev.get(visitante_abrev.upper(), {"oficial": visitante_abrev, "coloquial": visitante_abrev, "abrev": visitante_abrev})
            nom_loc_col, nom_vis_col = datos_loc["coloquial"], datos_vis["coloquial"]
            abrev_loc, abrev_vis = datos_loc["abrev"], datos_vis["abrev"]
            
            juega_rozas = any(p in nom_loc_col.upper() or p in nom_vis_col.upper() or p == abrev_loc.upper() or p == abrev_vis.upper() for p in PALABRAS_EQUIPO_OBJETIVO)
            es_categoria = any(c in cat.upper() for c in CATEGORIAS_OBJETIVO)
            es_objetivo = juega_rozas and es_categoria

            if es_objetivo:
                estados_muertos = ["FINAL", "APLAZAD", "CANCELAD", "SUSPENDID"]
                if not any(estado in situacion for estado in estados_muertos):
                    hay_objetivos_en_juego = True
                    if "DESCANSO" in situacion: hay_objetivos_en_descanso = True
                    elif "SIN COMENZAR" in situacion: hay_objetivos_en_calentamiento = True
            
            div_logo_loc = partido.find('div', class_='scorer_logo_left')
            img_loc = div_logo_loc.find('img') if div_logo_loc else None
            
            div_logo_vis = partido.find('div', class_='scorer_logo_right')
            img_vis = div_logo_vis.find('img') if div_logo_vis else None
            
            bot_left_div = partido.find('div', class_='scorer_bot_left')
            bot_left = bot_left_div.text.strip().split(" ") if bot_left_div else ["", ""]
            
            bot_right_div = partido.find('div', class_='scorer_bot_right')
            jornada = bot_right_div.text.strip() if bot_right_div else ""
            
            hora_registro = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
            
            nuevos_datos.append([
                cat, jornada, 
                bot_left[0] if len(bot_left)>0 else "", bot_left[1] if len(bot_left)>1 else "", 
                situacion, datos_loc["oficial"], nom_loc_col, abrev_loc, img_loc['src'] if img_loc else "",
                datos_vis["oficial"], nom_vis_col, abrev_vis, img_vis['src'] if img_vis else "", 
                resultado, hora_registro
            ])
            
            if es_objetivo:
                clave = f"{nom_loc_col}_{nom_vis_col}"
                res_viejo = marcadores_viejos.get(clave)
                est_viejo = estados_viejos.get(clave)

                if situacion != "SIN COMENZAR" and (est_viejo == "SIN COMENZAR" or est_viejo is None) and "FINAL" not in situacion:
                    print(f"   ⏱️ ¡PARTIDO COMENZADO! {nom_loc_col} vs {nom_vis_col}")
                    enviar_alerta_push(cat, f"⏱️ ¡Empieza el partido! - {cat}", f"{nom_loc_col} vs {nom_vis_col} ya están en la pista.")
                    estados_viejos[clave] = situacion

                if res_viejo is not None and res_viejo != resultado and resultado != "" and "SIN COMENZAR" not in situacion:
                    print(f"   🚨 ¡GOL DETECTADO! {nom_loc_col} {resultado} {nom_vis_col}")
                    enviar_alerta_push(cat, f"🚨 ¡GOL! - {cat}", f"{nom_loc_col} {resultado} {nom_vis_col}")
                    marcadores_viejos[clave] = resultado 

                if "FINAL" in situacion and est_viejo is not None and "FINAL" not in est_viejo:
                    print(f"   🏁 ¡PARTIDO TERMINADO! {nom_loc_col} {resultado} {nom_vis_col}")
                    enviar_alerta_push(cat, f"🏁 Final del partido - {cat}", f"Resultado final: {nom_loc_col} {resultado} {nom_vis_col}")
                    subprocess.run(["python", "scraper.py"])
                    subprocess.run(["python", "scraper_clasificacion.py"])
                    subprocess.run(["python", "scraper_plantillas.py"])
                    estados_viejos[clave] = situacion
                
                if est_viejo != situacion:
                    estados_viejos[clave] = situacion

        except Exception as e:
            print(f"   ⚠️ Error procesando un partido: {e}")
            continue 

    hoja_memoria.clear()
    hoja_memoria.update(values=nuevos_datos, range_name='A1')

    if not hay_objetivos_en_juego:
        print("\n😴 No hay partidos de Las Rozas en nuestras categorías objetivo en juego. Me apago.")
        break
        
    tiempo_transcurrido = (time.time() - tiempo_inicio) / 60
    if tiempo_transcurrido >= minutos_maximos:
        print("\n⏳ Límite de 13 minutos alcanzado. Pidiendo el AUTO-RELEVO a GitHub...")
        url_dispatch = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/vigilante.yml/dispatches"
        headers_gh = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {os.environ['GH_TOKEN']}", "X-GitHub-Api-Version": "2022-11-28"}
        requests.post(url_dispatch, headers=headers_gh, json={"ref": "main"})
        break

    if hay_objetivos_en_descanso: time.sleep(420)
    elif hay_objetivos_en_calentamiento: time.sleep(180)
    else: time.sleep(60)
