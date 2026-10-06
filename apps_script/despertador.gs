/**
 * ═══════════════════════════════════════════════════════════════════════
 *  DESPERTADOR DE LOS ROBOTS (Google Apps Script, dentro de la hoja)
 * ═══════════════════════════════════════════════════════════════════════
 *  GitHub lanza las tareas programadas con horas de retraso, pero las que
 *  se piden "a mano" (workflow_dispatch) arrancan en segundos. Este script
 *  se ejecuta cada 5 minutos y es quien da la orden de arrancar:
 *
 *   1. Robots diarios: a partir de DESP_HORA_DIARIA lanza Calendario + Plantillas
 *      (una vez al día; el día 1 de cada mes, Plantillas en modo COMPLETA).
 *   2. Vigilante en vivo: si un partido de Las Rozas de tus categorías
 *      (columna A de Categorias_FMP) empieza en menos de DESP_MINUTOS_ANTES,
 *      o está en juego, y el Vigilante no está ya funcionando, lo lanza.
 *
 *  Requisito: propiedad del script GH_TOKEN con una llave de GitHub
 *  (Configuración del proyecto → Propiedades del script).
 *  Instalación: ejecutar una vez la función  instalarDespertador
 *  (todos los nombres empiezan por desp/DESP para no chocar con tus otros scripts)
 * ═══════════════════════════════════════════════════════════════════════
 */

const DESP_REPO = 'hockeypatinesapp-cpu/scraper-hockey';
const DESP_ZONA = 'Europe/Madrid';
const DESP_HORA_DIARIA = 6;          // 06:00 Madrid
const DESP_MINUTOS_ANTES = 65;       // el Vigilante acepta hasta 90 min antes
const DESP_MINUTOS_DESPUES = 150;    // margen máximo de duración de un partido
const DESP_ESPERA_MIN = 12; // min: evita lanzar dos veces seguidas
const DESP_PALABRAS_EQUIPO = ['ROZAS', 'ROZ'];
const DESP_HOJA_LOG = 'Despertador_Log';

// ─────────────────────────────────────────────────────────────────────────
//  FUNCIONES QUE PUEDES EJECUTAR TÚ (menú desplegable de arriba → Ejecutar)
// ─────────────────────────────────────────────────────────────────────────

/** Instala (o reinstala) la ejecución automática cada 5 minutos. */
function instalarDespertador() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'despertarRobots')
    .forEach(t => ScriptApp.deleteTrigger(t));
  ScriptApp.newTrigger('despertarRobots').timeBased().everyMinutes(5).create();
  despComprobarLlave_();
  despLog_('✅ Despertador instalado: se ejecutará cada 5 minutos.');
}

/** Quita la ejecución automática. */
function desinstalarDespertador() {
  ScriptApp.getProjectTriggers()
    .filter(t => t.getHandlerFunction() === 'despertarRobots')
    .forEach(t => ScriptApp.deleteTrigger(t));
  despLog_('⏹️ Despertador desinstalado.');
}

/** Muestra qué partidos vigilaría, sin lanzar nada. */
function simularDespertador() {
  const partidos = despPartidos_();
  if (!partidos.length) { despLog_('🔎 No hay partidos de Las Rozas próximos en tus categorías.'); return; }
  partidos.slice(0, 10).forEach(p => despLog_(
    `🔎 ${p.cat} · ${p.texto} · empieza ${despFmt_(p.inicio)} · el Vigilante se lanzaría a partir de ${despFmt_(new Date(p.inicio.getTime() - DESP_MINUTOS_ANTES * 60000))}`
  ));
}

// ─────────────────────────────────────────────────────────────────────────
//  EJECUCIÓN AUTOMÁTICA (cada 5 minutos)
// ─────────────────────────────────────────────────────────────────────────

function despertarRobots() {
  const lock = LockService.getScriptLock();
  if (!lock.tryLock(10000)) return;
  try {
    despRobotsDiarios_();
    despVigilante_();
  } catch (e) {
    despLog_('❌ Error: ' + e.message);
  } finally {
    lock.releaseLock();
  }
}

function despRobotsDiarios_() {
  const props = PropertiesService.getScriptProperties();
  const ahora = new Date();
  const hoy = Utilities.formatDate(ahora, DESP_ZONA, 'yyyy-MM-dd');
  const hora = Number(Utilities.formatDate(ahora, DESP_ZONA, 'H'));
  if (hora < DESP_HORA_DIARIA || props.getProperty('ULTIMO_DIARIO') === hoy) return;

  const diaMes = Utilities.formatDate(ahora, DESP_ZONA, 'd');
  const tipo = diaMes === '1' ? 'COMPLETA' : 'LIGERA';
  const ok1 = despLanzar_('bot.yml', {});
  const ok2 = despLanzar_('plantillas.yml', { tipo: tipo });
  if (ok1 && ok2) {
    props.setProperty('ULTIMO_DIARIO', hoy);
    despLog_(`🌅 Robots diarios lanzados (Calendario + Plantillas ${tipo}).`);
  }
}

function despVigilante_() {
  const ahora = Date.now();
  const enVentana = despPartidos_().filter(p =>
    ahora >= p.inicio.getTime() - DESP_MINUTOS_ANTES * 60000 &&
    ahora <= p.inicio.getTime() + DESP_MINUTOS_DESPUES * 60000
  );
  if (!enVentana.length) return;

  const props = PropertiesService.getScriptProperties();
  const ultimo = Number(props.getProperty('ULTIMO_VIGILANTE') || 0);
  if (ahora - ultimo < DESP_ESPERA_MIN * 60000) return;
  if (despVigilanteActivo_()) return;

  if (despLanzar_('vigilante.yml', {})) {
    props.setProperty('ULTIMO_VIGILANTE', String(ahora));
    despLog_('📡 Vigilante lanzado para: ' + enVentana.map(p => `${p.cat} ${p.texto} (${despFmt_(p.inicio)})`).join(' | '));
  }
}

