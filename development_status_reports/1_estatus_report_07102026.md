# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS
**Fecha de Generación:** 7 de Octubre de 2026 (Sesión de Refinamiento Post-Etapa 4)  
**Rama:** `development`  
**Último Commit Base:** `c81f485` (*feat(v2.0-etapa4): destajos, raya semanal, telemetria clima open-meteo, dashboard tri-modal y pruebas e2e completas*)  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito de este Documento

Este reporte documenta exhaustivamente todos los cambios implementados en la base de código entre el commit `c81f485` y el estado de trabajo actual. Está diseñado como un **manual de transferencia de contexto operativo** para futuras instancias del agente y para el equipo de desarrollo. 

Explica no solo *qué* cambió, sino *por qué* cambió, el *criterio de diseño*, la *arquitectura de las soluciones* y, fundamentalmente, la **metodología de pruebas rigurosas E2E (Playwright + Chromium)** con la que hemos estado garantizando la estabilidad absoluta de Estimapp.

---

## 2. Resumen General del Diff (vs. `c81f485`)

Un total de **7 módulos** fueron refinados e integrados (+847 líneas agregadas, -314 modificadas):

| Módulo | Líneas Modificadas | Naturaleza del Cambio |
| :--- | :---: | :--- |
| `modulos/dashboard_engine.py` | +403 / -140 | Gráfica de dona Altair/Vega, Opción A (cero simulación), nivelación milimétrica (0px de diferencia) y paridad Flexbox. |
| `modulos/db_engine.py` | +25 / -7 | `ttl=60` en `@st.cache_data` para sincronización en tiempo real; utilerías multi-archivo `extraer_nombres_archivos`. |
| `modulos/mediciones_engine.py` | +53 / -21 | Soporte de multi-evidencias fotográficas y croquis (`accept_multiple_files=True`), URLs compuestas y borrado atómico en Storage. |
| `modulos/excel_engine.py` | +58 / -18 | Inyección iterativa de múltiples fotos y croquis en hojas de evidencia para formatos IMSS, PJF y Estimapp. |
| `modulos/pdf_engine.py` | +423 / -48 | Múltiples evidencias en reportes, gráficas Matplotlib adaptativas tri-modales y generador de recibos de raya oficial en PDF. |
| `modulos/estimaciones_engine.py` | +38 / -16 | Integración de descarga de Recibo de Raya en PDF oficial y saneamiento en cascada de evidencias al eliminar estimaciones. |
| `modulos/proyectos_engine.py` | +161 / -48 | Geolocalización contextual por IP del usuario (`obtener_geolocalizacion_ip`) con sesgo viewbox en Nominatim y fallback global. |

---

## 3. Detalle Técnico de las Mejoras Implementadas

### A. Dashboard Financiero Adaptativo y Paridad Geométrica (`dashboard_engine.py`)

#### 1. Transición a Gráfica de Dona Interactiva (Altair / Vega-Lite)
- **Problema previo:** El desglose de costos utilizaba barras horizontales genéricas y posteriormente una gráfica de dona con fallos de renderizado en Streamlit debido a formateadores numéricos incompatibles en Vega (`format=".1f%"` no soportado directamente sobre cuantitativos en tooltip).
- **Solución implementada:** Se diseñó `_crear_grafica_dona(df_dist)` utilizando `alt.Chart(df_dist).mark_arc(innerRadius=65, outerRadius=115)` con:
  - Paleta cromática corporativa distinguida: Materiales (`#2563EB`), Mano de Obra (`#0D9488`), Herramienta (`#F59E0B`), Indirectos (`#64748B`), Utilidad (`#10B981`).
  - Campo pre-formateado `Participacion:N` y tooltip robusto con `format="$",.2f"` en los importes.

#### 2. Implementación de la "Opción A" (Estricta y Transparente)
- **Contexto:** En proyectos reales de clientes (ej. *INSTALACIÓN Y RETIRO DE PENDONES 2026* de Ingrid), el catálogo de conceptos puede haberse capturado sin desglose analítico de APUs (costos unitarios directos en `$0.00`) y sin trabajadores asignados en las mediciones de campo. El sistema previamente ejecutaba una simulación paramétrica proporcional que generaba confusión al inventar costos no declarados.
- **Solución implementada:** Si `suma_analitica_erogada <= 0` y no hay destajistas en campo:
  - No se simulan montos artificiales.
  - Las métricas operativas se presentan con total transparencia en `$0.00` y `0.0%`.
  - La gráfica de dona se oculta limpiamente y en su lugar se renderiza un aviso informativo amigable:
    > 💡 **Este proyecto no cuenta con desglose analítico (APUs) en su catálogo ni destajistas asignados en campo.**  
    > *Registra estos costos para ver la distribución real.*
  - La tabla de leyenda derecha muestra todos los rubros en `$0.00` con `0.0%`.

