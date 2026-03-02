import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Conectando a Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Resultados_FMP")

print("2. Leyendo la web de la Federación...")
url = "http://www.hockeypatines.fmp.es/league/4202"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
respuesta = requests.get(url, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

partidos = soup.find_all('tr', class_='team_class')
# Preparamos las cabeceras de tu Excel
datos_a_guardar = [["Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado"]] 

print("3. Extrayendo goles y horarios...")
for partido in partidos:
    columnas = partido.find_all('td')
    if len(columnas) > 12:
        fecha = columnas[1].text.strip()
        hora = columnas[2].text.strip()
        local = columnas[6].text.strip()
        visitante = columnas[8].text.strip()
        resultado = columnas[11].text.strip()
        
        # Limpiar texto vacío o saltos de línea raros
        datos_a_guardar.append([fecha, hora, local, visitante, resultado])

print("4. Escribiendo en tu Excel...")
hoja.clear() # Limpia lo viejo
hoja.update(datos_a_guardar, 'A1') # Escribe lo nuevo

print(f"¡ÉXITO! {len(datos_a_guardar)-1} partidos guardados a las {datetime.now()}.")
