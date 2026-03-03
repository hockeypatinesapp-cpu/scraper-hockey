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
        if len(fila) >= 4:
            clave = f"{fila[1]}_{fila[2]}" # Local_Visitante
            marcadores_viejos[clave] = fila[3] # Resultado
except Exception:
    pass # Si está vacía, no pasa nada

print("3. Mirando el panel en vivo de la Federación...")
url_vivo = "https://www.server2.sidgad.es/fmp/fmp_mc_1.php"
headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es'}

respuesta = requests.post(url_vivo, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

# Buscamos todos los bloques de partido (los 'a' que contienen 'scorer_game')
partidos_html = soup.find_all('a', class_=lambda c: c and 'scorer_game' in c)

nuevos_datos = [["Categoría", "Local", "Visitante", "Resultado en Vivo", "Hora del aviso"]]

print(f"   -> ¡Se están jugando {len(partidos_html)} partidos ahora mismo!")

for partido in partidos_html:
    try:
        cat = partido.find('div', class_='scorer_liga').text.strip()
        local = partido.find('div', class_='scorer_team_left').text.strip()
        visitante = partido.find('div', class_='scorer_team_right').text.strip()
        resultado = partido.find('div', class_='scorer_score').text.strip().replace('\n', ' ')
        
        if not local or not visitante: continue
            
        nuevos_datos.append([cat, local, visitante, resultado, str(datetime.now())])
        
        # --- EL DISPARADOR DE FIREBASE ---
        clave = f"{local}_{visitante}"
        res_viejo = marcadores_viejos.get(clave)
        
        # Si el partido ya lo teníamos guardado y el resultado ha cambiado...
        if res_viejo is not None and res_viejo != resultado:
            # Y no es un partido sin empezar...
            if "SIN COMENZAR" not in resultado.upper() and resultado != "":
                print(f"   🚨 ¡GOL DETECTADO! {local} {resultado} {visitante}")
                
                # ¡Enviamos el Push a los móviles!
                mensaje = messaging.Message(
                    notification=messaging.Notification(
                        title=f"🚨 ¡Novedades en {cat}!",
                        body=f"{local} vs {visitante} | Marcador: {resultado}"
                    ),
                    topic="alertas_goles"
                )
                messaging.send(mensaje)
    except Exception as e:
        continue # Si un partido tiene formato raro, lo ignoramos

print("4. Actualizando la Memoria_Vivo en Excel...")
hoja_memoria.clear()
hoja_memoria.update(nuevos_datos, 'A1')
print("¡Turno del Vigilante terminado!")