#### 3. Nivelación Milimétrica de Alturas en Modo Mixta (Paridad de Bordes Inferiores)
- **Problema:** En el modo de columnas paralelas (`col_pub, col_priv = st.columns(2)`), el contenedor izquierdo (*🏛️ Control Contractual Oficial*) cuenta con un badge delta en *Saldo por Ejercer* (`^ 0.00`), una barra de progreso nativa (`st.progress`) y su banner verde de estado (`🟢 Avance contractual al 100%`). Esto causaba que el contenedor derecho (*📈 Control Operativo y Rentabilidad*) fuera visiblemente más corto, dejando su borde inferior desalineado por ~17 píxeles.
- **Solución CSS & Geométrica:**
  - Se corrigieron los selectores CSS de paridad (`display: flex; flex-direction: column; height: 100%`), reemplazando selectores de hijo directo (`>`) por selectores descendientes compatibles con el DOM anidado de Streamlit:
    ```css
    [data-testid="column"]:has([data-testid="stVerticalBlockBorderWrapper"]) > [data-testid="stVerticalBlock"],
    [data-testid="column"]:has([data-testid="stVerticalBlockBorderWrapper"]) [data-testid="stElementContainer"]:has([data-testid="stVerticalBlockBorderWrapper"]) {
        display: flex !important;
        flex-direction: column !important;
        flex: 1 1 auto !important;
        height: 100% !important;
    }
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] {
        flex: 1 1 auto !important;
        display: flex !important;
        flex-direction: column !important;
        height: 100% !important;
    }
    [data-testid="column"] [data-testid="stVerticalBlockBorderWrapper"] > [data-testid="stVerticalBlock"] {
        flex: 1 1 auto !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        height: 100% !important;
    }
    ```
  - Se calibró dinámicamente el espaciador vertical interno (`espacio_comp = 39 if (gasto_erogado_real > 0 or utilidad_bruta_real > 0) else 59`).
  - **Resultado verificado por análisis de píxeles:** Borde inferior izquierdo: `y = 756px`, borde inferior derecho: `y = 756px`. **Diferencia: 0px (Alineación 100% perfecta).**
  - Se preservaron las dos barras de estado verdes intactas al pie de ambos contenedores.

---

### B. Multi-Evidencias Fotográficas y Croquis (`mediciones_engine.py`, `excel_engine.py`, `pdf_engine.py`, `db_engine.py`)

- **Subida múltiple:** `st.file_uploader` ahora incluye `accept_multiple_files=True` tanto para fotos en campo como para croquis.
- **Almacenamiento compatible:** Las URLs públicas de Supabase Storage se concatenan mediante cadenas separadas por coma (ej. `url1,url2`).
- **Exportadores:**
  - `excel_engine.py`: Las plantillas IMSS, PJF y Estimapp iteran sobre cada URL individual insertando todas las fotografías y croquis secuencialmente en las hojas de evidencias.
  - `pdf_engine.py`: Se adapta dinámicamente para insertar múltiples imágenes en el anexo fotográfico del reporte ejecutivo.
- **Borrado Atómico y Sanitización:** Se implementó `extraer_nombres_archivos()` en `db_engine.py`. Al eliminar una medición o estimación, el sistema elimina todos los archivos asociados del bucket `evidencias` en Supabase Storage sin dejar archivos huérfanos.

---

### C. Liquidación de Raya Semanal Oficial en PDF (`estimaciones_engine.py`, `pdf_engine.py`)

- En la Tab de Estimaciones, se sustituyó la exportación rudimentaria en archivo de texto plano (`.txt`) por un recibo formal generado con **ReportLab** (`generar_pdf_recibo_raya()`).
- Incluye membrete con datos de obra, contratista, periodo de corte, tabla detallada de jornales y destajos por trabajador, importe neto a pagar y sección de firmas de conformidad (*Recibí Conforme* y *Autorizó Residencia*).

---

### D. Geolocalización Contextual con Sesgo por IP (`proyectos_engine.py`)

- Se implementó `obtener_geolocalizacion_ip()` con caché de 1 hora (`ttl=3600`) y timeout defensivo estricto (<2.5s) consultando `http://ip-api.com/json/`.
- `resolver_geocodificacion_nominatim()` utiliza el código de país detectado (`countrycodes`) y un cuadrante `viewbox` de ±2.5° alrededor de las coordenadas de IP del usuario para priorizar direcciones locales (ej. Colima, CDMX, Guadalajara) al teclear referencias como "Av. Constitución".
- Cuenta con fallback global automático si la búsqueda contextual no arroja resultados.

