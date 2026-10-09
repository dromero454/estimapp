# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS (REPORTE #2)
**Fecha de Generación:** 8 de Octubre de 2026 (Sesión de Bug Tracker & Resolución de Incidencias v2.0)  
**Rama:** `development`  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito de este Documento

Este reporte documenta las adiciones estructurales al **Sistema de Reporte y Seguimiento de Incidencias (Bug Tracker)**, las mejoras al **Módulo de Administración de Superadministrador**, y la resolución, verificación y puesta en estado `Corregido` de los primeros cuatro reportes de incidencias (`BUG-001`, `BUG-002`, `BUG-003` y `BUG-004`).

---

## 2. Mejoras Estructurales al Sistema de Bug Tracker

### A. Componente Híbrido de Carga de Evidencias (Archivos y Capturas del Portapapeles)
1. **Doble Contenedor Geométricamente Nivelado al 50% de Ancho:**
   - Contenedor izquierdo: Widget nativo `st.file_uploader` para subir archivos y fotos con selector del sistema operativo o arrastre (`drag & drop`).
   - Contenedor derecho: Componente personalizado bidireccional HTML/JS/CSS (`modulos/clipboard_component/`) que escucha eventos de clic y `Ctrl + V` en el portapapeles, extrayendo imágenes en base64 de forma asíncrona hacia Python.
   - Ambos contenedores están diseñados con bordes redondeados idénticos, tipografía uniforme y limitación de altura con `overflow-y: auto`, mostrando un máximo visual de 3 screenshots en paralelo para mantener una cota perfecta de altura en la ventana modal.
2. **Re-indexación Dinámica de Screenshots:**
   - Al eliminar cualquier captura intermedia (ej. borrar `screenshot_1`), el listado en `st.session_state["bug_screenshots"]` se reordena y re-numera consecutivamente (`screenshot_1.png`, `screenshot_2.png`, etc.) evitando huecos en la base de datos o en el bucket `bugs`.
3. **Ampliación de Pestañas Afectadas (`PESTANAS_MODULOS`):**
   - Se expandió la lista en [modulos/bug_tracker.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/bug_tracker.py) para incluir la totalidad de las pestañas funcionales de la plataforma:
     `"Resumen Financiero"`, `"Captura en Campo"`, `"Estimaciones y Raya"`, `"Catálogo del Proyecto"`, `"Biblioteca Maestra"`, `"Personal y Cuadrillas"`, `"Proveedores"`, `"Proyectos"`, `"Consola Administrador"`, `"Autenticación / Sesión"`, `"General"`.

---

## 3. Infraestructura de Feedback e Iteración en Consola Admin

Para permitir un ciclo iterativo ágil entre Desarrollador/Usuario y el Agente de IA:
1. **Migración en Base de Datos PostgreSQL:**
   - Se agregó la columna `comentarios_revision TEXT` a la tabla `public.reportes_bugs`.
   - Se actualizaron las funciones almacenadas RPC:
     - `public.admin_update_reporte_bug`: Acepta `p_comentarios text DEFAULT NULL` y actualiza `comentarios_revision`.
     - `public.get_admin_reportes_bugs`: Retorna el campo `comentarios_revision` en el payload JSON.
   - Documentado en [data_model_v2.0.md](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/data_model_v2.0.md).
2. **Consola de Superadministrador (`modulos/admin_engine.py`):**
   - Se añadió la columna interactiva **Comentarios** a la tabla maestra de incidencias.
   - Se incorporó un campo de texto dedicado: **💬 Comentarios de Revisión / Feedback para Iteración** dentro de la tarjeta de gestión y resolución técnica de cada ticket.
   - Permite al usuario regresar un ticket de `'Corregido'` a `'En Revisión'` detallando observaciones específicas que el agente leerá directamente en la siguiente iteración.

---

## 4. Resolución Técnica de los Bugs (`BUG-001` a `BUG-004`)

### `BUG-001`: Proyectos - Latitud y Longitud WGS84 de Sólo Lectura
- **Módulo modificado:** [modulos/proyectos_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/proyectos_engine.py)
- **Problema:** Los campos de coordenadas satelitales eran editables manualmente, lo que ponía en riesgo la precisión geoespacial requerida por los futuros modelos de Machine Learning de predicción de viabilidad de costos.
- **Solución:** Se les asignó `disabled=True` en la interfaz. El geocodificador satelital automático OpenStreetMap/Nominatim sigue poblando ambos campos sin permitir alteración arbitraria.

### `BUG-002`: Proveedores - Desfase Numérico en Selector de Baja
- **Módulo modificado:** [modulos/proveedores_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/proveedores_engine.py)
- **Problema:** La tabla inferior mostraba filas numeradas del `#1` al `#N`, mientras que el desplegable para dar de baja mostraba identificadores desfasados (ej. `#11`, `#12`).
- **Solución:** Se alineó el formateador de llaves del selectbox utilizando `enumerate(proveedores_list, start=1)` para garantizar coincidencia visual exacta `#1..N`.

### `BUG-003`: Proveedores - Eliminación de Jerga Técnica SQL
- **Módulo modificado:** [modulos/proveedores_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/proveedores_engine.py)
- **Problema:** El pie aclaratorio bajo el selector de eliminación mostraba la leyenda interna `(ON DELETE SET NULL)`.
- **Solución:** Se limpió el texto para presentar una redacción profesional y orientada al usuario: *"Los insumos asociados en composiciones APU preservan su historial y costo, pero su vínculo comercial quedará desasociado."*

### `BUG-004`: Biblioteca Maestra & Catálogo - Reseteo Reactivo de Desglose APU
- **Módulos modificados:** [modulos/biblioteca_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/biblioteca_engine.py) y [modulos/catalogo_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/catalogo_engine.py)
- **Problema:** Si el usuario ingresaba montos en Material, Mano de Obra, Herramienta o Costo Indirecto y posteriormente modificaba el Precio Unitario (PU) final manualmente, los componentes directos mantenían sus valores previos, provocando una discrepancia aritmética entre la sumatoria de componentes y el PU mostrado.
- **Solución:** Se implementaron callbacks reactivos `_on_pu_ref_bib_change` y `_on_pu_cat_change` en el evento `on_change` del widget de PU. Al alterarse el PU de forma directa, los cuatro componentes analíticos se reinician automáticamente a `$0.00`.

---

## 5. Protocolo de Verificación E2E y Estatus Actual

Todos los cambios fueron validados exhaustivamente mediante el script de pruebas automatizadas [scratch/test_four_bugs_fixes.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/scratch/test_four_bugs_fixes.py) con Playwright y Chromium en entorno headless:
- **BUG-001:** Comprobación de propiedad `is_disabled()` en latitud y longitud. (Aprobado)
- **BUG-002:** Coincidencia de prefijo `#1` en desplegable de baja de proveedores. (Aprobado)
- **BUG-003:** Ausencia de cadena SQL `(ON DELETE SET NULL)`. (Aprobado)
- **BUG-004:** Inyección de montos directos, sobreescritura de PU a `$17.50` y comprobación de reseteo a `$0.00` de materiales y mano de obra. (Aprobado)

Los cuatro tickets fueron actualizados en la base de datos `public.reportes_bugs` a `estado = 'Corregido'` con sus respectivas notas técnicas, quedando listos para la validación final por parte del desarrollador.
