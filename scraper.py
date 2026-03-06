import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)
hoja = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Resultados_FMP")

print("2. Leyendo el Diccionario de Equipos...")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_fmp = {}
for fila in datos_dicc[1:]: # Ignoramos la cabecera
    if len(fila) >= 3:
        fmp = fila[0].strip().upper()
        if fmp:
            # Guardamos el pack de 3 nombres
            diccionario_fmp[fmp] = {
                "oficial": fila[0].strip(),
                "coloquial": fila[1].strip(),
                "abrev": fila[2].strip()
            }

categorias = {
    "4186": "JUNIOR",
    "4202": "SUB-17 FEM",
    "4187": "1ª AUT. MASC",
    "4198": "1ª AUT. FEM"
}

# ⚠️ NUEVAS CABECERAS (Ahora incluimos Logo Local y Logo Visitante)
datos_a_guardar = [["Categoría", "Jornada", "Fecha", "Hora", "Local Oficial", "Local Coloquial", "Local Abrev.", "Logo Local", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Logo Visitante", "Resultado", "Última Actualización"]]

print("3. Extrayendo calendarios, logos y unificando nombres...")
for liga_id, nombre_cat in categorias.items():
    url_secreta = f"https://www.server2.sidgad.es/fmp/fmp_cal_idc_{liga_id}_1.php"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Origin': 'http://www.hockeypatines.fmp.es',
        'Referer': f'http://www.hockeypatines.fmp.es/league/{liga_id}',
        'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
    }
    payload = {'idc': liga_id, 'site_lang': 'es'}
    
    respuesta = requests.post(url_secreta, headers=headers, data=payload)
    soup = BeautifulSoup(respuesta.text, 'html.parser')
    
    tabla = soup.find('table', id='my_calendar_table')
    if not tabla: continue
        
    jornada_actual = "Desconocida"
    
    for elemento in tabla.find_all(['thead', 'tbody']):
        if elemento.name == 'thead' and 'head_jornada' in elemento.get('class', []):
            jornada_actual = elemento.text.strip()
            
        elif elemento.name == 'tbody':
            partidos = elemento.find_all('tr', class_='team_class')
            for partido in partidos:
                if partido.get('gamedate') == '00000000': continue
                    
                columnas = partido.find_all('td')
                if len(columnas) > 12:
                    fecha = columnas[1].text.strip()
                    if "00/00/0000" in fecha: continue
                        
                    hora = columnas[2].text.strip()
