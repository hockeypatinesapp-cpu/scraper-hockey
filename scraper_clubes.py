import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")

print("2. Leyendo la web del directorio de clubes...")
url = "https://www.fmp.es/clubes-de-hockey-sobre-patines/"
headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

respuesta = requests.get(url, headers=headers)
soup = BeautifulSoup(respuesta.text, 'html.parser')

clubes_html = soup.find_all('h3')
datos_escrapeados = {}

print(f"3. ¡Encontrados {len(clubes_html)} clubes! Extrayendo datos...")
ahora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

for h3 in clubes_html:
    nombre_club = h3.text.strip()
    tabla = h3.find_next_sibling('table')
    
    if tabla:
        datos_club = {"POBLACIÓN": "", "WEB": "", "E-MAIL": "", "PISTA": "", "DIRECCIÓN PISTA": ""}
        filas = tabla.find_all('tr')
        for fila in filas:
            th = fila.find('th')
            td = fila.find('td')
            if th and td:
                clave = th.text.strip().upper()
                if clave in datos_club:
                    datos_club[clave] = td.text.strip()
                    
        # Guardamos el club usando su nombre en MAYÚSCULAS como llave maestra
        datos_escrapeados[nombre_club.upper()] = datos_club

print("4. Cruzando datos con tu Diccionario_Equipos...")
datos_actuales = hoja.get_all_values()

if not datos_actuales:
    print("❌ ERROR: La pestaña Diccionario_Equipos está vacía.")
    exit()

cabeceras = datos_actuales[0]

# Buscamos en qué columna está el "Nombre oficial" automáticamente
idx_nombre_oficial = -1
for i, col in enumerate(cabeceras):
    if "NOMBRE OFICIAL" in col.upper():
        idx_nombre_oficial = i
        break

if idx_nombre_oficial == -1:
    print("❌ ERROR: No se encontró la columna 'Nombre oficial' en el Diccionario.")
    exit()

# Nos aseguramos de que las cabeceras extra existan en tu Excel, si no, las creamos
nuevas_columnas = ["Población", "Web", "E-mail", "Pista", "Dirección Pista", "Última Actualización"]
for col in nuevas_columnas:
    if col not in cabeceras:
        cabeceras.append(col)

datos_a_guardar = [cabeceras]

# Recorremos tus equipos uno a uno para rellenar los huecos
for fila in datos_actuales[1:]:
    # Si la fila es más corta que las cabeceras, la rellenamos con espacios en blanco
    while len(fila) < len(cabeceras):
        fila.append("")
        
    if len(fila) > idx_nombre_oficial:
        nombre_oficial_fila = fila[idx_nombre_oficial].strip()
        
        # Comparamos ignorando mayúsculas y minúsculas
        match = datos_escrapeados.get(nombre_oficial_fila.upper())
        
        if match:
            fila[cabeceras.index("Población")] = match["POBLACIÓN"]
            fila[cabeceras.index("Web")] = match["WEB"]
            fila[cabeceras.index("E-mail")] = match["E-MAIL"]
            fila[cabeceras.index("Pista")] = match["PISTA"]
            fila[cabeceras.index("Dirección Pista")] = match["DIRECCIÓN PISTA"]
            fila[cabeceras.index("Última Actualización")] = ahora

    datos_a_guardar.append(fila)

print("5. Escribiendo el diccionario enriquecido en tu Excel...")
hoja.clear()
hoja.update(datos_a_guardar, 'A1')

print("¡ÉXITO TOTAL! Directorio integrado a la perfección.")
