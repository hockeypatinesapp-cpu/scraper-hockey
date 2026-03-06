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

# ⚠️ NUEVAS CABECERAS (Ahora tenemos 3 columnas por equipo)
datos_a_guardar = [["Categoría", "Jornada", "Fecha", "Hora", "Local Oficial", "Local Coloquial", "Local Abrev.", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Resultado", "Última Actualización"]]

print("3. Extrayendo calendarios y unificando nombres...")
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
                    local_fmp = columnas[6].text.strip()
                    visitante_fmp = columnas[8].text.strip()
                    resultado = columnas[11].text.strip()
                    ahora = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
                    
                    if local_fmp and visitante_fmp:
                        # Buscamos en el diccionario. Si es un equipo nuevo que aún no está, repetimos el nombre base.
                        datos_loc = diccionario_fmp.get(local_fmp.upper(), {"oficial": local_fmp, "coloquial": local_fmp, "abrev": local_fmp})
                        datos_vis = diccionario_fmp.get(visitante_fmp.upper(), {"oficial": visitante_fmp, "coloquial": visitante_fmp, "abrev": visitante_fmp})
                        
                        datos_a_guardar.append([
                            nombre_cat, jornada_actual, fecha, hora, 
                            datos_loc["oficial"], datos_loc["coloquial"], datos_loc["abrev"],
                            datos_vis["oficial"], datos_vis["coloquial"], datos_vis["abrev"],
                            resultado, ahora
                        ])

print("4. Actualizando base de datos central...")
hoja.clear()
hoja.update(datos_a_guardar, 'A1')
print(f"¡SISTEMA COMPLETADO! Excel actualizado.")
