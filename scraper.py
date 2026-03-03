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

# Aquí tienes el "diccionario" maestro. Puedes añadir más ligas en el futuro siguiendo este formato.
categorias = {
    "4186": "JUNIOR",
    "4202": "SUB-17 FEM",
    "4187": "1ª AUT. MASC",
    "4198": "1ª AUT. FEM"
}

# Las nuevas cabeceras de tu Excel
datos_a_guardar = [["Categoría", "Jornada", "Fecha", "Hora", "Equipo Local", "Equipo Visitante", "Resultado", "Última Actualización"]]

print("2. Iniciando el escaneo masivo de categorías...")

for liga_id, nombre_cat in categorias.items():
    print(f"   -> Escaneando: {nombre_cat} (ID: {liga_id})")
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
    
    # Buscamos la tabla completa
    tabla = soup.find('table', id='my_calendar_table')
    if not tabla:
        continue
        
    jornada_actual = "Desconocida"
    
    # Leemos la tabla en orden de arriba a abajo para saber en qué jornada estamos
    for elemento in tabla.find_all(['thead', 'tbody']):
        
        # Si vemos una cabecera de jornada, guardamos su nombre (Ej: "JORNADA 1")
        if elemento.name == 'thead' and 'head_jornada' in elemento.get('class', []):
            jornada_actual = elemento.text.strip()
            
        # Si vemos el cuerpo de la tabla, sacamos los partidos y les ponemos la jornada actual
        elif elemento.name == 'tbody':
            partidos = elemento.find_all('tr', class_='team_class')
            
            for partido in partidos:
                # 1er Filtro: Ignorar gamedate="00000000"
                if partido.get('gamedate') == '00000000':
                    continue
                    
                columnas = partido.find_all('td')
                if len(columnas) > 12:
                    fecha = columnas[1].text.strip()
                    # 2do Filtro: Ignorar fecha de texto "00/00/0000" por si acaso
                    if "00/00/0000" in fecha:
                        continue
                        
                    hora = columnas[2].text.strip()
                    local = columnas[6].text.strip()
                    visitante = columnas[8].text.strip()
                    resultado = columnas[11].text.strip()
                    
                    # Generamos la hora actual (Ajuste UTC+1 aprox para España)
                    ahora = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
                    
                    # Guardamos toda la fila si tiene datos válidos
                    if local and visitante:
                        datos_a_guardar.append([nombre_cat, jornada_actual, fecha, hora, local, visitante, resultado, ahora])

print(f"3. ¡Misión cumplida! Se van a guardar {len(datos_a_guardar)-1} partidos en total.")
print("4. Escribiendo en tu Excel...")
hoja.clear()
hoja.update(datos_a_guardar, 'A1')
print("¡Base de datos centralizada con éxito!")
