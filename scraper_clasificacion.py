import os
import json
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)

# Conectamos con la nueva pestaña que acabas de crear
hoja_clasificacion = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Clasificacion_FMP")

print("2. Leyendo el Diccionario de Equipos...")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_fmp = {}
for fila in datos_dicc[1:]: 
    if len(fila) >= 3:
        fmp = fila[0].strip().upper()
        if fmp:
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

# Cabeceras: 1ª Columna Categoría, Última Timestamp
datos_a_guardar = [["Categoría", "Pos", "Logo", "Oficial", "Coloquial", "Abrev", "PT", "PJ", "PG", "PE", "PP", "GF", "GC", "Gav", "PEN", "Última Actualización"]]

print("3. Extrayendo las tablas de clasificación...")
for liga_id, nombre_cat in categorias.items():
    try:
        url_clasif = f"https://www.server2.sidgad.es/fmp/fmp_clasif_idc_{liga_id}_1.php"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Origin': 'http://www.hockeypatines.fmp.es',
            'Referer': f'http://www.hockeypatines.fmp.es/league/{liga_id}',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        payload = {'idc': liga_id, 'site_lang': 'es'}
        
        respuesta = requests.post(url_clasif, headers=headers, data=payload)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        tabla = soup.find('table', class_='tabla_clasif')
        if not tabla: continue
            
        filas = tabla.find('tbody').find_all('tr')
        ahora = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
        
        for fila in filas:
            columnas = fila.find_all('td')
            if len(columnas) >= 12:
                posicion = columnas[0].text.strip()
                
                img_tag = columnas[1].find('img')
                logo = img_tag.get('src', '') if img_tag else ""
                
                div_nombre = columnas[2].find('div', class_='no_mobile')
                equipo_web = div_nombre.text.strip() if div_nombre else columnas[2].text.strip()
                
                # --- FILTRO ANTIFANTASMAS ---
                if not equipo_web or "DESCANSO" in equipo_web.upper(): 
                    continue
                    
                datos_equipo = diccionario_fmp.get(equipo_web.upper(), {"oficial": equipo_web, "coloquial": equipo_web, "abrev": equipo_web})
                
                pt = columnas[3].text.strip()
                pj = columnas[4].text.strip()
                pg = columnas[5].text.strip()
                pe = columnas[6].text.strip()
                pp = columnas[7].text.strip()
                gf = columnas[8].text.strip()
                gc = columnas[9].text.strip()
                gav = columnas[10].text.strip()
                pen = columnas[11].text.strip()
                
                datos_a_guardar.append([
                    nombre_cat, posicion, logo, 
                    datos_equipo["oficial"], datos_equipo["coloquial"], datos_equipo["abrev"], 
                    pt, pj, pg, pe, pp, gf, gc, gav, pen, ahora
                ])
                
    except Exception as e:
        print(f"      ❌ Error aislado procesando la liga {nombre_cat}: {e}")

print("4. Guardando las clasificaciones en Google Sheets...")
try:
    hoja_clasificacion.clear()
    hoja_clasificacion.update(values=datos_a_guardar, range_name='A1', value_input_option='USER_ENTERED')
    print("¡CLASIFICACIONES ACTUALIZADAS CON ÉXITO!")
except TypeError:
    hoja_clasificacion.update('A1', datos_a_guardar, value_input_option='USER_ENTERED')
    print("¡CLASIFICACIONES ACTUALIZADAS (Modo Clásico)!")
