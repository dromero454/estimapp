# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS (REPORTE #4)
**Fecha de Generación:** 13 de Octubre de 2026 (Resolución Integral del Lote de Incidencias BUG-006 a BUG-013)  
**Rama:** `development`  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito y Resumen Ejecutivo

Este documento detalla la resolución técnica exhaustiva, atómica y probada de un lote integral de 8 reportes de incidencias (`BUG-006` a `BUG-013`) en la plataforma Estimapp. 

Las intervenciones cubrieron desde extensiones al modelo de datos en PostgreSQL (Supabase Cloud), ingeniería de backend en el motor de importación Excel y generador de reportes PDF, hasta mejoras de experiencia de usuario, reactividad en captura de campo y visualizaciones analíticas interactivas en el Dashboard.

Todos los tickets fueron verificados mediante suites unitarias de prueba y automatización E2E en navegador con Playwright, y sus estados fueron actualizados en la base de datos a `'Corregido'` con notas de resolución técnicas detalladas, dejándolos listos para la inspección y validación final por parte del Superadministrador.

---

## 2. Modificaciones al Modelo de Datos (PostgreSQL en Supabase Cloud)

### Tabla `personal_obra`
- **Columna Agregada**: `modalidad_pago TEXT DEFAULT 'Por Destajo'`
- **Constraint / Valores Válidos**: `'Por Destajo'`, `'Por Jornada'`.
- **Propósito**: Permitir clasificar contractualmente al personal en dos esquemas operativos con fórmulas de liquidación financieras completamente distintas:
  1. *Por Destajo*: Liquidación ligada al volumen de obra ejecutado multiplicado por el precio unitario de mano de obra del concepto.
  2. *Por Jornada*: Liquidación basada en días trabajados multiplicados por la cuota diaria fija pactada.
- **Migración Ejecutada**:
  ```sql
  ALTER TABLE personal_obra 
  ADD COLUMN IF NOT EXISTS modalidad_pago TEXT DEFAULT 'Por Destajo';
  
  UPDATE personal_obra 
  SET modalidad_pago = 'Por Destajo' 
  WHERE modalidad_pago IS NULL;
  ```

---

## 3. Desglose Técnico por Incidencia Resuelta

### 🔹 BUG-006: Captura de Giro "Otros" y Sincronización Dinámica de Filtros
- **Módulo**: `modulos/proveedores_engine.py`
- **Diagnóstico**: Al dar de alta un proveedor con giro "Otros", el sistema no ofrecía una caja de texto para especificar la actividad económica real. Si se registraba un giro personalizado mediante base de datos, el filtro superior y la columna `SelectboxColumn` de `st.data_editor` provocaban inconsistencias o bloqueos en el frontend de Streamlit por no coincidir con las opciones estáticas predefinidas.
- **Solución Implementada**:
  1. Se implementó un subcampo condicional en el formulario de registro (`st.text_input("Especifica el giro o actividad comercial")`) que se despliega únicamente cuando se selecciona `giro == "Otros"`, guardando el registro con la nomenclatura normalizada `Otros: [detalle]`.
  2. El listado de giros para el filtro superior y para el componente `st.column_config.SelectboxColumn` de la tabla interactiva ahora extrae dinámicamente todos los giros únicos existentes en la base de datos y los fusiona con la lista estándar:
     ```python
     giros_en_bd = [p.get("giro") for p in proveedores_list if p.get("giro")]
     opciones_giro = sorted(list(set(GIROS_PREDEFINIDOS + giros_en_bd)))
     ```
  3. Esto elimina cualquier error de validación en BaseWeb/Streamlit al editar proveedores con giros personalizados.

---

### 🔹 BUG-007: Consecutivos Posicionales y Redacción Amigable en Baja de Personal
- **Módulo**: `modulos/personal_engine.py`
- **Diagnóstico**: El selector para dar de baja trabajadores mostraba el ID primario de base de datos (`#33`) en lugar de alinearse con el número de fila visible (`#1..N`) en la tabla de cuadrillas. Además, el texto explicativo exponía tecnicismos de base de datos (`(ON DELETE SET NULL)`), reduciendo la calidad percibida del software.
- **Solución Implementada**:
  1. Se actualizaron las etiquetas del `st.selectbox` mediante `enumerate(personal_list, start=1)`:
     ```python
     def fmt_baja(idx_p):
         i, p = idx_p
         return f"#{i} - {p.get('nombre_completo', 'Sin nombre')} ({p.get('oficio_especialidad', 'General')})"
     ```
  2. Se sustituyó el texto técnico por una redacción profesional y tranquilizadora:
     > *"Nota: Al dar de baja a un trabajador, su registro histórico en generadores y mediciones de campo se preservará intacto para auditoría y archivo."*

---

