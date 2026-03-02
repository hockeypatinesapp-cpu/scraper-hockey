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

print("2. Abriendo navegador virtual (Modo Ninja)...")
url = "http://www.hockeypatines.fmp.es/league/4202"

with sync_playwright() as p:
    # Le ponemos disfraces para que la web crea que somos un humano usando Google Chrome
    browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
    context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    page = context.new_page()
    
    print("   - Cargando la web de la federación...")
    page.goto(url)
    
    print("   - Esperando 15 segundos de reloj para que cargue absolutamente todo...")
    page.wait_for_timeout(15000) # Espera bruta de 15 segundos sí o sí
    
    print("   - Buscando datos en la web principal y en ventanas ocultas (iframes)...")
    # Copiamos el código de la web principal Y de cualquier ventana incrustada
    html_total = page.content()
    for frame in page.frames:
        try:
            html_total += frame.content()
        except:
            pass
            
    browser.close()

soup = BeautifulSoup(html_total, 'html.parser')
partidos = soup.find_all('tr', class_='team_class')

datos_a_guardar = [["Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado"]] 

print(f"3. ¡BINGO! Se han encontrado {len(partidos)} partidos. Extrayendo goles...")
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
