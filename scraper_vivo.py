import os
import json
import gspread
import requests
import firebase_admin
from firebase_admin import credentials, messaging
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Despertando al Vigilante...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja_memoria = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Memoria_Vivo")

print("2. Leyendo el Diccionario de Equipos...")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_abrev = {}
for fila in datos_dicc[1:]:
    if len(fila) >= 3:
        abrev_key = fila[2].strip().upper() # Usamos la abreviatura como llave
        if abrev_key:
            diccionario_abrev[abrev_key] = {
                "oficial": fila[0].strip(),
                "coloquial": fila[1].strip(),
                "abrev": fila[2].strip()
            }

if not firebase_admin._apps:
    credenciales_firebase = json.loads(os.environ['FIREBASE_JSON'])
    cred = credentials.Certificate(credenciales_firebase)
    firebase_admin.initialize_app(cred)

print("3. Leyendo la memoria de los últimos 15 minutos...")
marcadores_viejos = {}
try:
    datos_viejos = hoja_memoria.get_all_values()
    for fila in datos_viejos[1:]:
        if len(fila) >= 14: # Tenemos muchas más columnas ahora
            # Usaremos los nombres Coloquiales como clave para la memoria (Están en las columnas 6 y 10)
            clave = f"{fila[6]}_{fila[10]}" 
            marcadores_viejos[clave] = fila[13] # El resultado está en la columna 13
except Exception:
    pass

print("4. Mirando el panel en vivo de la Federación...")
url_vivo = "https://www.server2.sidgad.es/fmp/fmp_mc_1.php"
headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}

respuesta = requests.post(url_vivo, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

partidos_html = soup.find_all('a', class_=lambda c: c and 'scorer_game' in c)

# ⚠️ NUEVAS CABECERAS PARA EL VIVO
nuevos_datos = [["Categoría", "Jornada", "Fecha", "Hora", "Situación", "Local Oficial", "Local Coloquial", "Local Abrev.", "Logo Local", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Logo Visitante", "Resultado en Vivo", "Hora del aviso"]]

for partido in partidos_html:
    try:
        cat = partido.find('div', class_='scorer_liga').text.strip()
        local_abrev = partido.find('div', class_='scorer_team_left').text.strip()
        visitante_abrev = partido.find('div', class_='scorer_team_right').text.strip()
        resultado = partido.find('div', class_='scorer_score').text.strip().replace('\n', ' ')
        
        div_logo_local = partido.find('div', class_='scorer_logo_left')
        logo_local = div_logo_local.find('img')['src'] if div_logo_local and div_logo_local.find('img') else ""
        
        div_logo_visit = partido.find('div', class_='scorer_logo_right')
        logo_visitante = div_logo_visit.find('img')['src'] if div_logo_visit and div_logo_visit.find('img') else ""
        
        bot_left = partido.find('div', class_='scorer_bot_left').text.strip()
        partes_fecha = bot_left.split(" ")
        fecha = partes_fecha[0] if len(partes_fecha) > 0 else bot_left
        hora = partes_fecha[1] if len(partes_fecha) > 1 else ""
        
        situacion = partido.find('div', class_='scorer_bot_center').text.strip()
        jornada = partido.find('div', class_='scorer_bot_right').text.strip()
        
        if not local_abrev or not visitante_abrev: continue
            
        # OBTENEMOS EL PACK COMPLETO DE NOMBRES DESDE EL DICCIONARIO
        datos_loc = diccionario_abrev.get(local_abrev.upper(), {"oficial": local_abrev, "coloquial": local_abrev, "abrev": local_abrev})
        datos_vis = diccionario_abrev.get(visitante_abrev.upper(), {"oficial": visitante_abrev, "coloquial": visitante_abrev, "abrev": visitante_abrev})
        
        nuevos_datos.append([
            cat, jornada, fecha, hora, situacion, 
            datos_loc["oficial"], datos_loc["coloquial"], datos_loc["abrev"], logo_local,
            datos_vis["oficial"], datos_vis["coloquial"], datos_vis["abrev"], logo_visitante, 
            resultado, str(datetime.now())
        ])
        
        # --- EL DISPARADOR DE FIREBASE ---
        # Usaremos los nombres coloquiales para las alertas push porque quedan más naturales
        nom_loc_col = datos_loc["coloquial"]
        nom_vis_col = datos_vis["coloquial"]
        
        clave = f"{nom_loc_col}_{nom_vis_col}"
        res_viejo = marcadores_viejos.get(clave)
        
        if res_viejo is not None and res_viejo != resultado:
            if "SIN COMENZAR" not in resultado.upper() and resultado != "":
                print(f"   🚨 ¡GOL DETECTADO! {nom_loc_col} {resultado} {nom_vis_col}")
                
                mensaje = messaging.Message(
                    notification=messaging.Notification(
                        title=f"🚨 ¡Novedades en {cat}!",
                        body=f"{nom_loc_col} vs {nom_vis_col} | Marcador: {resultado}"
                    ),
                    topic="alertas_goles"
                )
                messaging.send(mensaje)
    except Exception as e:
        continue 

print("5. Actualizando la Memoria_Vivo en Excel...")
hoja_memoria.clear()
hoja_memoria.update(nuevos_datos, 'A1')
print("¡Turno del Vigilante terminado con base de datos ampliada!")