### 🔹 BUG-008: Separación Estricta de Mano de Obra (Destajos vs Jornadas)
- **Módulos**: `modulos/personal_engine.py`, `modulos/estimaciones_engine.py`, `modulos/pdf_engine.py`, `modulos/db_engine.py`
- **Diagnóstico**: La aplicación calculaba la mano de obra sin distinguir entre trabajadores a destajo y trabajadores por jornada diaria, mezclando conceptos volumétricos con sueldos fijos.
- **Solución Implementada**:
  1. **Alta de Personal**: Se agregó el selector `Modalidad de Pago` (`"Por Destajo"` / `"Por Jornada"`) en el formulario de registro de trabajadores.
  2. **Consulta Enriquecida**: Se actualizó `get_mediciones` en `modulos/db_engine.py` para incluir mediante foreign table de Supabase la modalidad de pago, el costo unitario de mano de obra y la descripción del concepto.
  3. **Liquidación en Tab 3 (Estimaciones y Pagos)**:
     - Se crearon **4 tarjetas KPI superiores**: Gran Total Mano de Obra, Total por Destajos, Total por Jornadas y Jornadas Acumuladas.
     - Se estructuró la sección en **dos tablas independientes**:
       - *Tabla 1 (Superior)*: **Relación de Actividades Liquidadas por Destajo**: Lista cada concepto ejecutado, unidad, P.U. de Mano de Obra contratado, volumen ejecutado en el periodo y subtotal a liquidar.
       - *Tabla 2 (Inferior)*: **Relación de Actividades Liquidadas por Jornada**: Detalla cada trabajador, especialidad, jornadas computadas, salario diario pactado y total a pagar.
  4. **Emisión de Recibos y Cédula en PDF**:
     - Se implementó `generar_pdf_recibo_pagos()` en `modulos/pdf_engine.py`.
     - El documento oficial imprime primero la tabla de destajos por concepto, después la nómina de trabajadores por jornada, y finalmente los recibos individuales consolidados con campo *"Firma de Recibido:"* (eliminando la referencia a huella).

---

### 🔹 BUG-009: Robustecimiento de Importación Excel y Categoría en Bug Tracker
- **Módulos**: `modulos/db_engine.py`, `modulos/bug_tracker.py`
- **Diagnóstico**: Al subir plantillas Excel con filas vacías o celdas de cantidad no especificadas, la función `procesar_excel_importacion()` fallaba con `ValueError: cannot convert float NaN to integer`. La causa raíz fue la peculiaridad de Python donde `bool(float('nan')) == True`, por lo que expresiones como `cant_raw or 0.0` no protegían contra valores `np.nan`. Asimismo, en el Bug Tracker no existía la categoría "Importación de Archivos".
- **Solución Implementada**:
  1. Se implementó el helper seguro `_safe_float()` en `modulos/db_engine.py`:
     ```python
     def _safe_float(val, default=0.0):
         if pd.isna(val):
             return default
         try:
             res = float(val)
             return default if math.isnan(res) else res
         except (ValueError, TypeError):
             return default
     ```
  2. Se validó contra el archivo reportado (`BUG-009_Plantilla_Cat_Proyecto_...xlsx`), procesando exitosamente los 6 registros de prueba sin excepciones.
  3. Se incorporó `"Importación de Archivos"` al listado oficial `CATEGORIAS_BUGS` en `modulos/bug_tracker.py`.

---

### 🔹 BUG-010: Nomenclatura Tab 3 y Erradicación del Término "Raya"
- **Módulos**: `app.py`, `modulos/bug_tracker.py`, `modulos/estimaciones_engine.py`
- **Diagnóstico**: El término "Raya" y "Telemetría Meteorológica" persistían en la barra de pestañas, en los selectores del Bug Tracker modal y en el Drawer lateral de superadmin.
- **Solución Implementada**:
  1. Se actualizó la constante `PESTANAS_MODULOS` en `app.py` y `modulos/bug_tracker.py` reemplazando `'Estimaciones y Raya'` por `'Estimaciones y Pagos'`.
  2. La Tab 3 ahora se titula formalmente `📑 Estimaciones y Pagos`.
  3. El subpanel de liquidación se renombró a `Liquidación de Pagos y Control de Destajos`.
  4. La sección climática se homologó a `Reporte Meteorológico`.
  5. Se erradicó por completo la palabra "Raya" de todos los títulos, botones y leyendas de la plataforma.

---

### 🔹 BUG-011: Edición Inline de Personal y Jornadas en Mediciones de Campo
- **Módulo**: `modulos/mediciones_engine.py`
- **Diagnóstico**: En la tabla de mediciones de campo, para corregir el trabajador asignado o las jornadas capturadas era necesario eliminar el registro completo y volver a capturarlo.
- **Solución Implementada**:
  1. Se configuraron las columnas `Destajista / Trabajador` (`SelectboxColumn`) y `Jornadas` (`NumberColumn`) como editables en `st.data_editor`.
  2. Se implementó la lógica de detección de deltas al guardar cambios:
     - Mapea el nombre seleccionado al `id_personal` correspondiente.
     - Ejecuta una actualización atómica en Supabase Cloud sobre `mediciones_campo`:
       ```python
       supabase.table("mediciones_campo").update(payload).eq("id", id_med).execute()
       ```
  3. Muestra una notificación de éxito clara y recarga limpiamente el estado.

---

