"""
Monitor de citas - Ministerio de Ciencia, Innovación y Universidades.

Flujo:
  1. Abre https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/
  2. El panel "SELECCIONAR SUCURSAL" ya está abierto por defecto.
     Selecciona "Oficina asistencia telefónica" (radio button).
  3. El panel "SELECCIONAR SERVICIO" se abre automáticamente.
     Selecciona "Asistencia reconocimiento títulos".
  4. El panel "SELECCIONAR FECHA Y HORA" muestra:
       - Banner verde "no hay citas disponibles" -> silencio.
       - Calendario / horas -> avisa por Telegram.
"""

import asyncio
import os
import sys
from datetime import datetime

import requests
from playwright.async_api import async_playwright

# ── Configuración ─────────────────────────────────────────────────────────────
URL_CITA = "https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/"

# Texto exacto que sale cuando NO hay citas (en el banner verde)
TEXTO_NO_HAY_CITAS = "zzzzzzzzzzz"

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")


def log(msg: str) -> None:
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


# ── Telegram ──────────────────────────────────────────────────────────────────
def enviar_telegram(texto: str) -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        log("⚠ TELEGRAM_TOKEN o TELEGRAM_CHAT_ID no configurados en secrets")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        r = requests.post(
            url,
            data={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": texto,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if r.status_code == 200:
            log("✅ Telegram: mensaje enviado")
        else:
            log(f"⚠ Telegram error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"⚠ Error al enviar Telegram: {e}")


def enviar_telegram_foto(ruta: str, caption: str = "") -> None:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
        with open(ruta, "rb") as f:
            r = requests.post(
                url,
                data={
                    "chat_id": TELEGRAM_CHAT_ID,
                    "caption": caption,
                    "parse_mode": "HTML",
                },
                files={"photo": f},
                timeout=20,
            )
        if r.status_code == 200:
            log("✅ Telegram: foto enviada")
    except Exception as e:
        log(f"⚠ Error al enviar foto: {e}")


# ── Selector helpers ──────────────────────────────────────────────────────────
async def click_opcion_robusto(page, texto_busqueda: str, etiqueta: str) -> bool:
    """
    Intenta clicar una opción (radio button) que contenga texto_busqueda.
    Prueba selectores típicos de Angular Material y devuelve True si clica.
    """
    selectores = [
        f"mat-radio-button:has-text('{texto_busqueda}')",
        f"[role='radio']:has-text('{texto_busqueda}')",
        f"label:has-text('{texto_busqueda}')",
        f".mat-radio-button:has-text('{texto_busqueda}')",
        f".mat-radio-label:has-text('{texto_busqueda}')",
        f"text={texto_busqueda}",
        f"div:has(input[type='radio']):has-text('{texto_busqueda}')",
        f"li:has-text('{texto_busqueda}')",
    ]

    for selector in selectores:
        try:
            el = page.locator(selector).first
            count = await el.count()
            if count > 0:
                log(f"    → Encontrado con: {selector}")
                await el.scroll_into_view_if_needed(timeout=3000)
                await el.click(timeout=5000)
                log(f"  ✓ {etiqueta} seleccionado")
                return True
        except Exception as e:
            log(f"    ✗ Selector '{selector[:60]}' falló: {str(e)[:80]}")
            continue

    return False


async def guardar_html_debug(page, nombre: str) -> None:
    """Guarda el HTML actual para diagnóstico."""
    try:
        html = await page.content()
        with open(nombre, "w", encoding="utf-8") as f:
            f.write(html)
        log(f"  📄 HTML guardado en {nombre} ({len(html)} bytes)")
    except Exception as e:
        log(f"  ⚠ No se pudo guardar HTML: {e}")


# ── Comprobación ──────────────────────────────────────────────────────────────
async def comprobar() -> str:
    """
    Devuelve:
      "sin_citas"  -> banner verde presente
      "hay_citas"  -> banner ausente, posible calendario
      "error"      -> algo falló
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1400, "height": 900},
            locale="es-ES",
        )
        page = await context.new_page()

        try:
            # ── Paso 1: abrir la página ──
            log("→ Paso 1: abriendo página...")
            await page.goto(URL_CITA, wait_until="networkidle", timeout=45000)
            await page.wait_for_timeout(5000)
            await page.screenshot(path="paso1_inicio.png", full_page=True)
            log(f"  URL final: {page.url}")

            # ── Paso 2: esperar opciones de sucursal (panel ya abierto) ──
            log("→ Paso 2: esperando opciones de sucursal...")
            try:
                await page.wait_for_selector(
                    "text=/Oficina.{0,5}asistencia/i", timeout=20000
                )
                log("  ✓ Las opciones de sucursal son visibles")
            except Exception as e:
                log(f"  ⚠ No aparecieron las opciones: {e}")
                await guardar_html_debug(page, "debug_paso2.html")
                await page.screenshot(path="paso2_fallo.png", full_page=True)
                raise

            await page.screenshot(path="paso2_opciones_sucursal.png", full_page=True)

            # ── Paso 3: clic en "Oficina asistencia telefónica" ──
            log("→ Paso 3: clicando en 'Oficina asistencia telefónica'...")
            ok = await click_opcion_robusto(
                page, "Oficina asistencia telefónica", "Sucursal"
            )
            if not ok:
                log("  → Intentando con JavaScript directo...")
                try:
                    clicked = await page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('*');
                            for (const el of els) {
                                if (el.children.length === 0 &&
                                    el.textContent &&
                                    el.textContent.includes('Oficina asistencia telef')) {
                                    let target = el;
                                    while (target &&
                                           target.tagName !== 'MAT-RADIO-BUTTON' &&
                                           target.tagName !== 'LABEL') {
                                        target = target.parentElement;
                                    }
                                    if (target) { target.click(); return true; }
                                    el.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    if clicked:
                        log("  ✓ Clic con JS ejecutado")
                        ok = True
                except Exception as e:
                    log(f"  ✗ JS también falló: {e}")

            if not ok:
                await guardar_html_debug(page, "debug_paso3.html")
                raise Exception("No se pudo seleccionar la sucursal")

            await page.wait_for_timeout(4000)
            await page.screenshot(path="paso3_sucursal_elegida.png", full_page=True)

            # ── Paso 4: esperar opciones de servicio ──
            log("→ Paso 4: esperando opciones de servicio...")
            try:
                await page.wait_for_selector(
                    "text=/Asistencia.{0,5}reconocimiento/i", timeout=15000
                )
                log("  ✓ Las opciones de servicio son visibles")
            except Exception:
                log("  → Servicio no visible, intentando abrir panel 2...")
                try:
                    cabecera = page.locator(
                        "text=/SELECCIONAR\\s*SERVICIO/i"
                    ).first
                    await cabecera.click(timeout=8000)
                    await page.wait_for_timeout(3000)
                    await page.wait_for_selector(
                        "text=/Asistencia.{0,5}reconocimiento/i", timeout=10000
                    )
                    log("  ✓ Panel de servicio abierto manualmente")
                except Exception as e:
                    log(f"  ⚠ No se encontró el servicio: {e}")
                    await guardar_html_debug(page, "debug_paso4.html")
                    raise

            await page.screenshot(path="paso4_opciones_servicio.png", full_page=True)

            # ── Paso 5: clic en "Asistencia reconocimiento títulos" ──
            log("→ Paso 5: clicando en 'Asistencia reconocimiento títulos'...")
            ok = await click_opcion_robusto(
                page, "Asistencia reconocimiento títulos", "Servicio"
            )
            if not ok:
                log("  → Intentando con JavaScript directo...")
                try:
                    clicked = await page.evaluate("""
                        () => {
                            const els = document.querySelectorAll('*');
                            for (const el of els) {
                                if (el.children.length === 0 &&
                                    el.textContent &&
                                    el.textContent.includes('reconocimiento')) {
                                    let target = el;
                                    while (target &&
                                           target.tagName !== 'MAT-RADIO-BUTTON' &&
                                           target.tagName !== 'LABEL') {
                                        target = target.parentElement;
                                    }
                                    if (target) { target.click(); return true; }
                                    el.click();
                                    return true;
                                }
                            }
                            return false;
                        }
                    """)
                    if clicked:
                        ok = True
                except Exception as e:
                    log(f"  ✗ JS también falló: {e}")

            if not ok:
                await guardar_html_debug(page, "debug_paso5.html")
                raise Exception("No se pudo seleccionar el servicio")

            # ── Paso 6: esperar al bloque 3 ──
            log("→ Paso 6: esperando bloque 'FECHA Y HORA'...")
            await page.wait_for_timeout(6000)
            await page.screenshot(path="paso6_estado_final.png", full_page=True)

            # ── Paso 7: decidir si hay citas ──
            log("→ Paso 7: analizando contenido...")
            contenido = (await page.content()).lower()

            if TEXTO_NO_HAY_CITAS in contenido:
                log("  ℹ Banner verde detectado: NO hay citas")
                await browser.close()
                return "sin_citas"
            else:
                log("  🚨 Banner 'no hay citas' AUSENTE -> posibles citas")
                await page.screenshot(path="hay_citas.png", full_page=True)
                await browser.close()
                return "hay_citas"

        except Exception as e:
            log(f"⚠ Error: {e}")
            try:
                await page.screenshot(path="error.png", full_page=True)
            except Exception:
                pass
            await browser.close()
            return "error"


# ── Main ──────────────────────────────────────────────────────────────────────
async def main():
    log("🔍 Iniciando monitor de citas (Ministerio Ciencia)")
    resultado = await comprobar()
    log(f"📊 Resultado: {resultado}")

    if resultado == "hay_citas":
        mensaje = (
            "🔬🚨 <b>¡POSIBLE CITA EN CIENCIA!</b>\n\n"
            "Trámite: <b>Asistencia reconocimiento títulos</b>\n"
            "Oficina: <b>Oficina asistencia telefónica</b>\n\n"
            "El banner de 'no hay citas' ha desaparecido.\n"
            "Entra YA en:\n"
            f"{URL_CITA}\n\n"
            "⚡ <i>Reserva rápido, las citas vuelan.</i>"
        )
        enviar_telegram(mensaje)
        if os.path.exists("hay_citas.png"):
            enviar_telegram_foto("hay_citas.png", "📸 Estado actual de la web")
    elif resultado == "error":
        log("ℹ Error registrado (no se envía Telegram para evitar spam)")
        sys.exit(1)
    else:
        log("✓ Todo normal. Sin citas disponibles.")


if __name__ == "__main__":
    asyncio.run(main())
