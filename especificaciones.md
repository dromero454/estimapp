# ESTIMAPP v2.0 - ESPECIFICACIONES TÉCNICAS DEL SISTEMA

Este documento describe la arquitectura técnica, modelo de datos, componentes de backend, estructura modular y flujos de frontend de **Estimapp** en su versión actual **v2.0**. Constituye la referencia técnica oficial para desarrolladores y agentes de inteligencia artificial.

---

## 1. Entorno de Ejecución y Dependencias

- **Plataforma Base**: Python 3.11+ sobre entorno virtual local `./venv/`.
- **Terminal Predeterminada**: Git Bash (entorno POSIX/Bash en Windows). NUNCA ejecutar cmdlets ni sintaxis de PowerShell (`Get-Content`, `Select-String`, etc.).
  - Activación: `source venv/Scripts/activate`
- **Gestor de Paquetes**: `requirements.txt`.
  - Dependencias principales: `streamlit`, `supabase`, `pandas`, `openpyxl`, `reportlab`, `matplotlib`, `pillow`, `altair`, `requests`, `toml`, `playwright`.
- **Ejecución Local**: `streamlit run app.py` (puerto predeterminado `8501`).

---

## 2. Estructura del Repositorio y Arquitectura Modular

```text
estimapp/
├── .agents/                               # Configuración de agentes, herramientas y skills
│   └── skills/                            # Directrices canónicas locales
│       ├── developing-with-streamlit/     # Reglas y patrones de Streamlit
│       ├── supabase/                      # Directrices oficiales de clientes Supabase
│       └── supabase-postgres-best-practices/# Mejores prácticas SQL y PostgreSQL
├── .archive/                              # Respaldo histórico de versiones previas
├── .streamlit/                            # Configuración local de entorno y secretos
│   └── secrets.toml                       # Credenciales de Supabase y [test_user]
├── development_status_reports/            # Memoria viva y reportes cronológicos de avance
│   └── 1_estatus_report_07102026.md       # Reporte fundacional post-Etapa 4
├── estimapp_v2.0/                         # Roadmap, DDL y checklists de la versión v2.0
│   ├── roadmap_v2.0.md
│   ├── supabase_migration_v2.sql
│   └── testing_checklist.md
├── modulos/                               # Backend desacoplado y lógica de negocio
│   ├── __init__.py                        # Inicializador de paquete Python
│   ├── admin_engine.py                    # Consola de Superadministrador (auditoría, storage, bugs)
│   ├── auth_engine.py                     # Autenticación, tarjetas de acceso y modal de perfil
│   ├── biblioteca_engine.py               # Tabuladores maestros por institución con soporte Dual Path
│   ├── bug_tracker.py                     # Diálogo modal y persistencia de tickets de incidencias
│   ├── catalogo_engine.py                 # Catálogo del proyecto, desglose APU e importador Excel
│   ├── dashboard_engine.py                # Dashboard tri-modal, dona Altair y paridad milimétrica
│   ├── db_engine.py                       # Caché con TTL (ttl=60), normalizador y multi-archivos
│   ├── estimaciones_engine.py             # Cortes de estimación, telemetría clima y recibo de raya
│   ├── excel_engine.py                    # Inyección OpenPyXL en plantillas IMSS, PJF y Estimapp
│   ├── mediciones_engine.py               # Generadores de campo, destajistas y multi-evidencias
│   ├── pdf_engine.py                      # ReportLab: Resumen ejecutivo tri-modal y Recibo de Raya
│   ├── personal_engine.py                 # Directorio de trabajadores y cuadrillas del despacho
│   ├── proveedores_engine.py              # Directorio de proveedores de materiales e insumos
│   └── proyectos_engine.py                # Contratos de obra, geocodificación OSM sesgada por IP
├── test_files/                            # Plantillas maestras base oficiales (.xlsx)
├── scratch/                               # Scripts de prueba, inspección DOM y screenshots E2E
├── AGENTS.md                              # Reglas operativas y directrices agénticas obligatorias
├── data_model_v2.0.md                     # Diccionario de datos y esquema DDL oficial v2.0
├── especificaciones.md                    # Este documento técnico
├── README.md                              # Visión ejecutiva, arquitectura y hoja de ruta ML
├── app.py                                 # Orquestador frontend Streamlit (8 tabs + Consola Admin)
└── requirements.txt                       # Dependencias fijas de Python
```

