"""
Monitor de citas - Ministerio de Ciencia, Innovación y Universidades.

Flujo:
  1. Abre https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/
  2. Despliega "SELECCIONAR SUCURSAL" y elige "Oficina asistencia telefónica"
  3. Despliega "SELECCIONAR SERVICIO" y elige "Asistencia reconocimiento títulos"
  4. Lee el bloque "SELECCIONAR FECHA Y HORA":
       - Si aparece el banner verde "no hay citas disponibles" -> silencio.
       - Si NO aparece ese banner -> hay calendario -> avisa por Telegram.
"""

import asyncio
import os
import sys
from datetime import datetime

import requests
from playwright.async_api import async_playwright

# ── Configuración ─────────────────────────────────────────────────────────────
URL_CITA = "https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/"

SUCURSAL = "Oficina asistencia telefónica"
SERVICIO = "Asistencia reconocimiento títulos"

# Texto exacto que sale cuando NO hay citas (en el banner verde)
TEXTO_NO_HAY_CITAS = "no hay citas disponibles"

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
        data = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": texto,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        }
        r = requests.post(url, data=data, timeout=15)
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
        else:
            log(f"⚠ Telegram foto error {r.status_code}: {r.text}")
    except Exception as e:
        log(f"⚠ Error al enviar foto: {e}")


# ── Comprobación ──────────────────────────────────────────────────────────────
async def comprobar() -> str:
    """
    Devuelve uno de estos valores:
      "sin_citas"        -> el banner verde aparece, todo normal
      "hay_citas"        -> banner ausente, posible calendario => avisar
      "error"            -> algo falló (avisar como precaución)
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
            # ── Paso 1: abrir la página ──────────────────────────────────────
            log("→ Paso 1: abriendo página de cita previa...")
            await page.goto(URL_CITA, wait_until="networkidle", timeout=45000)
            await page.wait_for_timeout(3000)
            await page.screenshot(path="paso1_inicio.png", full_page=True)
            log(f"  URL: {page.url}")

            # ── Paso 2: desplegar bloque "SELECCIONAR SUCURSAL" ──────────────
            log("→ Paso 2: desplegando 'SELECCIONAR SUCURSAL'...")
            try:
                # Click en la cabecera del acordeón
                cabecera_sucursal = page.locator(
                    "text=/SELECCIONAR\\s*SUCURSAL/i"
                ).first
                await cabecera_sucursal.click(timeout=15000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                log(f"  ℹ No hizo falta clic explícito en sucursal: {e}")

            # ── Paso 3: elegir "Oficina asistencia telefónica" ───────────────
            log(f"→ Paso 3: eligiendo sucursal '{SUCURSAL}'...")
            clicado = False
            for selector in [
                f"label:has-text('{SUCURSAL}')",
                f"text='{SUCURSAL}'",
                "text=/Oficina\\s*asistencia\\s*telef/i",
                "text=/Oficina\\s*virtual/i",
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        await el.click(timeout=8000)
                        clicado = True
                        log(f"  ✓ Sucursal seleccionada (selector: {selector})")
                        break
                except Exception:
                    continue

            if not clicado:
                raise Exception("No se pudo seleccionar la sucursal")

            await page.wait_for_timeout(3000)
            await page.screenshot(path="paso3_sucursal.png", full_page=True)

            # ── Paso 4: desplegar "SELECCIONAR SERVICIO" si hace falta ───────
            log("→ Paso 4: desplegando 'SELECCIONAR SERVICIO' si está cerrado...")
            try:
                # Buscamos si el servicio ya está visible; si no, clicamos cabecera
                servicio_visible = await page.locator(
                    f"text=/{SERVICIO}/i"
                ).count()
                if servicio_visible == 0:
                    cabecera_servicio = page.locator(
                        "text=/SELECCIONAR\\s*SERVICIO/i"
                    ).first
                    await cabecera_servicio.click(timeout=10000)
                    await page.wait_for_timeout(2000)
            except Exception as e:
                log(f"  ℹ Cabecera servicio: {e}")

            # ── Paso 5: elegir "Asistencia reconocimiento títulos" ───────────
            log(f"→ Paso 5: eligiendo servicio '{SERVICIO}'...")
            clicado = False
            for selector in [
                f"label:has-text('{SERVICIO}')",
                f"text='{SERVICIO}'",
                "text=/Asistencia\\s*reconocimiento\\s*t.tulos/i",
            ]:
                try:
                    el = page.locator(selector).first
                    if await el.count() > 0:
                        await el.click(timeout=8000)
                        clicado = True
                        log(f"  ✓ Servicio seleccionado (selector: {selector})")
                        break
                except Exception:
                    continue

            if not clicado:
                raise Exception("No se pudo seleccionar el servicio")

            # Esperar a que el bloque 3 cargue su contenido
            await page.wait_for_timeout(5000)
            await page.screenshot(path="paso5_servicio.png", full_page=True)

            # ── Paso 6: desplegar "SELECCIONAR FECHA Y HORA" si hace falta ───
            log("→ Paso 6: comprobando bloque 'SELECCIONAR FECHA Y HORA'...")
            try:
                cabecera_fecha = page.locator(
                    "text=/SELECCIONAR\\s*FECHA\\s*Y\\s*HORA/i"
                ).first
                # Intentar abrirlo (si ya está abierto, no pasa nada)
                await cabecera_fecha.click(timeout=5000)
                await page.wait_for_timeout(3000)
            except Exception:
                pass

            await page.screenshot(path="paso6_fecha.png", full_page=True)

            # ── Paso 7: leer el contenido y decidir ──────────────────────────
            log("→ Paso 7: analizando si hay citas...")
            contenido = (await page.content()).lower()

            if TEXTO_NO_HAY_CITAS in contenido:
                log("  ℹ Banner verde detectado: NO hay citas")
                await browser.close()
                return "sin_citas"
            else:
                log("  🚨 Banner verde NO detectado: POSIBLE calendario")
                # Capturamos solo el bloque 3 para enviar a Telegram si podemos
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
            f"Trámite: <b>{SERVICIO}</b>\n"
            f"Oficina: <b>{SUCURSAL}</b>\n\n"
            "El banner de 'no hay citas' ha desaparecido.\n"
            "Entra YA en:\n"
            f"{URL_CITA}\n\n"
            "⚡ <i>Las citas vuelan, reserva rápido.</i>"
        )
        enviar_telegram(mensaje)
        if os.path.exists("hay_citas.png"):
            enviar_telegram_foto("hay_citas.png", "📸 Estado actual de la web")

    elif resultado == "error":
        # Solo avisamos por error si fue algo grave. Para evitar spam,
        # comentamos esta línea por defecto. Descoméntala si quieres avisos
        # también cuando falle el script.
        # enviar_telegram("⚠ Error en el bot de citas de Ciencia. Revisa los logs.")
        log("ℹ Error registrado (no se envía Telegram para evitar spam)")
        sys.exit(1)

    else:  # sin_citas
        log("✓ Todo normal. Sin citas disponibles. Hasta la próxima.")


if __name__ == "__main__":
    asyncio.run(main())
