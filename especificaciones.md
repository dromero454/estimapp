# ESTIMAPP - Especificaciones Técnicas del Sistema

Este documento describe la arquitectura técnica, modelo de datos, estructura de directorios y componentes del software **Estimapp**. Debe utilizarse como referencia técnica oficial por desarrolladores y agentes de software.

---

## 1. Entorno de Ejecución y Dependencias
- **Entorno Virtual**: `venv` en la raíz del proyecto.
  - Activación (Bash / Git Bash): `source venv/Scripts/activate`
  - Activación (PowerShell / CMD): `venv\Scripts\activate`
- **Gestor de Paquetes**: `requirements.txt`.
  - Dependencias principales: `streamlit`, `supabase`, `pandas`, `openpyxl`, `reportlab`, `matplotlib`, `pillow`, `requests`.
- **Ejecución Local**: `streamlit run app.py`

---

## 2. Estructura del Repositorio y Directorios

```text
estimapp/
├── .archive/               # Respaldo local de versiones históricas (ignorado en Git).
├── .streamlit/             # Configuración de entorno y secretos locales (secrets.toml).
├── modulos/                # Lógica de negocio y backend desacoplado.
│   ├── __init__.py         # Inicializador de paquete Python.
│   ├── auth_engine.py      # Autenticación, tarjetas de login y registro.
│   ├── db_engine.py        # Consultas a Supabase, caché reactiva y utilidades.
│   ├── excel_engine.py     # Generación e inyección binaria en plantillas Excel oficiales.
│   └── pdf_engine.py       # Compilación de resumen ejecutivo en PDF (ReportLab).
├── test_files/             # Plantillas base oficiales preparadas para exportación Excel.
├── AGENTS.md               # Arnés de reglas de operación y restricciones agénticas.
├── especificaciones.md     # Documento maestro de arquitectura y datos (este archivo).
├── app.py                  # Frontend orquestador de Streamlit (6 tabs principales).
├── requirements.txt        # Dependencias fijas de Python.
└── .gitignore              # Exclusiones de control de versiones.
```

### Detalle de Carpetas Especiales
- **`.archive/`**: Contiene archivos de respaldo históricos (`backup*.py`). Está ignorado en Git para evitar ruido semántico e indexación innecesaria en agentes.
- **`.streamlit/`**: Contiene `secrets.toml` con las variables de entorno de Supabase (`SUPABASE_URL` y `SUPABASE_KEY`). **Nunca se comitea en Git**.
- **`test_files/`**: Carpeta de trabajo que resguarda las plantillas maestras oficiales en formato `.xlsx` utilizadas por `modulos/excel_engine.py`:
  - `plantilla_maestra_estimacion_imss.xlsx`
  - `plantilla_maestra_estimacion_pjf.xlsx`

---

## 3. Infraestructura Cloud (Supabase)

### 3.1 Base de Datos (PostgreSQL en Supabase)
La base de datos relacional opera sobre Supabase Cloud bajo el esquema `public`. Consta de las siguientes tablas:

1. **`instituciones`**:
   - Catálogo de dependencias gubernamentales y clientes (IMSS, PJF, SEDENA, etc.).
   - Campos: `id` (BIGSERIAL PK), `nombre` (TEXT NOT NULL), `user_id` (UUID FK a auth.users), `created_at` (TIMESTAMPTZ).
2. **`biblioteca_conceptos`**:
   - Tabulador maestro de precios de referencia e insumos de obra.
   - Campos: `id` (BIGSERIAL PK), `user_id` (UUID), `institucion` (TEXT), `especialidad` (TEXT), `categoria` (TEXT), `clave` (TEXT), `descripcion` (TEXT), `unidad` (TEXT), `precio_referencial` (NUMERIC).
3. **`proyectos`**:
   - Contratos de obra dados de alta por cada usuario/empresa.
   - Campos: `id` (UUID/BIGINT PK), `user_id` (UUID), `nombre_obra` (TEXT), `descripcion_sintetica` (TEXT), `ubicacion` (TEXT), `unidad` (TEXT), `contrato_no` (TEXT), `concurso_no` (TEXT), `contratista` (TEXT), `residente_obra` (TEXT).
