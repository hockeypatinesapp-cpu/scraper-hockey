import os
import json
import gspread
import requests
import pytz
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
for fila in datos_dicc[1:]: 
    if len(fila) >= 3:
        fmp = fila[0].strip().upper()
        if fmp:
            diccionario_fmp[fmp] = {"oficial": fila[0].strip(), "coloquial": fila[1].strip(), "abrev": fila[2].strip()}

categorias = {"4186": "JUNIOR", "4202": "SUB-17 FEM", "4187": "1ª AUT. MASC", "4198": "1ª AUT. FEM"}

datos_a_guardar = [["Categoría", "Jornada", "Fecha", "Hora", "Local Oficial", "Local Coloquial", "Local Abrev.", "Logo Local", "Visitante Oficial", "Visitante Coloquial", "Visitante Abrev.", "Logo Visitante", "Resultado", "Última Actualización"]]

print("3. Extrayendo calendarios...")
for liga_id, nombre_cat in categorias.items():
    try:
        url_secreta = f"https://www.server2.sidgad.es/fmp/fmp_cal_idc_{liga_id}_1.php"
        headers = {'User-Agent': 'Mozilla/5.0', 'Origin': 'http://www.hockeypatines.fmp.es', 'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'}
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
                for partido in elemento.find_all('tr', class_='team_class'):
                    if partido.get('gamedate') == '00000000': continue
                    columnas = partido.find_all('td')
                    if len(columnas) > 12:
                        fecha = columnas[1].text.strip()
                        if "00/00/0000" in fecha: continue
                        hora = columnas[2].text.strip()
                        
                        img_loc = columnas[5].find('img')
                        logo_loc = img_loc.get('src', '') if img_loc else ""
                        img_vis = columnas[7].find('img')
                        logo_vis = img_vis.get('src', '') if img_vis else ""
                        
                        local_fmp = columnas[6].text.strip()
                        visitante_fmp = columnas[8].text.strip()
                        resultado = columnas[11].text.strip()
                        ahora = (datetime.utcnow() + timedelta(hours=1)).strftime("%d/%m/%Y %H:%M:%S")
                        
                        if local_fmp and visitante_fmp:
                            datos_loc = diccionario_fmp.get(local_fmp.upper(), {"oficial": local_fmp, "coloquial": local_fmp, "abrev": local_fmp})
                            datos_vis = diccionario_fmp.get(visitante_fmp.upper(), {"oficial": visitante_fmp, "coloquial": visitante_fmp, "abrev": visitante_fmp})
                            
                            datos_a_guardar.append([nombre_cat, jornada_actual, fecha, hora, datos_loc["oficial"], datos_loc["coloquial"], datos_loc["abrev"], logo_loc, datos_vis["oficial"], datos_vis["coloquial"], datos_vis["abrev"], logo_vis, resultado, ahora])
    except Exception as e:
        pass

print("4. Actualizando base de datos central...")
try:
    hoja.clear()
    hoja.update(values=datos_a_guardar, range_name='A1', value_input_option='USER_ENTERED')
except TypeError:
    hoja.update('A1', datos_a_guardar, value_input_option='USER_ENTERED')


# =======================================================
# FASE 5: LA MAGIA DEL DESPERTADOR DINÁMICO (-1 MINUTO)
# =======================================================
print("5. Calculando horarios del Vigilante para HOY...")
zona_madrid = pytz.timezone('Europe/Madrid')
hoy = datetime.now(zona_madrid)
hoy_str = hoy.strftime("%d/%m/%Y")

horas_objetivo = set()
CATEGORIAS_OBJETIVO = ["JUNIOR", "SUB-17 FEM", "1ª AUT. MASC"]
PALABRA_EQUIPO_OBJETIVO = "ROZAS"

for fila in datos_a_guardar[1:]:
    cat = fila[0].upper()
    fecha = fila[2]
    hora = fila[3]
    loc_col = fila[5].upper()
    vis_col = fila[9].upper()

    if fecha == hoy_str and hora:
        if cat in CATEGORIAS_OBJETIVO or PALABRA_EQUIPO_OBJETIVO in loc_col or PALABRA_EQUIPO_OBJETIVO in vis_col:
            horas_objetivo.add(hora)

crons_generados = []
for h in horas_objetivo:
    try:
        # Fusionamos la fecha de hoy con la hora del partido
        hora_dt = datetime.strptime(f"{hoy_str} {h}", "%d/%m/%Y %H:%M")
        hora_dt = zona_madrid.localize(hora_dt)
        
        # Le restamos exactamente 1 minuto al reloj
        hora_inicio = hora_dt - timedelta(minutes=1)
        
        # Lo pasamos a hora UTC para que GitHub lo entienda perfectamente
        hora_utc = hora_inicio.astimezone(pytz.utc)
        
        # Creamos la línea de código para GitHub Actions
        cron_str = f"    - cron: '{hora_utc.minute} {hora_utc.hour} {hora_utc.day} {hora_utc.month} *'\n"
        crons_generados.append(cron_str)
    except Exception:
        pass

if not crons_generados:
    print("   -> Hoy no hay partidos que vigilar. Desactivando el Vigilante.")
    crons_generados.append("    - cron: '0 0 31 2 *'\n") # Fecha imposible (31 de febrero) para apagarlo

# Escribir la nueva alarma en el archivo vigilante.yml
ruta_yml = ".github/workflows/vigilante.yml"
if os.path.exists(ruta_yml):
    with open(ruta_yml, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    nuevas_lineas = []
    en_schedule = False
    for linea in lineas:
        if linea.strip() == "schedule:":
            nuevas_lineas.append(linea)
            nuevas_lineas.extend(crons_generados)
            en_schedule = True
        elif en_schedule and linea.strip().startswith("- cron:"):
            continue # Borramos las alarmas de ayer
        elif en_schedule and not linea.strip().startswith("- cron:"):
            en_schedule = False
            nuevas_lineas.append(linea)
        else:
            nuevas_lineas.append(linea)

    with open(ruta_yml, 'w', encoding='utf-8') as f:
        f.writelines(nuevas_lineas)
    print("¡Alarmas reconfiguradas con éxito!")