---

## 3. Infraestructura Cloud (Supabase)

### 3.1 Integración MCP Server
El entorno cuenta con el servidor MCP de Supabase (`supabase-db` vía OAuth). El agente debe priorizar las herramientas MCP para consultar esquemas reales, tipos de columnas, foreign keys y políticas RLS directamente en la nube antes de ejecutar o proponer migraciones.

### 3.2 Esquema Relacional Vigente (PostgreSQL en Supabase)
El sistema opera sobre el esquema `public` con **13 tablas relacionales activas**, todas protegidas con **Row Level Security (RLS)**:

1. **`instituciones`**: Catálogo de dependencias gubernamentales y clientes institucionales (IMSS, PJF, SEDENA, etc.).
2. **`proyectos`**: Contratos de obra con 14 columnas ampliadas v2.0:
   - Modalidad tri-modal (`publica`, `privada`, `mixta`).
   - Factores paramétricos de sobrecosto: `porcentaje_indirectos`, `porcentaje_utilidad`, `porcentaje_herramienta`, `porcentaje_iva`.
   - Georreferenciación: `pais`, `estado`, `municipio`, `codigo_postal`, `direccion_calle`, `formatted_address`, `latitud`, `longitud`.
3. **`catalogo_conceptos`**: Catálogo contractual oficial de la obra con arquitectura **Dual Path**:
   - Desglose analítico de APU: `costo_material`, `costo_mano_obra`, `costo_herramienta`, `costo_indirecto`, `porcentaje_utilidad`.
   - Cálculo reactivo del precio unitario contractual a partir del análisis de costos directos e indirectos.
4. **`biblioteca_conceptos`**: Tabulador maestro independiente de precios de referencia e insumos con soporte Dual Path (`costo_material`, `costo_mano_obra`, `costo_herramienta`, `costo_indirecto`, `precio_referencial`).
5. **`estimaciones`**: Periodos de corte temporal de avance (Estimación 1, 2, 3...) con control de estados (`borrador`, `en_revision`, `aprobada`) y registro de fechas.
6. **`mediciones_campo`**: Generadores volumétricos capturados en sitio:
   - Geometría: `largo`, `ancho`, `alto`, `piezas`, `cantidad_total`.
   - Asignación de destajo: `id_personal` (FK a `personal_obra`), `horas_o_jornales`.
   - Multi-evidencias: `url_foto` y `url_croquis` (cadenas con múltiples URLs públicas separadas por comas).
7. **`personal_obra`**: Directorio de trabajadores y cuadrillas del despacho (`nombre`, `especialidad`, `costo_jornal_base`, `telefono`).
8. **`proveedores`**: Directorio de proveedores de materiales y subcontratos (`nombre_comercial`, `giro`, `contacto`, `telefono`).
9. **`insumos_concepto`**: Descomposición analítica detallada de insumos unitarios para cada concepto del catálogo (`material`, `mdeo`, `herramienta`, `subcontrato`, `indirecto`).
10. **`hitos_cobro`**: Cronograma comercial de hitos de facturación y cobro vinculado al proyecto.
11. **`telemetria_clima`**: Registro de condiciones meteorológicas en campo obtenido vía Open-Meteo (`temp_media_c`, `temp_max_c`, `precipitacion_mm`, `dias_lluvia`, `humedad_relativa_pct`).
12. **`perfiles`**: Datos ampliados del usuario de Supabase Auth (`nombre`, `apellido_paterno`, `apellido_materno`, `empresa_despacho`, `rol`, `es_admin`).
13. **`reportes_bugs`**: Bug Tracker integral con folios correlativos (`BUG-XXX`), tabs afectadas, categoría, evidencias adjuntas, estado (`Abierto`, `En Revisión`, `Corregido`, `Bajo Consideración`, `Validado`, `Descartado`), notas de resolución y comentarios de revisión. (Ver manual normativo en `./PROTOCOLO_BUGS.md`).