---

### E. Invalidación Inteligente de Caché (`db_engine.py`)

- Se agregó `ttl=60` a todas las funciones decoradas con `@st.cache_data`:
  - `get_proyectos`, `get_conceptos`, `get_estimaciones`, `get_mediciones`, `get_biblioteca_conceptos`, `get_biblioteca_instituciones`.
- **Impacto:** Las operaciones de creación, edición o borrado en la base de datos se reflejan automáticamente en la interfaz en menos de un minuto (o inmediatamente al recargar la sesión), eliminando la necesidad de reiniciar el proceso de Streamlit.

---

## 4. Filosofía y Protocolo de Testing Agéntico (Playwright + Chromium)

### ¿Cómo trabajamos en este proyecto?
Para cualquier agente que continúe el trabajo en Estimapp: **aquí no se asume nada sin validación visual y estructural en vivo**. El desarrollo de interfaces reactivas en Streamlit presenta peculiaridades (reruns de sesión, rerenderizado de componentes, jerarquías DOM complejas). Por ello, el estándar de trabajo obligatorio incluye:

#### 1. Navegación Headless Automatizada con Playwright
- Todos los cambios de interfaz se validan ejecutando scripts en `scratch/` que levantan una sesión de Chromium headless contra `http://localhost:8501`.
- La terminal de trabajo es **Git Bash** (entorno POSIX/Bash en Windows). NUNCA ejecutar sintaxis ni cmdlets de PowerShell (`Get-Content`, `Select-String`, etc.). Ejecutar scripts mediante `venv/Scripts/python.exe scratch/<script>.py` o `bash -c "source venv/Scripts/activate && python ..."`.

#### 2. Inspección Real del DOM vs. Selectores Hipotéticos
- Streamlit envuelve los widgets en múltiples capas (`stElementContainer`, `stVerticalBlock`, `stVerticalBlockBorderWrapper`).
- Antes de inyectar CSS, inspeccionar siempre la jerarquía real con `page.evaluate()` en Playwright para garantizar que los selectores hagan match exacto.

#### 3. Verificación Analítica de Píxeles (Python PIL)
- Para comprobar alineación visual, no basta con mirar una miniatura: tomamos capturas de pantalla de página completa (`page.screenshot()`) y las procesamos con Python PIL / NumPy para medir las coordenadas `y` exactas de bordes, banners y márgenes.
- Así es como certificamos que la diferencia entre los contenedores izquierdo y derecho se redujo de **17px** a **0px exactos**.

#### 4. Reglas Críticas de Aislamiento y Seguridad (Inviolables)
- **Credenciales de prueba:** Usar exclusivamente las credenciales de `test_user` configuradas en `.streamlit/secrets.toml` (usuario David).
- **Proyectos de prueba aislados:** Todo registro generado para pruebas DEBE usar el prefijo `TEST_` (ej. `TEST_PARIDAD_OBRA`, `TEST_PROY_MIXTO`).
- **Limpieza (Teardown):** El script de prueba debe implementar un bloque `finally:` o función `cleanup()` que elimine los registros creados sin dejar huérfanos.
- **Protección de datos reales:** **NUNCA modificar, sobreescribir contraseñas ni borrar proyectos o datos de clientes reales** (ej. usuario Ingrid o usuario Pablo). Row Level Security (RLS) protege la separación multiusuario, pero el agente debe ser estrictamente respetuoso de los datos existentes.

---

## 5. Estado de Salud del Proyecto al Cierre de esta Sesión

1. **Servidor Streamlit:** En ejecución estable y continua (`streamlit run app.py` en puerto 8501 sin crashes).
2. **Excepciones de Runtime:** `0` errores rojos (`.stException`).
3. **Consola y Logs:** Limpios. No hay advertencias de Vega-Lite ni errores de PostgREST.
4. **Base de Datos Supabase:** Tablas e índices íntegros; todas las entidades de prueba temporales fueron purgadas.
5. **Dashboard:** Funcional en sus tres modalidades (`publica`, `privada`, `mixta`), con la gráfica de dona interactiva, manejo de proyectos sin APU conforme a la Opción A, y nivelación geométrica perfecta de contenedores.

---
*Fin del reporte de estatus. Cualquier duda o siguiente paso puede ser consultado directamente con el desarrollador o revisando las especificaciones en `especificaciones.md` y `AGENTS.md`.*
