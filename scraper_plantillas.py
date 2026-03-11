import os
import json
import time
import gspread
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

print("1. Conectando a tu Google Sheets...")
credenciales = json.loads(os.environ['CREDENTIALS_JSON'])
gc = gspread.service_account_from_dict(credenciales)

hoja_plantillas = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Plantillas_FMP")

print("2. Leyendo el Diccionario de Equipos (por Abreviatura)...")
hoja_diccionario = gc.open_by_key(os.environ['SHEET_ID']).worksheet("Diccionario_Equipos")
datos_dicc = hoja_diccionario.get_all_values()
diccionario_abrev = {}
for fila in datos_dicc[1:]: 
    if len(fila) >= 3:
        abrev = fila[2].strip().upper() # Ahora usamos la abreviatura como llave
        if abrev:
            diccionario_abrev[abrev] = {"oficial": fila[0].strip(), "coloquial": fila[1].strip(), "abrev": fila[2].strip()}

categorias = {
    "4186": "JUNIOR",
    "4202": "SUB-17 FEM",
    "4187": "1ª AUT. MASC",
    "4198": "1ª AUT. FEM"
}

# Cabeceras ampliadas con ID Equipo, Logo y Bandera
datos_a_guardar = [["Categoría", "Equipo Oficial", "Equipo Coloquial", "Equipo Abrev", "ID Equipo", "Logo Club", "Bandera", "Nombre Jugador", "ID Jugador", "Foto URL", "Goles", "PJ", "Media Goles", "Asistencias", "Media Asist", "Faltas Directas", "Media FD", "Penaltis", "Media Pen", "Azules", "Media Azules", "Rojas", "Media Rojas", "Última Actualización"]]

print("3. Extrayendo las estadísticas y fotos de los jugadores...")
for liga_id, nombre_cat in categorias.items():
    print(f" -> Procesando liga: {nombre_cat}...")
    try:
        url_stats = f"https://www.server2.sidgad.es/fmp/fmp_stats_1_{liga_id}.php"
        headers = {
            'User-Agent': 'Mozilla/5.0',
            'Origin': 'http://www.hockeypatines.fmp.es',
            'Referer': f'http://www.hockeypatines.fmp.es/league/{liga_id}',
            'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'
        }
        
        payload = {
            'idc': liga_id, 
            'tipo_stats': 'plantillas', 
            'site_lang': 'es'
        }
        
        respuesta = requests.post(url_stats, headers=headers, data=payload)
        soup = BeautifulSoup(respuesta.text, 'html.parser')
        
        filas_jugadores = soup.find_all('tr', class_='fila_stats_player')
        ahora = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
        
        for fila in filas_jugadores:
            columnas = fila.find_all('td')
            if len(columnas) < 15: continue
            
            # --- 1. DATOS DEL EQUIPO (Corregido) ---
            texto_equipo = columnas[1].text.strip().upper()
            datos_equipo = diccionario_abrev.get(texto_equipo, {"oficial": texto_equipo, "coloquial": texto_equipo, "abrev": texto_equipo})
            
            # --- 2. LOGO Y BANDERA ---
            img_logo = columnas[2].find('img')
            url_logo = img_logo.get('src', '') if img_logo else ""
            
            img_bandera = columnas[3].find('img')
            url_bandera = img_bandera.get('src', '') if img_bandera else ""
            
            # --- 3. DATOS BÁSICOS DEL JUGADOR ---
            enlace = fila.find('a', class_='nombre_ficha_jugador_plus')
            if not enlace: continue
            
            nombre = enlace.get('player_name', '').strip()
            id_jugador = enlace.get('id_player', '').strip()
            id_equipo = enlace.get('team_id', '').strip()
            
            # --- 4. EXTRACCIÓN DINÁMICA DE LA FOTO ---
            url_foto = ""
            if id_jugador and id_equipo:
                url_perfil = f"https://www.server2.sidgad.es/fmp/profiles/fmp_profileseason_{id_jugador}_1_39.php"
                payload_perfil = {
                    'idm': '1',
                    'idc': liga_id,
                    'id_player': id_jugador,
                    'team_id': id_equipo,
                    'temp_name': ''
                }
                
                try:
                    res_perfil = requests.post(url_perfil, headers=headers, data=payload_perfil)
                    soup_perfil = BeautifulSoup(res_perfil.text, 'html.parser')
                    div_foto = soup_perfil.find('div', class_='player_profile_picture')
                    
                    if div_foto and 'style' in div_foto.attrs:
                        estilo = div_foto['style']
                        if 'url(' in estilo:
                            parte_derecha = estilo.split('url(')[1]
                            url_sucia = parte_derecha.split(')')[0]
                            url_foto = url_sucia.strip("'\" ")
                except Exception as e:
                    pass
                
                time.sleep(0.5)
            
            # --- 5. ESTADÍSTICAS ---
            goles = columnas[5].text.strip()
            pj = columnas[6].text.strip()
            m_goles = columnas[7].text.strip()
            asist = columnas[8].text.strip()
            m_asist = columnas[9].text.strip()
            fd = columnas[10].text.strip()
            m_fd = columnas[11].text.strip()
            pen = columnas[12].text.strip()
            m_pen = columnas[13].text.strip()
            azul = columnas[14].text.strip()
            
            m_azul = columnas[15].text.strip() if len(columnas) > 15 else ""
            roja = columnas[16].text.strip() if len(columnas) > 16 else ""
            m_roja = columnas[17].text.strip() if len(columnas) > 17 else ""
            
            datos_a_guardar.append([
                nombre_cat, 
                datos_equipo["oficial"], datos_equipo["coloquial"], datos_equipo["abrev"], 
                id_equipo, url_logo, url_bandera,
                nombre, id_jugador, url_foto, 
                goles, pj, m_goles, asist, m_asist, fd, m_fd, pen, m_pen, azul, m_azul, roja, m_roja, 
                ahora
            ])
            
    except Exception as e:
        print(f"      ❌ Error aislado procesando la liga {nombre_cat}: {e}")

print("4. Guardando en Google Sheets...")
try:
    hoja_plantillas.clear()
    hoja_plantillas.update(values=datos_a_guardar, range_name='A1', value_input_option='USER_ENTERED')
    print("¡PLANTILLAS ACTUALIZADAS CON ÉXITO!")
except TypeError:
    hoja_plantillas.update('A1', datos_a_guardar, value_input_option='USER_ENTERED')
    print("¡PLANTILLAS ACTUALIZADAS (Modo Clásico)!")
