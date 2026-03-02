import os
import json
import time
import gspread
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Resultados_FMP")

print("2. Abriendo navegador virtual...")
url = "http://www.hockeypatines.fmp.es/league/4202"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    print("   - Cargando la web de la federación...")
    page.goto(url)
    
    print("   - Esperando a que el código dibuje los partidos...")
    try:
        # EL TRUCO ESTÁ AQUÍ: state='attached' (busca en el código fuente, aunque no se vea en pantalla)
        page.wait_for_selector('tr.team_class', state='attached', timeout=15000)
        time.sleep(3) # Pausa extra para asegurar que cargan todos los goles
        print("   - ¡Partidos detectados en el código!")
    except Exception as e:
        print("   - Aviso: No aparecieron los partidos a tiempo.")
        
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'html.parser')
partidos = soup.find_all('tr', class_='team_class')

datos_a_guardar = [["Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado"]] 

print(f"3. Se han encontrado {len(partidos)} partidos. Extrayendo goles...")
for partido in partidos:
    columnas = partido.find_all('td')
    if len(columnas) > 12:
        fecha = columnas[1].text.strip()
        hora = columnas[2].text.strip()
        local = columnas[6].text.strip()
        visitante = columnas[8].text.strip()
        resultado = columnas[11].text.strip()
        
        datos_a_guardar.append([fecha, hora, local, visitante, resultado])

print("4. Escribiendo en tu Excel...")
hoja.clear() 
hoja.update(datos_a_guardar, 'A1') 

print(f"¡ÉXITO TOTAL! {len(datos_a_guardar)-1} partidos guardados a las {datetime.now()}.")