#### Vista Analítica de Machine Learning
- **`v_telemetria_rendimientos_ml`**: Feature Store SQL unificado que cruza mediciones de campo, factores geográficos, especialidades de catálogo, destajistas asignados y telemetría climática para preparar el entrenamiento de modelos predictivos de rendimientos y costos.

### 3.3 Almacenamiento en la Nube (Supabase Storage)
- **Bucket `evidencias`**: Fotografías de obra y croquis técnicos subidos desde Captura en Campo. Las imágenes se comprimen con Pillow (máx. 1280px / 80% calidad JPEG). Soporta subidas múltiples y eliminación atómica en cascada.
- **Bucket `plantillas`**: Archivos `.xlsx` maestros oficiales para exportación en la nube.
- **Bucket `bugs`**: Evidencias fotográficas y archivos adjuntos de incidencias bajo la ruta `{folio}/{archivo}`.

---

## 4. Descripción de Módulos del Backend (`modulos/`)

### 4.1 `dashboard_engine.py` (Balance Presupuestal y Financiero)
- **Tri-modal adaptativo**:
  - `publica`: Enfoque contractual tradicional (Contratado, Estimado, Saldo por Ejercer, Avance Oficial y Barra de Progreso).
  - `privada`: Enfoque de negocio y rentabilidad real (Erogado Real, Utilidad Bruta, Margen del Despacho, Destajos Pagados y Semáforo de Nómina).
  - `mixta`: Dos columnas paralelas sincronizadas (`col_pub` y `col_priv`).
- **Gráfica de Dona Interactiva (Altair / Vega-Lite)**: Representa los 5 rubros del despacho (Materiales, Mano de Obra, Herramienta, Indirectos, Utilidad) con paleta corporativa y tooltips numéricos limpios.
- **Opción A (Estricta y Transparente)**: Si el catálogo carece de desglose analítico (APUs en `$0.00`) y no hay destajistas asignados en campo, no simula costos; muestra rubros en `$0.00`, oculta la dona y despliega un aviso informativo contextual.
- **Nivelación Milimétrica**: Reglas Flexbox en Streamlit y espaciador dinámico de `59px` (o `39px`) que logran alineación inferior exacta a nivel de píxel (**0px de diferencia**).

### 4.2 `mediciones_engine.py` (Captura en Campo y Generadores)
- Entrada paramétrica con calculadoras geométricas dinámicas (`m`, `m²` rectangular/triangular/trapecio, `m³`, `kg`, `litros`, `lote`, etc.).
- Asignación opcional de trabajador destajista desde `personal_obra` e ingreso de jornadas/horas.
- Subida múltiple de fotografías y croquis (`accept_multiple_files=True`).
- Editor interactivo de generadores (`st.data_editor`) con eliminación y recálculo en tiempo real.

### 4.3 `estimaciones_engine.py` (Cortes, Raya y Telemetría)
- Apertura, edición y cierre de periodos de estimación con control de estados.
- **Módulo de Liquidación de Raya Semanal**: Calcula los montos devengados por destajista y jornales en el periodo y permite descargar el Recibo Oficial en PDF ReportLab.
- Telemetría meteorológica automatizada mediante consulta a Open-Meteo.

### 4.4 `catalogo_engine.py` y `biblioteca_engine.py` (Catálogo y Tabuladores)
- Soporte **Dual Path**: Permite capturar conceptos de forma simple (P.U. directo) o analítica (APU detallado).
- Importador masivo de Excel con normalización tolerante de encabezados (acepta variantes con o sin acentos, mayúsculas, prefijos "(Opcional)").

### 4.5 `personal_engine.py` y `proveedores_engine.py` (Directorios de Obra)
- Gestión de trabajadores activos, oficios y costos base de jornal.
- Catálogo de proveedores clasificados por giro comercial.

### 4.6 `proyectos_engine.py` (Contratos y Geocodificación)
- Alta y configuración de proyectos de obra.
- **Geocodificación OpenStreetMap / Nominatim Contextual**: Consulta primero la IP pública del usuario (`obtener_geolocalizacion_ip`, caché de 1h) para aplicar sesgo por país y cuadrante `viewbox`, con fallback global automático.

