import os
import json
import time
import gspread
import requests
import firebase_admin
from firebase_admin import credentials, messaging
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Despertando al Vigilante Inteligente...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja_memoria = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Memoria_Vivo")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")

if not firebase_admin._apps:
    credenciales_firebase = json.loads(os.environ['FIREBASE_JSON'])
    cred = credentials.Certificate(credenciales_firebase)
    firebase_admin.initialize_app(cred)

print("2. Leyendo Diccionario y Memoria...")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_abrev = {}
for fila in datos_dicc[1:]:
    if len(fila) >= 3 and fila[2].strip():
        diccionario_abrev[fila[2].strip().upper()] = {"oficial": fila[0].strip(), "coloquial": fila[1].strip(), "abrev": fila[2].strip()}

marcadores_viejos = {}
try:
    for fila in hoja_memoria.get_all_values()[1:]:
        if len(fila) >= 14:
            marcadores_viejos[f"{fila[6]}_{fila[10]}"] = fila[13]
except: pass

url_vivo = "https://www.server2.sidgad.es/fmp/fmp_mc_1.php"
headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}

# --- CONFIGURACIÓN DE FILTROS ESTRICTOS ---
CATEGORIAS_OBJETIVO = ["JUVENIL", "JUNIOR", "SUB-17 FEM", "1ª MASCULINA", "1ª AUT. MASC"]
PALABRA_EQUIPO_OBJETIVO = "ROZAS"

tiempo_inicio = time.time()
minutos_maximos = 13.0 # A los 13 minutos pedimos el relevo a GitHub

while True:
    print(f"\n--- [Escaneo a las {datetime.now().strftime('%H:%M:%S')}] ---")
    respuesta = requests.post(url_vivo, headers=headers)
    soup = BeautifulSoup(respuesta.text, 'html.parser')
    
    partidos_html = soup.find_all('a', class_=lambda c: c and 'scorer_game' in c)
    nuevos_datos = [["Categoría", "Jornada", "Fecha", "Hora", "Situación", "Local Oficial", "Local Coloquial", "Local Abrev.", "Logo Local", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Logo Visitante", "Resultado en Vivo", "Hora del aviso"]]
    
    hay_objetivos_en_juego = False
    hay_objetivos_en_descanso = False

    for partido in partidos_html:
        try:
            cat = partido.find('div', class_='scorer_liga').text.strip()
            local_abrev = partido.find('div', class_='scorer_team_left').text.strip()
            visitante_abrev = partido.find('div', class_='scorer_team_right').text.strip()
            resultado = partido.find('div', class_='scorer_score').text.strip().replace('\n', ' ')
            situacion = partido.find('div', class_='scorer_bot_center').text.strip().upper()
            
            if not local_abrev or not visitante_abrev: continue
                
            datos_loc = diccionario_abrev.get(local_abrev.upper(), {"oficial": local_abrev, "coloquial": local_abrev, "abrev": local_abrev})
            datos_vis = diccionario_abrev.get(visitante_abrev.upper(), {"oficial": visitante_abrev, "coloquial": visitante_abrev, "abrev": visitante_abrev})
            nom_loc_col, nom_vis_col = datos_loc["coloquial"], datos_vis["coloquial"]
            
            # 1. COMPROBAR SI ES UN PARTIDO QUE NOS INTERESA DE VERDAD
            juega_rozas = PALABRA_EQUIPO_OBJETIVO in nom_loc_col.upper() or PALABRA_EQUIPO_OBJETIVO in nom_vis_col.upper()
            es_categoria = any(c in cat.upper() for c in CATEGORIAS_OBJETIVO)
            
            # Tienen que darse las dos condiciones a la vez
            es_objetivo = juega_rozas and es_categoria

            # 2. SI ES OBJETIVO, ANALIZAR SU ESTADO
            if es_objetivo:
                estados_inactivos = ["FINAL", "SIN COMENZAR", "APLAZAD", "CANCELAD", "SUSPENDID"]
                if not any(estado in situacion for estado in estados_inactivos):
                    hay_objetivos_en_juego = True
                    if "DESCANSO" in situacion:
                        hay_objetivos_en_descanso = True
            
            # Extraer logos, fecha, etc.
            img_loc = partido.find('div', class_='scorer_logo_left').find('img')
            img_vis = partido.find('div', class_='scorer_logo_right').find('img')
            bot_left = partido.find('div', class_='scorer_bot_left').text.strip().split(" ")
            
            nuevos_datos.append([
                cat, partido.find('div', class_='scorer_bot_right').text.strip(), 
                bot_left[0] if len(bot_left)>0 else "", bot_left[1] if len(bot_left)>1 else "", 
                situacion, datos_loc["oficial"], nom_loc_col, datos_loc["abrev"], img_loc['src'] if img_loc else "",
                datos_vis["oficial"], nom_vis_col, datos_vis["abrev"], img_vis['src'] if img_vis else "", 
                resultado, str(datetime.now())
            ])
            
            # --- DISPARADOR FIREBASE ---
            if es_objetivo:
                clave = f"{nom_loc_col}_{nom_vis_col}"
                res_viejo = marcadores_viejos.get(clave)
                if res_viejo is not None and res_viejo != resultado and resultado != "" and "SIN COMENZAR" not in situacion:
                    print(f"   🚨 ¡GOL DETECTADO! {nom_loc_col} {resultado} {nom_vis_col}")
                    mensaje = messaging.Message(
                        notification=messaging.Notification(title=f"🚨 {cat}", body=f"{nom_loc_col} vs {nom_vis_col} | Marcador: {resultado}"),
                        topic="alertas_goles"
                    )
                    messaging.send(mensaje)
                    marcadores_viejos[clave] = resultado 

        except Exception as e: continue 

    hoja_memoria.clear()
    hoja_memoria.update(values=nuevos_datos, range_name='A1')

    # --- LÓGICA DE TIEMPOS Y RELEVOS ---
    if not hay_objetivos_en_juego:
        print("\n😴 No hay partidos de Las Rozas en nuestras categorías objetivo en juego. Me apago.")
        break
        
    tiempo_transcurrido = (time.time() - tiempo_inicio) / 60
    
    if tiempo_transcurrido >= minutos_maximos:
        print("\n⏳ Límite de 13 minutos alcanzado. El partido sigue. ¡Pidiendo el AUTO-RELEVO a GitHub!")
        url_dispatch = f"https://api.github.com/repos/{os.environ['GITHUB_REPOSITORY']}/actions/workflows/vigilante.yml/dispatches"
        headers_gh = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GH_TOKEN']}",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        requests.post(url_dispatch, headers=headers_gh, json={"ref": "main"})
        break

    if hay_objetivos_en_descanso:
        print("⏸️ Partido en DESCANSO. Durmiendo 7 minutos para ahorrar recursos...")
        time.sleep(420)
    else:
        print("🔥 Partido en juego. Esperando 60 segundos...")
        time.sleep(60)
