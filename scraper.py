import os
import json
import gspread
from bs4 import BeautifulSoup
from datetime import datetime
from playwright.sync_api import sync_playwright

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Resultados_FMP")

print("2. Abriendo navegador virtual y esperando a la web...")
url = "http://www.hockeypatines.fmp.es/league/4202"

# Usamos Playwright para simular un navegador real
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    # Esperamos hasta que la red deje de cargar cosas (el JavaScript termina)
    page.goto(url, wait_until="networkidle")
    html = page.content()
    browser.close()

soup = BeautifulSoup(html, 'html.parser')
partidos = soup.find_all('tr', class_='team_class')

# Preparamos las cabeceras
datos_a_guardar = [["Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado"]] 

print(f"3. ¡Magia! Se han encontrado {len(partidos)} partidos. Extrayendo goles...")
for partido in partidos:
    columnas = partido.find_all('td')
    if len(columnas) > 12: # Asegurarnos de que es una fila de partido real
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
