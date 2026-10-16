# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS (REPORTE #6)
**Fecha de Generación:** 16 de Octubre de 2026 (Auditoría Integral de Materiales y Proveedores, Regla Top 7 + Otros y Nivelación Milimétrica del Dashboard)  
**Rama:** `development`  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito y Resumen Ejecutivo

Este documento formaliza el cierre del hito de integración comercial y financiera entre el Catálogo de Conceptos, los Proveedores registrados y el Dashboard Adaptativo (Tab 1) en Estimapp:
1. **Llegada del Enfoque Comercial a Catálogo de Conceptos**:
   - Adición de la llave foránea `id_proveedor` en `public.catalogo_conceptos` en Supabase Cloud con regla de integridad `ON DELETE SET NULL`.
   - Modificación del flujo de alta manual y edición en línea atómica en el presupuesto mediante columna interactiva `st.column_config.SelectboxColumn("Proveedor Mat.")` en `st.data_editor`.
2. **Tercer Enfoque Analítico en el Dashboard Adaptativo (Tab 1)**:
   - Implementación de la perspectiva `"📦 Materiales: Desglose por Proveedor"`, coexistiendo armoniosamente con `"📊 General: Costos y Margen"` y `"👷 Mano de Obra: Trabajadores y Destajos"`.
   - Motor de agregación financiera y auditoría de volumen ejecutado en mediciones de campo vs costo directo de materiales (`costo_material`).
   - Implementación de la **Regla Top 7 + 8vo Consolidado** (`📦 Otros Proveedores (Consolidado)`), evitando saturación visual cuando existan decenas de proveedores.
   - Gráfica de dona interactiva en Vega-Lite con paleta cromática cobalt/indigo y leyenda flotante alineada milimétricamente (`x=305, y=8`).
   - Barra resumen inferior de 4 píldoras con tooltips flotantes BaseWeb SVG y `white-space: nowrap` estricto:
     `[🏢 Con Proveedor] [⚠️ Sin Asignar] [🏪 Comercios con Gasto] [📦 Total Materiales]`.
3. **Nivelación Milimétrica y Erradicación de Desplazamiento Vertical (CLS = 0)**:
   - Estandarización de `height=220` en los 3 `st.dataframe` de distribución.
   - Paridad geométrica perfecta:
     - `table_to_strip`: `24.0 px` en todas las vistas.
     - `strip_to_bottom`: `12.0 px` en todas las vistas.
     - Altura total del contenedor: `368 px` uniforme en todas las vistas.

---

## 2. Modificaciones al Modelo de Datos (PostgreSQL en Supabase Cloud)

### Tabla `catalogo_conceptos`
- **Columna Agregada**: `id_proveedor BIGINT REFERENCES public.proveedores(id) ON DELETE SET NULL`
- **Índice Agregado**: `CREATE INDEX idx_catalogo_conceptos_id_proveedor ON public.catalogo_conceptos(id_proveedor);`
- **Documentación**: Reflejado en diagrama relacional y diccionario de columnas en `data_model_v2.0.md`.

---

## 3. Desglose de Cambios por Módulo

### 🔹 `modulos/db_engine.py` y `modulos/proveedores_engine.py`
- Función con caché `get_proveedores(user_id)` con invalidación atómica (`st.cache_data.clear()`) ante inserción, edición o baja de proveedores.

### 🔹 `modulos/catalogo_engine.py`
- Mapeo bidireccional entre `id_proveedor` y el nombre comercial del proveedor para alimentar el selector del catálogo interactivo.
- Tooltip informativo en la sección de subida masiva de Excel para instruir al residente sobre la asignación directa de proveedores con doble clic en la tabla.

### 🔹 `modulos/dashboard_engine.py`
- Funciones analíticas: `_calcular_df_materiales(sel_filtro)`, `_crear_grafica_dona_mat(df_mat_data)`.
- Sincronización matemática estricta con estimaciones individuales y acumuladas (cuadratura al centavo: `$64,529.50` en el proyecto de prueba).
- Nivelación visual milimétrica mediante `height=220` en `st.dataframe` y estilos de una sola línea en `html_barra_mat` y `html_barra_mo`.

---

## 4. Estado del Entorno de Pruebas y Validación Automatizada
- Se ejecutaron auditorías en script con Playwright (`scratch/capture_all_3_views.py`), comprobando la constancia exacta de los espacios intermedios e inferiores en pantalla completa.
- **Git Branch**: `development`.
- **Integridad**: Cero pantallas rojas, RLS activo y preservado en las 13 tablas de la base de datos.
