# =======================================================
# FASE 5: LA MAGIA DEL DESPERTADOR DINÁMICO (-60 MINUTOS)
# =======================================================
print("5. Calculando horarios del Vigilante para HOY...")
zona_madrid = pytz.timezone('Europe/Madrid')
hoy = datetime.now(zona_madrid)
hoy_str = hoy.strftime("%d/%m/%Y")

horas_objetivo = set()
CATEGORIAS_OBJETIVO = ["JUVENIL", "JUNIOR", "SUB-17 FEM", "1ª MASCULINA", "1ª AUT. MASC", "1ª AUTONÓMICA MASCULINA", "1ª AUTONOMICA MASCULINA"]
PALABRAS_EQUIPO_OBJETIVO = ["ROZAS", "ROZ"]

for fila in datos_a_guardar[1:]:
    cat = fila[0].upper()
    fecha = fila[2]
    hora = fila[3]
    loc_col = fila[5].upper()
    vis_col = fila[9].upper()
    abrev_loc = fila[6].upper()
    abrev_vis = fila[10].upper()

    if fecha == hoy_str and hora:
        juega_rozas = any(p in loc_col or p in vis_col or p == abrev_loc or p == abrev_vis for p in PALABRAS_EQUIPO_OBJETIVO)
        es_categoria = any(c in cat for c in CATEGORIAS_OBJETIVO)
        
        if juega_rozas and es_categoria:
            horas_objetivo.add(hora)

crons_generados = []
for h in horas_objetivo:
    try:
        hora_dt = datetime.strptime(f"{hoy_str} {h}", "%d/%m/%Y %H:%M")
        hora_dt = zona_madrid.localize(hora_dt)
        # --- EL TRUCO: LE RESTAMOS 60 MINUTOS ---
        hora_inicio = hora_dt - timedelta(minutes=60)
        hora_utc = hora_inicio.astimezone(pytz.utc)
        cron_str = f"    - cron: '{hora_utc.minute} {hora_utc.hour} {hora_utc.day} {hora_utc.month} *'\n"
        crons_generados.append(cron_str)
    except Exception:
        pass

if not crons_generados:
    print("   -> Hoy no hay partidos de nuestras categorías objetivo que vigilar. Desactivando el Vigilante.")
    crons_generados.append("    - cron: '0 0 31 2 *'\n")

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
            continue 
        elif en_schedule and not linea.strip().startswith("- cron:"):
            en_schedule = False
            nuevas_lineas.append(linea)
        else:
            nuevas_lineas.append(linea)

    with open(ruta_yml, 'w', encoding='utf-8') as f:
        f.writelines(nuevas_lineas)
    print("¡Alarmas reconfiguradas con éxito (con 1h de antelación)!")
else:
    print(f"⚠️ No se encontró el archivo {ruta_yml} para actualizar las alarmas.")
