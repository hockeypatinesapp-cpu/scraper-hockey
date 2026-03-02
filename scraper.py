import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Resultados_FMP")

print("2. Atacando la puerta trasera del servidor Sidgad...")
# Aquí puedes cambiar el número de la liga cuando quieras (4186 = Junior, 4202 = Sub17)
liga_id = "4186" 

url_secreta = f"https://www.server2.sidgad.es/fmp/fmp_cal_idc_{liga_id}_1.php"

# Nos disfrazamos de su propia página web
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Origin': 'http://www.hockeypatines.fmp.es',
    'Referer': f'http://www.hockeypatines.fmp.es/league/{liga_id}',
    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
}

# Los parámetros mágicos que descubriste en la pestaña Payload
payload = {
    'idc': liga_id,
    'site_lang': 'es'
}

# Hacemos la llamada secreta
respuesta = requests.post(url_secreta, headers=headers, data=payload)
print(f"   - [DIAGNÓSTICO] Código de respuesta: {respuesta.status_code}")

# El servidor nos devuelve directamente el código HTML de la tabla
soup = BeautifulSoup(respuesta.text, 'html.parser')
partidos = soup.find_all('tr', class_='team_class')

datos_a_guardar = [["Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado"]] 

print(f"3. ¡BINGO! Se han encontrado {len(partidos)} partidos. Extrayendo goles...")
if len(partidos) > 0:
    for partido in partidos:
        columnas = partido.find_all('td')
        if len(columnas) > 12:
            fecha = columnas[1].text.strip()
            hora = columnas[2].text.strip()
            local = columnas[6].text.strip()
            visitante = columnas[8].text.strip()
            resultado = columnas[11].text.strip()
            
            # Evitar filas raras o vacías
            if local and visitante:
                datos_a_guardar.append([fecha, hora, local, visitante, resultado])

    print("4. Escribiendo en tu Excel...")
    hoja.clear() 
    hoja.update(datos_a_guardar, 'A1') 
    print(f"¡ÉXITO TOTAL! {len(datos_a_guardar)-1} partidos guardados a las {datetime.now()}.")
else:
    print("❌ ERROR: No se encontraron partidos.")
