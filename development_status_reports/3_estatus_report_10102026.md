# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS (REPORTE #3)
**Fecha de Generación:** 10 de Octubre de 2026 (Sesión de Modularización, Viewport Atómico y Persistencia Bidireccional de Pestañas)  
**Rama:** `development`  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito de este Documento

Este reporte documenta la resolución integral y definitiva de los últimos desafíos de arquitectura en la plataforma Estimapp:
1. **Modularización limpia del Drawer To-Go de Superadmin** en un módulo independiente (`modulos/drawer_tracker.py`), reduciendo `modulos/bug_tracker.py` de casi 900 líneas a 297 líneas enfocadas exclusivamente en el modal de incidencias general.
2. **Eliminación del Renderizado Fantasma y Mezcla Visual de Vistas** mediante la encapsulación en un contenedor atómico (`main_viewport = st.empty()`).
3. **Persistencia Bidireccional del Estado de Navegación de Pestañas**: Recordar la pestaña activa tanto al alternar entre la aplicación de Obra y la Consola de Administrador como viceversa.
4. **Blindaje de Escucha de Eventos DOM y Estabilidad del Drawer**: Eliminación de fallos de clausura en iframes de Streamlit (`el.onclick`) y anclaje procedimental estable del drawer en el árbol de widgets.

---

## 2. Diagnóstico de Causa Raíz y Solución Arquitectónica

### A. Modularización de `bug_tracker.py` ➔ `drawer_tracker.py`
- **Problema previo:** En `bug_tracker.py` se habían acumulado casi 900 líneas combinando dos paradigmas opuestos: el modal de reporte para cualquier usuario (`@st.dialog`) y la barra lateral flotante e interactiva exclusiva para Superadmin (`@st.fragment`).
- **Solución implementada:** Se extrajo toda la lógica, estilos CSS, panel scrolleable, subida de evidencias y notas de resolución hacia `modulos/drawer_tracker.py`. `modulos/bug_tracker.py` ahora contiene solo las constantes y el diálogo modal (`render_bug_report_dialog`), re-exportando el drawer para mantener retrocompatibilidad.

### B. Erradicación del Renderizado Fantasma y Micro-Parpadeos
- **Hallazgo Crítico:** Inicialmente se probó encapsular las vistas en `main_viewport = st.empty()`. Sin embargo, esto causaba que en cada rerun (por interacción o apertura de la barra lateral), `st.empty()` vaciaba y destruía todo el DOM del viewport principal antes de repintarlo, provocando micro-parpadeos y la desaparición momentánea de tablas y tarjetas.
- **Solución Definitiva:**
  1. Se eliminó `st.empty()`. Ambas vistas ahora se ejecutan en el flujo procedimental principal, permitiendo que el motor de reconciliación de React preserve los componentes montados en el DOM sin destruirlos al abrir o cerrar el drawer lateral.
  2. En la rama de Admin se implementó `st.stop()`:
     ```python
     if st.session_state.get("vista_actual") == "admin" and es_admin_usr:
         render_admin_dashboard(supabase)
         st.stop()
     ```
     Como el drawer de seguimiento se renderiza procedimentalmente en la línea 463 (antes de este bloque), la barra lateral ya está activa. `st.stop()` detiene inmediatamente la ejecución de Python, garantizando que el código y pestañas de Obra jamás se ejecuten en la consola de Admin (cero deltas fantasma, cero renderizado doble y máxima velocidad).

### C. Persistencia Bidireccional de Pestañas sin Reruns de Servidor
- **Problema de `on_change="rerun"`:** Al forzar `on_change="rerun"` en `st.tabs`, cada clic del usuario en una pestaña disparaba una ejecución completa de Python, eliminando la fluidez nativa a 0ms de Streamlit.
- **Solución Definitiva (0ms Latencia y Persistencia Total):**
  1. Se retiró `on_change="rerun"` tanto en Obra como en Admin, restaurando el comportamiento nativo de BaseWeb (`on_change="ignore"`). El cambio de pestaña ocurre al 100% en el cliente en 0ms, sin peticiones al servidor ni parpadeos.
  2. En el cliente (`components.html`), un escuchador pasivo en `doc.documentElement.dataset.tabSyncBound` captura el texto de `[role="tab"][aria-selected="true"]` y lo sincroniza con la URL vía `window.parent.history.replaceState` en los parámetros `t_obra` y `t_admin`.
  3. Asimismo, al hacer clic en los enlaces del header (`.admin-link`, `.tracking-link`, etc.) o en el botón "⬅️ Volver a la aplicación", la pestaña activa se estampa inmediatamente en la URL.
  4. En Python, `st.tabs` recibe `default=st.query_params.get("t_obra")` y `default=st.query_params.get("t_admin")`, seleccionando instantáneamente la pestaña correcta sin requerir reruns adicionales.

### D. Anclaje Procedimental del Drawer y Despacho de Eventos en el Encabezado
- **Estabilidad del Drawer:** Se colocó el renderizado de `render_bug_tracking_drawer` en una posición procedimental previa a la vista principal (línea 463). De este modo, los deltas del drawer se envían al navegador de inmediato, eliminando desapariciones temporales o re-deslizamientos innecesarios.
- **Limpieza de Clics (`el.onclick` y `doc.documentElement.dataset`):** Se reemplazó el binding con `addEventListener` y flags `dataset.bound` en el documento por asignación directa de propiedades `el.onclick` y almacenamiento seguro en `doc.documentElement.dataset`. Esto garantiza que los escuchadores apunten a contextos vivos sin fugas de clausuras.

---

## 3. Verificación Automatizada E2E con Playwright

