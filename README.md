# 🔬 Bot de citas - Ministerio de Ciencia, Innovación y Universidades

Vigila cada 5 minutos la web de cita previa del Ministerio:
- URL: https://citaprevia.ciencia.gob.es/qmaticwebbooking/#/
- Sucursal: **Oficina asistencia telefónica**
- Servicio: **Asistencia reconocimiento títulos**

Cuando aparecen citas disponibles, envía aviso por Telegram.

---

## 📊 Cómo funciona

```
GitHub Actions (cada 5 min)
        │
        ▼
   Abre navegador headless (Playwright)
        │
        ▼
   1. Entra en citaprevia.ciencia.gob.es
   2. Despliega "SELECCIONAR SUCURSAL"
   3. Clic "Oficina asistencia telefónica"
   4. Despliega "SELECCIONAR SERVICIO"
   5. Clic "Asistencia reconocimiento títulos"
   6. Lee bloque "SELECCIONAR FECHA Y HORA"
        │
   ┌────┴────┐
   │         │
"no hay   ¡HAY CITAS!
 citas"        │
   │           ▼
  Nada    📱 Telegram:
            - Aviso urgente
            - Captura de pantalla
```

---

## 🚀 Cómo desplegar (paso a paso)

### 1. Crear el repositorio en GitHub

```bash
cd citas-ciencia
git init
git add .
git commit -m "Initial commit: bot citas ciencia"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/citas-ciencia.git
git push -u origin main
```

### 2. Configurar los 2 Secrets en GitHub

Ve a tu repo → **Settings → Secrets and variables → Actions → New repository secret**:

| Nombre | Valor |
|---|---|
| `TELEGRAM_TOKEN` | El token largo que te dio @BotFather (formato `8621375446:AAH...`) |
| `TELEGRAM_CHAT_ID` | `611838379` |

⚠️ **Importante**: el token se pega directamente aquí, NUNCA en el código.

### 3. Activar Actions y probar

1. Pestaña **Actions** del repo → si te pide habilitar workflows, hazlo
2. Selecciona **"Monitor Citas Ciencia"** en la lista de la izquierda
3. Pulsa **"Run workflow"** → **"Run workflow"** (verde)
4. Espera ~1 minuto, recarga la página, y mira el resultado

Si todo va bien, el log mostrará:
```
🔍 Iniciando monitor de citas (Ministerio Ciencia)
→ Paso 1: abriendo página de cita previa...
→ Paso 2: desplegando 'SELECCIONAR SUCURSAL'...
→ Paso 3: eligiendo sucursal 'Oficina asistencia telefónica'...
  ✓ Sucursal seleccionada
→ Paso 4: desplegando 'SELECCIONAR SERVICIO'...
→ Paso 5: eligiendo servicio 'Asistencia reconocimiento títulos'...
  ✓ Servicio seleccionado
→ Paso 6: comprobando bloque 'SELECCIONAR FECHA Y HORA'...
→ Paso 7: analizando si hay citas...
  ℹ Banner verde detectado: NO hay citas
📊 Resultado: sin_citas
✓ Todo normal. Sin citas disponibles.
```

### 4. Una vez probado, ya corre solo

A partir de ahí GitHub Actions ejecutará el bot **cada 5 minutos automáticamente**.
Cuando aparezcan citas, recibirás el aviso por Telegram al instante.

---

## 🐛 Si algo falla

**El primer "Run workflow" falla:**

Ve a Actions → última ejecución → mira el log. En la parte inferior verás
"Artifacts" con las **capturas de pantalla** de cada paso. Descárgalas y
mira en cuál se quedó atascado el bot.

**Pasa el bot pero nunca avisa aunque tú veas citas:**

Es posible que el texto del banner verde haya cambiado. Edita en
`monitor_citas.py` la constante `TEXTO_NO_HAY_CITAS` para que coincida
con el nuevo texto exacto.

**Pasa el bot y avisa siempre aunque no haya citas:**

El bot no detecta el banner verde. Mira la captura de `paso6_fecha.png`
para ver qué texto aparece realmente y ajusta `TEXTO_NO_HAY_CITAS`.

---

## 🔧 Personalización

### Cambiar sucursal o servicio

Edita las constantes al inicio de `monitor_citas.py`:

```python
SUCURSAL = "MICIU"  # Para ir presencialmente en Madrid
SERVICIO = "Otro servicio del menú"
```

### Cambiar frecuencia

Edita `.github/workflows/monitor.yml`:

```yaml
- cron: "*/3 * * * *"   # cada 3 minutos
- cron: "*/10 * * * *"  # cada 10 minutos
```

---

## 💰 Coste

- **Repo público**: minutos de GitHub Actions **ilimitados gratis**
- **Repo privado**: 2000 minutos/mes gratis (con esta config consumes ~150/mes)
- **Telegram**: gratis
- **Playwright**: gratis
- **Servidores propios**: ninguno

Total: **0 €**.
