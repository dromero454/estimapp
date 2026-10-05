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
- **Aislamiento de Pruebas**: Todo registro generado durante pruebas debe usar el prefijo `TEST_` para garantizar una limpieza completa al finalizar.

---

## 4. Protocolo Holístico de Pruebas E2E (Simulación de Usuario)
Al realizar validaciones completas, el agente debe cubrir el flujo de vida completo del sistema:

1. **Autenticación**: Iniciar sesión utilizando las credenciales de testing configuradas en `.streamlit/secrets.toml` bajo el bloque `[test_user]`.
2. **Creación de Entidades (Ciclo Completo)**:
   - Dar de alta una institución de prueba (`TEST_INSTITUCION`).
   - Crear un contrato/proyecto oficial (`TEST_OBRA_SIMULADA`) asignado a un residente de obra.
   - Poblar el catálogo con conceptos representativos utilizando **todas las unidades disponibles** en el normalizador de `db_engine.py` (`m`, `m²`, `m³`, `kg`, `pza`, `lote`, etc.), con cantidades contratadas y precios unitarios coherentes.
   - Abrir **3 periodos de estimación** consecutivos.
   - Capturar generadores de avance en campo para validar la reactividad geométrica.
3. **Validación de Salidas y Reportes**:
   - Inspeccionar el renderizado del dashboard de balance financiero y avance físico.
   - Validar la compilación del resumen ejecutivo en PDF (ReportLab) y la exportación de plantillas Excel (OpenPyXL) sin excepciones de runtime.
4. **Limpieza e Integridad de Borrado (Tear Down)**:
   - Validar que los botones de eliminación de registros (generadores, estimaciones, conceptos, proyectos e instituciones) eliminen los datos de forma atómica y en cascada sin dejar huérfanos en la base de datos ni provocar caídas visuales en la interfaz.

---

## 5. Reglas Críticas de Arquitectura (INVIOLABLES)
1. **Header Sticky Unificado**:
   - El membrete superior (Logo, Institución, Subtítulo, Usuario y botón Salir) DEBE residir en un único bloque HTML inyectado con clase `.sticky-header` (`top: 0`).
   - NUNCA dividir el encabezado en `st.columns` nativos de Streamlit. Las pestañas (`tablist`) deben fijarse a `top: 72px`.
2. **Desacople Institución vs Categoría**:
   - `instituciones`: Tabla propia en Supabase. NUNCA usar registros dummy 'INIT'.
   - `categoria`: Subpartida/partida opcional dentro de los conceptos.
3. **Persistencia y Aislamiento Multiusuario Estricto (RLS)**:
   - Toda consulta e inserción debe vincular y filtrar explícitamente por el `user_id` de la sesión activa (`.eq("user_id", user_id)` o relación de propiedad de proyecto). NUNCA depender de registros globales o huérfanos con `user_id` nulo. Row Level Security (RLS) se encuentra activo en las 7 tablas de la base de datos.
4. **Normalización de Unidades**:
   - Obligatorio usar `normalizar_unidad()` de `./modulos/db_engine.py`.
5. **Limpieza de Formularios sin Romper Sesión**:
   - Incrementar la clave de versión dinámica (`counter_key += 1`) en `st.session_state` tras un envío exitoso.