Se ejecutó la suite de validación completa en Chromium (`scratch/verify_smooth_flow.py`):
1. **Inicio de sesión** como Superadministrador aprobado.
2. **Navegación en Obra** hacia una pestaña no inicial (`📚 Catálogo del Proyecto`): Cambio instantáneo en 0ms.
3. **Apertura de la Barra Lateral (Drawer To-Go)**: Panel visible, animación fluida, cero parpadeo y la pestaña de Obra permanece intacta.
4. **Cierre de la Barra Lateral**: Ocultamiento instantáneo sin alterar la vista.
5. **Transición a Consola de Administrador**:
   - Consola desplegada limpiamente.
   - Exactamente 1 tablist en pantalla (0 pestañas fantasma de Obra).
6. **Navegación en Consola de Admin** hacia una pestaña no inicial (`🐞 Gestión de Incidencias`).
7. **Retorno a la Aplicación de Obra**:
   - **La pestaña activa se restauró automáticamente en `📚 Catálogo del Proyecto`**.
8. **Segundo Retorno a la Consola de Admin**:
   - **La pestaña activa se restauró automáticamente en `🐞 Gestión de Incidencias`**.
9. **Resultado de la Suite:** `🎉 ALL TESTS PASSED WITH 100% SUCCESS!`.

---

## 4. Estado de la Base de Código y Archivos Modificados
- `app.py`: Eliminación de `main_viewport = st.empty()`, conmutación atómica con `st.stop()`, captura de pestañas en `query_params` y eventos con `doc.documentElement.dataset`. Inclusión de `importlib.reload(modulos.drawer_tracker)` y neutralización a 0.0px del contenedor fragment en `hideAndBindTrigger()`.
- `modulos/bug_tracker.py`: Reducido a 297 líneas. Diálogo modal de reporte conciso y aislado.
- `modulos/drawer_tracker.py`: Nuevo módulo dedicado al Drawer To-Go de Superadmin (~600 líneas).
- `modulos/admin_engine.py`: Tabs nativos con `default=default_admin_tab` vía `query_params` y retiro de `on_change="rerun"`.

---

## 5. Ajuste Aislado de Desplazamiento Vertical (Zero-Shift 0.0px) y Preservación de Headers

### A. Diagnóstico del Salto Visual de 32px al Abrir el Drawer
- **Causa Raíz:** Al llamar `render_bug_tracking_drawer` en la línea 465 de `app.py`, el contenedor de `@st.fragment` generaba un bloque en el flujo procedimental vertical de Streamlit (`stLayoutWrapper` / `stVerticalBlock`) de 16px de altura + 16px de separación = 32px exactos.
- **Efecto Visual:** Aunque el panel visual `.st-key-drawer_tracking_panel` flota a la derecha con `position: fixed`, su bloque contenedor padre empujaba hacia abajo la tira de pestañas (`stTabs`) exactamente 32px (de Y=179.8px a Y=211.8px), creando la ilusión óptica de que el Header cambiaba de tamaño.

### B. Blindaje Inviolable de los Headers (Regla 6 de AGENTS.md)
- Por acuerdo estricto de arquitectura y para proteger la UX global de contratistas y residentes, **ambos headers permanecieron 100% intactos**:
  - Cero modificaciones a la estructura HTML y estilos CSS de `.sticky-header`.
  - Cero alteraciones al banner de la Consola de Administrador.

### C. Solución Implementada (Ajuste Aislado en Cliente)
- En `hideAndBindTrigger()` (`components.html` en `app.py`), se aplicó el mismo mecanismo que ya neutraliza los disparadores invisibles:
  ```javascript
  const drawerPanel = doc.querySelector('.st-key-drawer_tracking_panel');
  if (drawerPanel) {
      const mainBlock = doc.querySelector('[data-testid="stMainBlockContainer"] > .stVerticalBlock');
      if (mainBlock) {
          for (const child of mainBlock.children) {
              if (child.contains(drawerPanel)) {
                  if (child.style.position !== 'absolute') {
                      child.style.position = 'absolute';
                      child.style.height = '0px';
                      child.style.width = '0px';
                      child.style.margin = '0px';
                      child.style.padding = '0px';
                      child.style.pointerEvents = 'none';
                  }
                  break;
              }
          }
      }
      drawerPanel.style.setProperty('pointer-events', 'auto', 'important');
  }
  ```
- **Medición Empírica con Playwright en Navegador Real:**
  - Altura Header: Cerrado = `123.76 px` | Abierto = `123.76 px` (**Diferencia: `0.0 px`**).
  - Cota Y Pestañas: Cerrado = `179.76 px` | Abierto = `179.76 px` (**Salto Vertical: `0.0 px`**).
  - Cierre y Apertura con Botón ✕: 100% fluido y reactivo.

---

## 6. Directorio de Respaldo y Mecanismo de Regresión Inmediata (Zero-Delay Rollback)

Para máxima seguridad del desarrollador y permitir pruebas sin riesgo alguno:
1. **Directorio de Respaldo Físico:** Se encuentra respaldado el estado exacto pre-ajuste en:
   - `backups/drawer_isolated_adjustment_checkpoint/app.py`
   - `backups/drawer_isolated_adjustment_checkpoint/drawer_tracker.py`
   - `backups/drawer_isolated_adjustment_checkpoint/bug_tracker.py`
   - `backups/drawer_isolated_adjustment_checkpoint/admin_engine.py`
2. **Script de Restauración Instantánea:**
   - Archivo: `rollback_to_checkpoint.py`
   - Ejecución: `python rollback_to_checkpoint.py`
   - Tiempo de restauración: Menos de 1 segundo sin demoras ni dependencias externas.