// ─────────────────────────────────────────────────────────────────────────
//  LECTURA DE LA HOJA
// ─────────────────────────────────────────────────────────────────────────

/** Partidos de Las Rozas, de tus categorías, con fecha y hora, sin resultado todavía. */
function despPartidos_() {
  const libro = SpreadsheetApp.getActive();
  const categorias = libro.getSheetByName('Categorias_FMP').getDataRange().getDisplayValues()
    .slice(1).map(f => String(f[0]).trim().toUpperCase()).filter(Boolean);

  const filas = libro.getSheetByName('Resultados_FMP').getDataRange().getDisplayValues().slice(1);
  const ahora = Date.now();
  const out = [];
  filas.forEach(f => {
    const cat = String(f[0]).trim().toUpperCase();
    const fecha = String(f[3]).trim(), hora = String(f[4]).trim();
    const locCol = String(f[6]).toUpperCase(), visCol = String(f[10]).toUpperCase();
    const locAb = String(f[7]).trim().toUpperCase(), visAb = String(f[11]).trim().toUpperCase();
    const resultado = String(f[13]).trim();
    if (!fecha || !/^\d{1,2}:\d{2}/.test(hora)) return;
    if (/\d+\s*[-:]\s*\d+/.test(resultado)) return;               // ya terminado
    if (!categorias.some(c => cat.indexOf(c) >= 0)) return;
    const juegaRozas = DESP_PALABRAS_EQUIPO.some(p =>
      locCol.indexOf(p) >= 0 || visCol.indexOf(p) >= 0 || locAb === p || visAb === p);
    if (!juegaRozas) return;
    let inicio;
    try { inicio = Utilities.parseDate(`${fecha} ${hora.slice(0, 5)}`, DESP_ZONA, 'd/M/yyyy HH:mm'); }
    catch (e) { return; }
    if (inicio.getTime() + DESP_MINUTOS_DESPUES * 60000 < ahora) return; // ya pasado
    out.push({ cat: f[0], inicio: inicio, texto: `${f[7] || f[6]} vs ${f[11] || f[10]}` });
  });
  return out.sort((a, b) => a.inicio - b.inicio);
}

// ─────────────────────────────────────────────────────────────────────────
//  GITHUB
// ─────────────────────────────────────────────────────────────────────────

function despToken_() {
  const t = PropertiesService.getScriptProperties().getProperty('GH_TOKEN');
  if (!t) throw new Error('Falta la propiedad del script GH_TOKEN (Configuración del proyecto → Propiedades del script).');
  return t.trim();
}

function despGithub_(metodo, ruta, cuerpo) {
  const opciones = {
    method: metodo,
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + despToken_(),
      Accept: 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
    },
  };
  if (cuerpo) { opciones.contentType = 'application/json'; opciones.payload = JSON.stringify(cuerpo); }
  return UrlFetchApp.fetch('https://api.github.com/repos/' + DESP_REPO + ruta, opciones);
}

function despLanzar_(workflow, inputs) {
  const r = despGithub_('post', `/actions/workflows/${workflow}/dispatches`, { ref: 'main', inputs: inputs });
  if (r.getResponseCode() === 204) return true;
  despLog_(`❌ GitHub rechazó lanzar ${workflow}: ${r.getResponseCode()} ${r.getContentText().slice(0, 200)}`);
  return false;
}

function despVigilanteActivo_() {
  const r = despGithub_('get', '/actions/workflows/vigilante.yml/runs?per_page=5');
  if (r.getResponseCode() !== 200) return false;
  return JSON.parse(r.getContentText()).workflow_runs
    .some(run => ['queued', 'in_progress', 'waiting', 'requested', 'pending'].indexOf(run.status) >= 0);
}

function despComprobarLlave_() {
  const r = despGithub_('get', '');
  if (r.getResponseCode() !== 200) throw new Error('La llave GH_TOKEN no funciona (' + r.getResponseCode() + '). Revisa que la copiaste completa.');
  const permisos = JSON.parse(r.getContentText()).permissions || {};
  if (!permisos.push) throw new Error('La llave GH_TOKEN no tiene permiso para lanzar robots: créala marcando "repo".');
  despLog_('🔑 Llave de GitHub correcta.');
}

// ─────────────────────────────────────────────────────────────────────────
//  REGISTRO (pestaña Despertador_Log, últimas 200 líneas)
// ─────────────────────────────────────────────────────────────────────────

function despLog_(texto) {
  console.log(texto);
  try {
    const libro = SpreadsheetApp.getActive();
    const hoja = libro.getSheetByName(DESP_HOJA_LOG) || libro.insertSheet(DESP_HOJA_LOG);
    hoja.insertRowBefore(1);
    hoja.getRange(1, 1, 1, 2).setValues([[Utilities.formatDate(new Date(), DESP_ZONA, 'dd/MM/yyyy HH:mm:ss'), texto]]);
    if (hoja.getMaxRows() > 200) hoja.deleteRows(201, hoja.getMaxRows() - 200);
  } catch (e) { /* el registro nunca debe romper el despertador */ }
}

function despFmt_(d) { return Utilities.formatDate(d, DESP_ZONA, 'dd/MM HH:mm'); }