### 🔹 BUG-012: Reactividad en Captura de Campo según Modalidad de Contratación
- **Módulo**: `modulos/mediciones_engine.py`
- **Diagnóstico**: El campo en el formulario de captura se llamaba genéricamente "Trabajador asignado" y permitía capturar jornadas incluso si el trabajador seleccionado operaba bajo esquema de destajo.
- **Solución Implementada**:
  1. El campo se renombró a `👷 Destajista / Trabajador responsable`.
  2. Se agregó reactividad dinámica con `disabled`:
     - Al seleccionar un trabajador cuya modalidad de pago es `"Por Destajo"` (o `"Sin asignar"`), el campo de `Jornadas invertidas` se deshabilita automáticamente y presenta un mensaje explicativo (`help`):
       > *"Los trabajadores por destajo cobran sobre el volumen de obra ejecutado. El campo de jornadas solo aplica para personal liquidado por jornada fija."*
     - Al seleccionar un trabajador `"Por Jornada"`, el campo se habilita normalmente para capturar los días laborados.

---

### 🔹 BUG-013: Dashboard Interactivo: Gasto Reportable y Dona Filtrable por Estimación
- **Módulo**: `modulos/dashboard_engine.py`
- **Diagnóstico**: El dashboard carecía de una métrica clara para el "Gasto Reportable" (monto contratado estimado con margen), la gráfica de dona de costos no permitía aislar periodos específicos de estimación, y los banners de semáforo carecían de márgenes estéticos.
- **Solución Implementada**:
  1. Se renombró la sección principal a `##### 🏛️ Resumen Global del Proyecto`.
  2. Se incorporó una 5ª tarjeta métrica destacada: **`Gasto Reportable`**, que totaliza el monto acumulado proyectado con margen sobre las estimaciones activas.
  3. Se añadió un selector interactivo sobre la gráfica de dona y la tabla analítica:
     - Opción por defecto: `"Total Acumulado"`.
     - Opciones dinámicas: `"Estimación 1"`, `"Estimación 2"`, etc.
     - La distribución porcentual de Costo Directo, Costo Indirecto y Margen se recalcula reactivamente según la selección del usuario.
  4. Se insertaron separadores de respiro `<div style='height: 8px;'></div>` alrededor de los avisos de semáforo de costo y avance.

---

## 4. Estado de los Tickets en Supabase (`reportes_bugs`)

En estricto apego a `PROTOCOLO_BUGS.md` y `AGENTS.md`, el agente **únicamente** transiciona los tickets al estado `'Corregido'` y documenta la resolución técnica. La facultad de `'Validado'` o `'Descartado'` queda reservada de forma exclusiva para el Superadministrador.

| Folio | Categoría | Pestaña Afectada | Estado Anterior | Estado Actual | Actualizado |
|---|---|---|---|---|---|
| **BUG-006** | Otro | Proveedores | Abierto | **Corregido** | 2026-10-13 |
| **BUG-007** | Cálculos y Fórmulas | Personal y Cuadrillas | Abierto | **Corregido** | 2026-10-13 |
| **BUG-008** | Cálculos y Fórmulas | Estimaciones y Pagos | Abierto | **Corregido** | 2026-10-13 |
| **BUG-009** | Exportación/Importación | Catálogo del Proyecto | Abierto | **Corregido** | 2026-10-13 |
| **BUG-010** | Interfaz y Visualización | Estimaciones y Pagos | Abierto | **Corregido** | 2026-10-13 |
| **BUG-011** | Cálculos y Fórmulas | Captura en Campo | Abierto | **Corregido** | 2026-10-13 |
| **BUG-012** | Interfaz y Visualización | Captura en Campo | Abierto | **Corregido** | 2026-10-13 |
| **BUG-013** | Interfaz y Visualización | General / Dashboard | Abierto | **Corregido** | 2026-10-13 |

---

## 5. Verificación Automatizada E2E y Estabilidad

Se ejecutó la suite de pruebas automatizadas en Chromium mediante Playwright (`scratch/verify_all_bugs_e2e.py`):
1. **Inicio de sesión automatizado** con credenciales oficiales de testing (`test_user`): Exitoso.
2. **Inspección de Pestañas**:
   - `📑 Estimaciones y Pagos` presente y activa.
   - Término `Raya` 100% ausente del DOM.
3. **Tab 1 (Dashboard)**: Título `🏛️ Resumen Global del Proyecto`, métrica de `Gasto Reportable` y filtro de dona validados.
4. **Tab 3 (Estimaciones y Pagos)**: Subpanel `Liquidación de Pagos y Control de Destajos` validado.
5. **Tab 6 (Personal y Cuadrillas)**: Selector `Modalidad de Pago` y consecutivos validados.
6. **Tab 7 (Proveedores)**: Directorio activo y captura de giros personalizados validados.
7. **Generador PDF**: `generar_pdf_recibo_pagos()` compila limpiamente sin fallos de formato.
8. **Importador Excel**: Valida celdas vacías y NaN sin lanzar `ValueError`.

Resultado global: **`ALL BROWSER E2E VALIDATIONS PASSED SUCCESSFULLY (Exit Code 0)`**.