4. **`catalogo_conceptos`**:
   - Presupuesto oficial contratado específico para un proyecto. Son copias desacopladas de la biblioteca o conceptos extraordinarios.
   - Campos: `id` (BIGINT PK), `id_proyecto` (FK a proyectos), `especialidad` (TEXT), `categoria` (TEXT), `clave` (TEXT), `descripcion` (TEXT), `unidad` (TEXT), `cantidad_contratada` (NUMERIC), `precio_unitario` (NUMERIC).
5. **`estimaciones`**:
   - Cortes temporales de avance de obra (Estimación 1, 2, 3...).
   - Campos: `id` (BIGINT PK), `id_proyecto` (FK a proyectos), `num_periodo` (INT), `periodo_inicio` (DATE), `periodo_fin` (DATE), `estado` (`borrador`, `en_revision`, `aprobada`).
6. **`mediciones_campo`**:
   - Volumetrías y generadores capturados en sitio con soporte geométrico y fotográfico.
   - Campos: `id` (BIGINT PK), `id_estimacion` (FK a estimaciones), `id_concepto` (FK a catalogo_conceptos), `localizacion` (TEXT), `eje` (TEXT), `tramo` (TEXT), `largo` (NUMERIC), `ancho` (NUMERIC), `alto` (NUMERIC), `piezas` (NUMERIC), `cantidad_total` (NUMERIC), `url_foto` (TEXT), `url_croquis` (TEXT).
7. **`perfiles`**:
   - Datos ampliados de usuario (`nombre`, `empresa_despacho`) asociados al identificador único de autenticación.

### 3.2 Almacenamiento (Supabase Storage)
- **Bucket `evidencias`**:
  - Almacena fotos de campo y croquis técnicos subidos desde la Tab de Captura.
  - Las imágenes son procesadas con Pillow antes de ser cargadas (máx. 1280px / 80% calidad JPEG).
- **Bucket `plantillas`**:
  - Almacena en la nube las plantillas maestras `.xlsx` para descarga e inyección dinámica.

---

## 4. Descripción de Módulos del Backend

- **`modulos/auth_engine.py`**:
  - Renderiza el flujo visual de autenticación y registro con diseño de tarjetas.
  - Gestiona la sesión de Supabase Auth y crea perfiles por defecto.
- **`modulos/db_engine.py`**:
  - Funciones de consulta a la base de datos decoradas con `@st.cache_data`.
  - Normalizador de unidades métricas (`normalizar_unidad`) para unificar simbologías (`m²`, `m³`, `kg`, `litros`, `m³/km`, etc.).
  - Generador de plantillas Excel en memoria para importación masiva.
  - Compresión y optimización de imágenes para Storage.
- **`modulos/excel_engine.py`**:
  - Motor de inyección paramétrica con OpenPyXL.
  - Escribe carátulas, números generadores, acumulados de periodos anteriores e inserta fotografías de evidencia directamente en las celdas designadas según la institución (IMSS, PJF o Libre).
- **`modulos/pdf_engine.py`**:
  - Generador de resumen ejecutivo de avance físico y financiero con ReportLab.
  - Integra tablas formateadas, encabezados contractuales y gráficos de barra/avance.

---

## 5. Frontend (`app.py`)
Estructurado en 6 pestañas funcionales:
1. **Control Presupuestal**: Dashboard de balance contractual, métricas financieras, tabla de avance físico y descarga de informe PDF.
2. **Captura en Campo**: Entrada de datos paramétricos con selector geométrico (`m²` triangular/trapecio, `m³`, `kg`, etc.), subida de fotos y editor editable de generadores.
3. **Estimaciones**: Apertura y edición de periodos de corte, cambio de estados y exportación de archivos oficiales en Excel.
4. **Catálogo del Proyecto**: Importación desde tabuladores maestros, carga masiva vía Excel y editor de conceptos de obra.
5. **Biblioteca Maestra de Conceptos**: Gestión global de instituciones y tabuladores de precios independientes.
6. **Proyectos**: Alta y actualización de contratos oficiales de obra.