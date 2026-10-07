# ESTIMAPP v2.0 - Matriz de Pruebas E2E y Checklist de Validación (Playwright / Chromium)

Este documento define el protocolo de control de calidad y pruebas automatizadas de extremo a extremo (E2E) con **Playwright y Chromium** para el agente en **Antigravity**. Cumple estrictamente con las reglas de **`AGENTS.md`**, garantizando que ninguna funcionalidad de la versión 1.0 sufra regresiones y que las nuevas capacidades de la versión 2.0 se validen exhaustivamente.

---

## 1. Reglas de Aislamiento y Configuración de Pruebas

1. **Entorno de Ejecución:**
   * Terminal: Git Bash.
   * Entorno Virtual: `source venv/Scripts/activate`
   * Comando de servidor: `streamlit run app.py`
2. **Nomenclatura de Datos:**
   * Toda entidad creada durante las pruebas debe usar el prefijo obligatorio `TEST_` (ej. `TEST_PROYECTO_PRIVADO`, `TEST_DESTAJISTA_1`, `TEST_PROVEEDOR_ACEROS`).
3. **Credenciales:**
   * Utilizar exclusivamente las credenciales de prueba en `.streamlit/secrets.toml` (`[test_user]`).

---

## 2. Checklist de Verificación por Módulos y Pestañas

### Bloque A: Base de Datos, Relaciones y RLS (Etapa 1)
- [x] **A.1 Migración DDL en Supabase:**
  - [x] Verificar que `public.proyectos` contiene las 14 columnas nuevas de modalidad, factores de costo y geodatos.
  - [x] Verificar que existen las tablas `public.proveedores`, `public.personal_obra`, `public.insumos_concepto`, `public.hitos_cobro` y `public.telemetria_clima`.
  - [x] Confirmar que la columna `importe` en `public.insumos_concepto` sea de tipo `STORED GENERATED` y rechace inserciones manuales directas.
- [x] **A.2 Políticas RLS:**
  - [x] Un usuario B no puede leer ni modificar proveedores ni personal creados por el usuario A (`auth.uid() = user_id`).
  - [x] Acceso a insumos, hitos y clima restringido a los proyectos propiedad del usuario activo.
- [x] **A.3 Vista Feature Store:**
  - [x] Ejecutar `SELECT * FROM public.v_telemetria_rendimientos_ml LIMIT 5;` y verificar que las columnas de features y targets calculados se resuelven sin errores de sintaxis.

---

### Bloque B: Directorios y Proyectos (Etapa 2 - Tab 6, Tab 7 y Tab 8)
- [x] **B.1 Tab 6 - Personal y Cuadrillas (`modulos/personal_engine.py`):**
  - [x] Alta de trabajador: `TEST_JUAN_ALBANIL`, especialidad `Albañilería`, jornal base `$550.00`.
  - [x] Edición interactiva: Modificar tarifa directamente en celda de `st.data_editor` y comprobar persistencia.
  - [x] Verificación de limpieza: El formulario se limpia tras el registro exitoso mediante `counter_key += 1`.
- [x] **B.2 Tab 7 - Proveedores (`modulos/proveedores_engine.py`):**
  - [x] Alta de proveedor: `TEST_FERRETERA_CENTRAL`, giro `Materiales`, teléfono `3120000000`.
  - [x] Búsqueda y filtrado: El buscador filtra registros correctamente sin recargas anómalas de la página.
- [x] **B.3 Tab 8 - Proyectos y Georreferenciación (`modulos/proyectos_engine.py`):**
  - [x] Crear proyecto con modalidad `privada`, `% Indirectos = 12%`, `% Utilidad = 18%`.
  - [x] **Prueba de Geocodificación Nominatim:**
    - [x] Introducir dirección en campo de búsqueda y hacer clic en `st.button("🔍 Buscar Dirección")`.
    - [x] Verificar que `latitud`, `longitud`, `estado` y `municipio` se autocompletan.
    - [x] **Edge case / Fallback:** Simular fallo de red o dirección inválida; comprobar que la app muestra advertencia suave (`st.warning`) y permite guardar el proyecto sin coordenadas.

---

### Bloque C: Catálogo y Biblioteca - Dual Path (Etapa 3 - Tab 4 y Tab 5)
- [x] **C.1 Tab 5 - Biblioteca Maestra (`modulos/biblioteca_engine.py`):**
  - [x] Alta con Precio Unitario Cerrado (Camino 1): Concepto estándar sin desglose.
  - [x] Alta con Desglose Analítico (Camino 2): Ingresar Material ($120), MdeO ($80), Herramienta ($10), Indirectos ($15). Verificar que calcula P.U. Referencial ($225).