### 4.7 `admin_engine.py` y `bug_tracker.py` (Superadministración e Incidencias)
- Panel de control para roles `superadmin`: telemetría global, auditoría de tablas, inspección de buckets y gestión del ciclo de vida de tickets de soporte (`reportes_bugs`).
- **Barra Lateral Derecha (Drawer "To-Go")**: Lista interactiva de trabajo activo para el superadministrador (`Abierto`, `En Revisión`, `Corregido`, `Bajo Consideración`), permitiendo auditar, editar y dar feedback continuo a los agentes mientras navega libremente por la app. (Ver `./PROTOCOLO_BUGS.md`).

### 4.8 `excel_engine.py` y `pdf_engine.py` (Motores de Exportación)
- **Excel**: Inyección binaria OpenPyXL en formatos oficiales IMSS, Poder Judicial de la Federación (PJF) y Formato Libre Estimapp, insertando todas las fotografías y croquis en hojas de reporte.
- **PDF**: Generador ReportLab con resumen ejecutivo tri-modal, gráficas vectoriales Matplotlib y recibos de raya semanal formalmente maquetados.

### 4.9 `db_engine.py` (Conectividad y Caché)
- Políticas de caché reactiva con TTL (`ttl=60`) en consultas clave para sincronización inmediata con Supabase Cloud.
- Normalizador unificado de unidades métricas (`normalizar_unidad`).
- Compresión de imágenes Pillow y utilerías de borrado atómico multi-archivo (`extraer_nombres_archivos`).

---

## 5. Frontend y Flujo de Navegación (`app.py`)

La interfaz opera con un **Header Sticky Unificado** inyectado mediante HTML/CSS personalizado (`.sticky-header`) con altura sincronizada a las pestañas vía variable CSS `--sticky-header-height`.

### 5.1 Modo Operativo de Obra (8 Pestañas Canónicas)
1. **📊 Resumen Financiero**: Dashboard adaptativo tri-modal, KPIs en tiempo real, gráfica de dona, desglose por concepto y exportación de informe PDF.
2. **📐 Captura en Campo**: Generadores de obra, calculadora geométrica, destajos, fotos múltiples y croquis.
3. **📑 Estimaciones y Raya**: Periodos de corte, telemetría climática, liquidación de nómina de destajistas y exportación de reportes Excel / Recibo de Raya PDF.
4. **📚 Catálogo del Proyecto**: Presupuesto oficial contratado, desglose APU, importación Excel y editor de conceptos.
5. **📖 Biblioteca Maestra**: Tabuladores centrales organizados por institución con soporte APU.
6. **👷 Personal y Cuadrillas**: Directorio de operarios, cuadrillas y salarios base.
7. **🚚 Proveedores**: Directorio comercial de casas de materiales y subcontratistas.
8. **🏢 Proyectos**: Alta de contratos, geocodificación automática en mapa y configuración de sobrecostos.

### 5.2 Modo Consola de Superadministrador (`admin_engine.py`)
Accesible mediante el botón de membrete superior para usuarios con privilegios:
- **Tab 1: Auditoría de Tablas**: Métricas de registros, volúmenes de datos y salud de tablas.
- **Tab 2: Almacenamiento**: KPIs de archivos en buckets `evidencias`, `plantillas` y `bugs`.
- **Tab 3: Incidencias**: Gestión y resolución de tickets de fallas técnicas.
- **Tab 4: Usuarios**: Administración de roles (`residente`, `superadmin`) y despachos.
- **Tab 5: Telemetría**: Indicadores de rendimiento de la plataforma.

---

## 6. Políticas de Seguridad y Aislamiento (RLS)

- **Multiusuario Estricto**: Todo registro creado en el sistema está vinculado directamente a un `user_id` de `auth.users` o a una relación jerárquica con un proyecto perteneciente al usuario activo.
- **Zero-Trust Cross-Tenant**: Se tienen pruebas automatizadas de seguridad con Playwright verificando que ningún usuario regular pueda ver contratos, catálogos, mediciones ni archivos de otro residente.