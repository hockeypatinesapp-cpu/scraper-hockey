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
    
    print("   - Esperando a que el JavaScript dibuje los partidos...")
    try:
        # Aquí está el truco: le decimos que no haga NADA hasta que vea la clase 'team_class'
        page.wait_for_selector('tr.team_class', timeout=15000)
        time.sleep(2) # Le damos 2 segundos extra para que termine de poner los goles
        print("   - ¡Partidos detectados en la pantalla!")
    except Exception as e:
        print("   - Aviso: No aparecieron los partidos a tiempo. Puede que la web esté caída o muy lenta.")
        
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