- [x] **C.2 Tab 4 - Catálogo del Proyecto (`modulos/catalogo_engine.py`):**
  - [x] Alta con factor de utilidad: Comprobar que hereda el `% Utilidad` del proyecto pero permite sobreescribirlo por partida.
  - [x] **Importador Excel:**
    - [x] Subir archivo Excel tradicional v1.0 (solo columnas de clave, descripción, unidad, cantidad, precio). Comprobar que importa perfectamente.
    - [x] Subir archivo Excel v2.0 (con columnas adicionales de desglose). Comprobar que lee los costos desglosados y la utilidad.
  - [x] **Normalización de Unidades:** Comprobar que entradas como `M2`, `m2`, `M²` se normalizan a `m²` vía `normalizar_unidad()`.

---

### Bloque D: Destajos, Periodos Libres y Dashboard (Etapa 4 - Tab 2, Tab 3 y Tab 1)
- [x] **D.1 Tab 2 - Captura en Campo (`modulos/mediciones_engine.py`):**
  - [x] Captura de generador geométrico sin destajista (Opción: *"Sin asignar"*). Comprobar compatibilidad con v1.0.
  - [x] Captura asignando a `TEST_JUAN_ALBANIL` con `1.5 jornales`. Comprobar almacenamiento en `mediciones_campo`.
- [x] **D.2 Tab 3 - Estimaciones y Raya (`modulos/estimaciones_engine.py`):**
  - [x] **Periodo Libre (N días):** Abrir estimación con fecha de inicio lunes y fin jueves (4 días). Verificar que no fuerza semanas fijas.
  - [x] **Resumen de Liquidación de Raya:**
    - [x] Verificar que agrupa las mediciones asignadas a `TEST_JUAN_ALBANIL` dentro de las fechas del corte.
    - [x] Comprobar el cálculo de importe a pagar (`Jornales × Costo Base`).
    - [x] Verificar la generación o vista previa del recibo de raya.
  - [x] **Telemetría Climática Silenciosa (Open-Meteo):**
    - [x] Al guardar la estimación en un proyecto georreferenciado, verificar inserción en `public.telemetria_clima`.
    - [x] **Edge case:** Guardar estimación en proyecto sin coordenadas. Comprobar que no lanza excepciones ni interrumpe el flujo.
- [x] **D.3 Tab 1 - Resumen Financiero Adaptativo (`modulos/dashboard_engine.py`):**
  - [x] Cambiar a un proyecto `publica`: Verifica que se visualizan tarjetas contractuales de avance oficial.
  - [x] Cambiar a un proyecto `privada`: Verifica que se visualizan tarjetas de costo erogado real, margen bruto y gráfica de distribución.
  - [x] Cambiar a un proyecto `mixta`: Verifica la coexistencia de ambos bloques en columnas paralelas.

---

### Bloque E: Integridad de Borrado y Purga (Tear Down)
- [x] **E.1 Borrado Defensivo de Personal (`SET NULL`):**
  - [x] Eliminar al trabajador `TEST_JUAN_ALBANIL`.
  - [x] Inspeccionar `public.mediciones_campo`: La medición generada previamente debe conservar su `cantidad_total`, `largo`, `ancho` e historial, con `id_personal = NULL`.
- [x] **E.2 Borrado en Cascada de Proyecto (`CASCADE`):**
  - [x] Eliminar `TEST_PROYECTO_PRIVADO`.
  - [x] Verificar que sus conceptos, estimaciones, mediciones, hitos y telemetría se borraron automáticamente.
  - [x] Verificar que `TEST_FERRETERA_CENTRAL` (proveedor) sigue existiendo intacto en la base de datos.
- [x] **E.3 Consola de Purga Segura:**
  - [x] Probar la opción de vaciado seguro en `admin_engine.py` escribiendo un texto diferente a `"CONFIRMAR"` (debe abortar la acción).
  - [x] Escribir `"CONFIRMAR"` y comprobar que ejecuta la purga de registros de prueba sin romper la sesión.

---

## 3. Guía de Ejecución de Pruebas Automatizadas con Playwright

Ejecutar la suite de pruebas E2E desde Git Bash:

```bash
# 1. Activar entorno virtual
source venv/Scripts/activate

# 2. Ejecutar suite de pruebas de regresión v1.0
pytest tests/e2e/test_v1_regression.py --browser chromium --headed

# 3. Ejecutar suite de validación de nuevas capacidades v2.0
pytest tests/e2e/test_v2_features.py --browser chromium

# 4. Generar reporte de cobertura y evidencias
pytest tests/e2e/ --html=reporte_pruebas_v2.html --self-contained-html
```
