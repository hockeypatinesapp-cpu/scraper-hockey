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

if not firebase_admin._apps:
    credenciales_firebase = json.loads(os.environ['FIREBASE_JSON'])
    cred = credentials.Certificate(credenciales_firebase)
    firebase_admin.initialize_app(cred)

print("2. Leyendo la memoria de los últimos 15 minutos...")
marcadores_viejos = {}
try:
    datos_viejos = hoja_memoria.get_all_values()
    for fila in datos_viejos[1:]: # Ignorar cabeceras
        # Hemos actualizado el índice porque ahora hay más columnas
        if len(fila) >= 10: 
            clave = f"{fila[5]}_{fila[7]}" # Local_Visitante
            marcadores_viejos[clave] = fila[9] # Resultado
except Exception:
    pass

print("3. Mirando el panel en vivo de la Federación...")
url_vivo = "https://www.server2.sidgad.es/fmp/fmp_mc_1.php"
headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}

respuesta = requests.post(url_vivo, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

partidos_html = soup.find_all('a', class_=lambda c: c and 'scorer_game' in c)

# Nuevas cabeceras ampliadas para el Excel
nuevos_datos = [["Categoría", "Jornada", "Fecha", "Hora", "Situación", "Local", "Logo Local", "Visitante", "Logo Visitante", "Resultado en Vivo", "Hora del aviso"]]

print(f"   -> ¡Se están jugando {len(partidos_html)} partidos ahora mismo!")

for partido in partidos_html:
    try:
        cat = partido.find('div', class_='scorer_liga').text.strip()
        local = partido.find('div', class_='scorer_team_left').text.strip()
        visitante = partido.find('div', class_='scorer_team_right').text.strip()
        resultado = partido.find('div', class_='scorer_score').text.strip().replace('\n', ' ')
        
        # --- EXTRACCIÓN DE NUEVOS DATOS ---
        # 1. Logos (Buscamos la etiqueta <img> y sacamos el enlace 'src')
        div_logo_local = partido.find('div', class_='scorer_logo_left')
        logo_local = div_logo_local.find('img')['src'] if div_logo_local and div_logo_local.find('img') else ""
        
        div_logo_visit = partido.find('div', class_='scorer_logo_right')
        logo_visitante = div_logo_visit.find('img')['src'] if div_logo_visit and div_logo_visit.find('img') else ""
        
        # 2. Fecha y Hora (Cortamos el texto "28/02 12:30" por el espacio)
        bot_left = partido.find('div', class_='scorer_bot_left').text.strip()
        partes_fecha = bot_left.split(" ")
        fecha = partes_fecha[0] if len(partes_fecha) > 0 else bot_left
        hora = partes_fecha[1] if len(partes_fecha) > 1 else ""
        
        # 3. Situación y Jornada
        situacion = partido.find('div', class_='scorer_bot_center').text.strip()
        jornada = partido.find('div', class_='scorer_bot_right').text.strip()
        
        if not local or not visitante: continue
            
        # Ordenamos los datos según las nuevas cabeceras
        nuevos_datos.append([cat, jornada, fecha, hora, situacion, local, logo_local, visitante, logo_visitante, resultado, str(datetime.now())])
        
        # --- EL DISPARADOR DE FIREBASE ---
        clave = f"{local}_{visitante}"
        res_viejo = marcadores_viejos.get(clave)
        
        if res_viejo is not None and res_viejo != resultado:
            if "SIN COMENZAR" not in resultado.upper() and resultado != "":
                print(f"   🚨 ¡GOL DETECTADO! {local} {resultado} {visitante}")
                
                mensaje = messaging.Message(
                    notification=messaging.Notification(
                        title=f"🚨 ¡Novedades en {cat}!",
                        body=f"{local} vs {visitante} | Marcador: {resultado}"
                    ),
                    topic="alertas_goles"
                )
                messaging.send(mensaje)
    except Exception as e:
        continue 

print("4. Actualizando la Memoria_Vivo en Excel...")
hoja_memoria.clear()
hoja_memoria.update(nuevos_datos, 'A1')
print("¡Turno del Vigilante terminado con nuevos campos!")
