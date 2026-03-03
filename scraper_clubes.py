import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Clubes_FMP")

print("2. Leyendo la web del directorio de clubes...")
url = "https://www.fmp.es/clubes-de-hockey-sobre-patines/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

respuesta = requests.get(url, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

clubes_html = soup.find_all('h3')

datos_a_guardar = [["Nombre Oficial", "Población", "Web", "E-mail", "Pista", "Dirección Pista", "Última Actualización"]]

print(f"3. ¡Encontrados {len(clubes_html)} clubes! Extrayendo datos de sus tablas...")

for h3 in clubes_html:
    nombre_club = h3.text.strip()
    tabla = h3.find_next_sibling('table')
    
    if tabla:
        # AQUÍ ESTABA EL FALLO: Hemos cambiado "Pista" por "PISTA" para que coincida exactamente
        datos_club = {"POBLACIÓN": "", "WEB": "", "E-MAIL": "", "PISTA": "", "DIRECCIÓN PISTA": ""}
        
        filas = tabla.find_all('tr')
        for fila in filas:
            th = fila.find('th')
            td = fila.find('td')
            if th and td:
                clave = th.text.strip().upper()
                if clave in datos_club:
                    datos_club[clave] = td.text.strip()
                    
        ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        datos_a_guardar.append([
            nombre_club, 
            datos_club["POBLACIÓN"], 
            datos_club["WEB"], 
            datos_club["E-MAIL"], 
            datos_club["PISTA"], # Y aquí también para leer el dato correctamente
            datos_club["DIRECCIÓN PISTA"],
            ahora
        ])

print("4. Escribiendo el directorio en tu Excel...")
hoja.clear()
hoja.update(datos_a_guardar, 'A1')

print("¡ÉXITO TOTAL! Directorio de clubes creado a la perfección.")
