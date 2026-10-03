# ESTIMAPP - Reglas de Arquitectura y Guía para Agentes

## 1. Contexto del Proyecto
- **Aplicación**: Estimapp (Control de avance físico y financiero de obra).
- **Frontend**: Streamlit (`app.py`), backend modular en `modulos/`.
- **Base de Datos & Auth**: PostgreSQL y Supabase Auth en Supabase Cloud.
- **Entorno de ejecución**: Python con entorno virtual `venv` activo (`source venv/Scripts/activate` o `venv\Scripts\activate`).
- **Especificaciones Completas**: Para detalles profundos de base de datos, buckets, tablas y módulos, consulta obligatoriamente `especificaciones.md`.

## 2. Reglas Críticas de Arquitectura (NO MODIFICAR NI ROMPER)
1. **Header Sticky Unificado**:
   - El encabezado superior (Logo, Institución al lado, Subtítulo, Usuario y botón Salir) DEBE residir en un único bloque HTML inyectado con clase `.sticky-header` (`top: 0`).
   - NUNCA dividir el membrete superior en `st.columns` nativos de Streamlit, ya que fragmenta el contenedor e impide que el bloque baje completo con el scroll.
   - Las pestañas (`tablist`) deben permanecer fijadas a `top: 72px`.
2. **Modelo de Instituciones vs Categorías**:
   - `instituciones`: Tabla propia en Supabase (`id`, `nombre`, `user_id`). NUNCA usar registros dummy 'INIT' para simular dependencias.
   - `categoria`: Subpartida/partida técnica opcional dentro de los conceptos. NUNCA almacenar el nombre de la institución en este campo.
3. **Persistencia Multiusuario**:
   - Las consultas deben preservar compatibilidad filtrando siempre por: `.or_(f"user_id.eq.{user_id},user_id.is.null")`.
4. **Normalización de Unidades**:
   - Toda unidad métrica debe procesarse obligatoriamente con `normalizar_unidad()` de `modulos/db_engine.py`.
5. **Manejo de Formularios y Estados**:
   - Para limpiar campos de texto tras envíos exitosos sin romper la sesión de Streamlit, incrementar la clave de versión dinámica (`counter_key += 1`) en `st.session_state`.

## 3. Comandos de Verificación y Testing
- **Ejecutar app localmente**: `streamlit run app.py` (con `venv` activo).
- **Verificación de dependencias**: `pip check` o `pip install -r requirements.txt`.
- **Pruebas de datos**: Al realizar pruebas automatizadas o manuales en la base de datos, utilizar siempre el prefijo `TEST_` en proyectos e instituciones antes de confirmar su eliminación.