# ESTIMAPP - Reglas de Operación y Arnés Agéntico

## 1. Contexto Operativo y Entorno
- **Aplicación**: Estimapp (Control de avance físico y financiero de obras públicas y privadas).
- **Terminal Predeterminada**: Git Bash (entorno POSIX/Bash en Windows). NUNCA ejecutar sintaxis ni cmdlets de PowerShell (`Get-Content`, `Select-String`, etc.).
- **Entorno Virtual**: Python activo en `./venv/`. Debe activarse siempre con `source venv/Scripts/activate`.
- **Ejecución Local**: `streamlit run app.py`.
- **Especificaciones Técnicas**: Consulta obligatoria de `./especificaciones.md` para esquemas de tablas, buckets y arquitectura relacional.

---

## 2. Directorios de Recursos y Rutas Relativas
El agente DEBE consultar y respetar los manuales y directrices locales antes de sugerir o escribir código:

- **Skills Oficiales de Streamlit**: `./.agents/skills/developing-with-streamlit/`
  - Consulta obligatoria antes de manipular layouts, fragmentos, ciclo de vida o renderizado de widgets.
- **Skills Oficiales de Supabase**: `./.agents/skills/supabase/`
  - Consulta obligatoria para interacción con clientes de Supabase, autenticación y buckets de Storage.
- **Mejores Prácticas de PostgreSQL**: `./.agents/skills/supabase-postgres-best-practices/`
  - Consulta obligatoria antes de redactar sentencias SQL, migraciones, índices o definiciones de columnas.

---

## 3. Integración con Supabase MCP Server
El agente dispone de integración activa con el servidor MCP de Supabase (`supabase-db` vía OAuth):
- **Capacidad de Inspección**: Utilizar prioritariamente las herramientas del servidor MCP para consultar schemas reales, tablas, tipos de columnas, foreign keys y políticas RLS directamente en Supabase Cloud.
- **Seguridad en Consultas**: Priorizar operaciones de solo lectura para diagnóstico. NUNCA ejecutar sentencias `DROP`, `TRUNCATE` ni `DELETE` directas sobre datos existentes de clientes o proyectos reales.
- **Datos de Prueba**: Todo registro insertado durante validaciones debe llevar el prefijo `TEST_` y eliminarse al concluir la verificación.

---

## 4. Protocolo Holístico de Pruebas y Diagnóstico (End-to-End)
Al ejecutar tareas de auditoría, refactorización o verificación funcional, el agente DEBE validar los tres niveles del sistema:

1. **Capa 1: Base de Datos (MCP / SQL)**:
   - Validar coherencia relacional entre `instituciones`, `proyectos`, `catalogo_conceptos`, `estimaciones` y `mediciones_campo`.
   - Comprobar que los tipos numéricos monetarios y de volumetría mantengan precisión adecuada (`NUMERIC`).
2. **Capa 2: Backend Modular (`./modulos/`)**:
   - `auth_engine.py`: Autenticación, creación de perfiles y control de sesión.
   - `db_engine.py`: Consultas con `@st.cache_data`, normalización estricta mediante `normalizar_unidad()`.
   - `excel_engine.py` & `pdf_engine.py`: Verificación de inyección binaria sobre las plantillas maestras en `./test_files/` sin corromper celdas ni fórmulas.
   - Comprobación estática de dependencias circulares e imports rotos.
3. **Capa 3: Frontend y UI (`./app.py`)**:
   - Inspeccionar la reactividad de `st.session_state` y prevenir errores por widgets duplicados o recreados dinámicamente (`StreamlitWidgetAlreadyInstantiatedError`).
   - Comprobar que las 6 pestañas rendericen sin excepciones en consola.

---

## 5. Reglas Críticas de Arquitectura (INVIOLABLES)
1. **Header Sticky Unificado**:
   - El membrete superior (Logo, Institución, Subtítulo, Usuario y botón Salir) DEBE residir en un único bloque HTML inyectado con clase `.sticky-header` (`top: 0`).
   - NUNCA dividir el encabezado en `st.columns` nativos sueltos de Streamlit, ya que fragmenta el contenedor e impide que descienda junto con el scroll.
   - Las pestañas (`tablist`) deben fijarse a `top: 72px`.
2. **Desacople Institución vs Categoría**:
   - `instituciones`: Tabla propia en Supabase. NUNCA usar registros dummy 'INIT' para simular dependencias.
   - `categoria`: Subpartida/partida opcional dentro de los conceptos. NUNCA almacenar el nombre de la institución en este campo.
3. **Persistencia Multiusuario Retrocompatible**:
   - Toda consulta a tablas compartidas o de usuario debe incluir el filtro: `.or_(f"user_id.eq.{user_id},user_id.is.null")`.
4. **Normalización de Unidades**:
   - Ninguna unidad de medida entra a la base de datos ni a los cálculos sin pasar por `normalizar_unidad()` de `./modulos/db_engine.py`.
5. **Limpieza de Formularios sin Romper Sesión**:
   - Para limpiar campos de texto tras envíos exitosos, incrementar la clave de versión dinámica (`counter_key += 1`) en `st.session_state`.