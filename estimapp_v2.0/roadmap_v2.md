# ESTIMAPP v2.0 - Plan Técnico de Migración y Roadmap de Implementación

Este documento contiene la hoja de ruta exhaustiva y secuencial para que un agente autónomo (basado en **Gemini Flash 3.8 en Antigravity**) actualice la plataforma de la versión **1.0** a la versión **2.0** sin regresiones, preservando la compatibilidad con obras públicas y adoptando las capacidades de obra privada, mixta, destajos, APU y telemetría climática.

---

## 1. Principios de Ejecución y Reglas Arquitectónicas de AGENTS.md

Antes de iniciar cualquier modificación, el agente DEBE tener presentes las siguientes restricciones del entorno:

1. **Header Sticky Unificado (Inviolable):**
   * El membrete superior reside en un bloque HTML con clase `.sticky-header` (`top: 0`).
   * La barra de pestañas (`tablist`) se ubica en `top: calc(var(--sticky-header-height, 98px) - 2px)`.
   * **NUNCA alterar la inyección del header ni intentar renderizar pestañas condicionales o dinámicas.**
2. **Las 8 Pestañas Universales Fijas:**
   * La barra de pestañas SIEMPRE muestra las 8 pestañas en el orden estricto de izquierda a derecha:
     `[1. Resumen Fin.]` `[2. Captura Campo]` `[3. Estimaciones/Raya]` `[4. Catálogo]` `[5. Biblioteca]` `[6. Personal]` `[7. Proveedores]` `[8. Proyectos]`
3. **Compatibilidad Hacia Atrás (Zero Breaking Changes para v1.0):**
   * Si un proyecto existente tiene `modalidad = 'publica'`, la aplicación debe comportarse de forma idéntica a la v1.0. Las nuevas funcionalidades (APU desglosado, asignación a destajistas, hitos) son estrictamente optativas o aditivas.
4. **Normalización de Unidades:**
   * Toda manipulación de unidades en catálogos y mediciones DEBE utilizar obligatoriamente `normalizar_unidad()` de `./modulos/db_engine.py`.
5. **Ciclo de Formularios y Estados en Streamlit:**
   * Para evitar reseteos involuntarios o colisiones de widgets, usar claves únicas (`key=f"destajista_sel_{id}"`) y el patrón de reinicio dinámico mediante `st.session_state.counter_key += 1`.
6. **Inserciones en Supabase:**
   * La columna `importe` en `public.insumos_concepto` es un campo calculado `STORED`. NUNCA incluirlo en el payload de un `insert()` o `update()`.

---

## 2. Mapa de Módulos Afectados en el Repositorio

```
estimapp/
├── app.py                      # Definición de pestañas (agregar Tab 6 y Tab 7)
├── especificaciones.md         # Actualización de schemas y especificación funcional
├── supabase_migration_v2.sql   # Script DDL definitivo para ejecución en Supabase
└── modulos/
    ├── admin_engine.py         # Actualizar purga defensiva y vaciado seguro
    ├── biblioteca_engine.py    # Incorporar Dual Path (costos directos base)
    ├── catalogo_engine.py      # Incorporar Dual Path + % Utilidad por concepto + Excel
    ├── dashboard_engine.py     # Renderizar KPIs contractuales vs margen real
    ├── db_engine.py            # Adaptadores de consulta, RLS y normalización
    ├── estimaciones_engine.py  # Fechas libres (N días), liquidación de raya y Open-Meteo
    ├── mediciones_engine.py    # Selector opcional de destajista y registro de horas
    ├── personal_engine.py      # [NUEVO] CRUD de Personal y Cuadrillas (Tab 6)
    ├── proyectos_engine.py     # Modalidades, factores globales y Nominatim OSM (Tab 8)
    └── proveedores_engine.py   # [NUEVO] CRUD de Proveedores Comerciales (Tab 7)
```

---

## 3. Hoja de Ruta por Etapas (Roadmap Secuencial)

```
[ ETAPA 1: SUPABASE & DDL ]
           │
           ▼
[ ETAPA 2: DIRECTORIOS & GEODATOS ] (Tab 6, Tab 7 y Tab 8)
           │
           ▼
[ ETAPA 3: DUAL PATH EN CATÁLOGOS ] (Tab 4 y Tab 5)
           │
           ▼
[ ETAPA 4: DESTAJOS, RAYA Y DASHBOARD ] (Tab 2, Tab 3 y Tab 1)
```

---

### ETAPA 1: Estructura de Base de Datos, Relaciones y Salvaguardas en Supabase

#### Objetivo
Crear y extender el esquema en Supabase sin afectar datos existentes, garantizando llaves foráneas defensivas, aislamiento por RLS y actualización de la consola de administración.

#### Tareas Técnicas
1. **Ejecución DDL:** Ejecutar el script `supabase_migration_v2.sql` a través del servidor MCP de Supabase (`supabase-db`).
2. **Verificación de RLS:** Comprobar que las 5 tablas nuevas (`proveedores`, `personal_obra`, `insumos_concepto`, `hitos_cobro`, `telemetria_clima`) tengan RLS activado y políticas basadas en `auth.uid() = user_id` o pertenencia del proyecto.
3. **Consola de Purga Segura (`modulos/admin_engine.py`):**
   * Incorporar `personal_obra`, `proveedores` e `insumos_concepto` a las opciones de vaciado.
   * Mantener la salvaguarda obligatoria: confirmación con la palabra `"CONFIRMAR"` y cláusula estricta `WHERE id IS NOT NULL`.

#### Definition of Done (DoD)
- [ ] Tablas y columnas creadas en Supabase sin errores de tipo.
- [ ] Vista `v_telemetria_rendimientos_ml` disponible para consultas.
- [ ] Función de purga en `admin_engine.py` actualizada y verificada con tests aislados.

---

### ETAPA 2: Directorios Maestros y Georreferenciación en Proyectos

#### Objetivo
Implementar las pestañas satélite de gestión transversal (`Personal` y `Proveedores`) y extender la configuración de obras en la `Tab 8`.

#### Tareas Técnicas
1. **Pestaña 6: Personal y Cuadrillas (`modulos/personal_engine.py`):**
   * Crear módulo con formulario de alta: Nombre completo, Especialidad (`Albañilería`, `Fierrero`, `Pintura`, `Plomería`, `Electricidad`, `Peón`, `Otro`), Costo Jornal Base ($) y Teléfono.
   * Tabla interactiva con `st.data_editor` para edición directa de tarifas.
   * Filtro por especialidad y búsqueda por nombre.
2. **Pestaña 7: Proveedores Comerciales (`modulos/proveedores_engine.py`):**
   * Crear módulo con formulario de alta: Nombre Comercial, Contacto, Teléfono y Giro (`Materiales`, `Fletes / Retiro`, `Acabados`, `Maquinaria`, `Otros`).
   * Visualizador en tabla con capacidades de búsqueda y edición rápida.
3. **Pestaña 8: Proyectos (`modulos/proyectos_engine.py`):**
   * Agregar selector de `modalidad`: `Obra Pública`, `Obra Privada` o `Mixta / Integral`.
   * Agregar campos numéricos para factores financieros: `% Indirectos` (def. 15%), `% Utilidad` (def. 15%), `% Herramienta` (def. 5%) y `% IVA` (def. 16%).
   * **Integración Geográfica Nominatim (OSM):**
     * Campo `st.text_input` para ingresar dirección o cruce de calles.
     * Botón explícito `st.button("🔍 Buscar Dirección")` (NUNCA en callback automático para respetar la cuota de 1 req/s).
     * Solicitud HTTP con cabecera `User-Agent: Estimapp/2.0`.
     * Extracción y autocompletado en campos ocultos/editables de: `pais`, `estado`, `municipio`, `codigo_postal`, `latitud` y `longitud`.
4. **Integración en `app.py`:**
   * Declarar formalmente las 8 pestañas en `st.tabs()` y llamar a sus respectivos motores.

#### Definition of Done (DoD)
- [ ] Alta, edición y lectura de trabajadores y proveedores funcionando.
- [ ] Búsqueda geográfica en Nominatim resuelve coordenadas y desglosa municipio/estado sin bloquear la app si la red falla.
- [ ] Proyectos nuevos guardan modalidad y factores globales.

---

### ETAPA 3: Dual Path en Catálogo del Proyecto y Biblioteca Maestra

#### Objetivo
Permitir el ingreso de conceptos tanto a precio unitario cerrado como desglosado por costos directos (Material, Mano de Obra, Herramienta, Indirectos), permitiendo márgenes de utilidad granulares por concepto.

#### Tareas Técnicas
1. **Pestaña 5: Biblioteca Maestra (`modulos/biblioteca_engine.py`):**
   * Formulario con expander opcional: *"Desglose Analítico de Costo Directo"*.
   * Si el usuario llena Material, Mano de Obra, Herramienta e Indirectos, el sistema calcula la suma y sugiere el `precio_referencial`.
   * En biblioteca NO se almacena utilidad (la utilidad es propiedad de la obra).
2. **Pestaña 4: Catálogo de Proyecto (`modulos/catalogo_engine.py`):**
   * Alta manual con Dual Path:
     * *Camino 1:* Ingreso directo de `precio_unitario`.
     * *Camino 2:* Desglose analítico + factor de utilidad. El campo `% Utilidad` toma por defecto el valor del proyecto (`p.porcentaje_utilidad`), pero es editable por concepto.
   * `st.data_editor`: Exponer las columnas de desglose y utilidad para edición rápida en celda.
   * **Importador Excel:** Actualizar la plantilla descargable con columnas opcionales (`Costo Material`, `Costo MdeO`, `Costo Herr`, `Costo Ind`, `% Utilidad`). Si vienen vacías, el importador asigna el P.U. tradicional sin romper el catálogo.

#### Definition of Done (DoD)
- [ ] Conceptos con precio cerrado se guardan y leen correctamente (compatibilidad v1.0).
- [ ] Conceptos analíticos calculan reactivamente el precio unitario y persisten el desglose.
- [ ] Importación y exportación de plantillas Excel funcionando en ambos modos.

---

### ETAPA 4: Destajos en Campo, Cortes de N Días Libres y Dashboard Financiero Adaptativo

#### Objetivo
Vincular el avance de campo con la nómina de destajistas, habilitar cortes temporales con telemetría meteorológica y desplegar el balance financiero integral.

#### Tareas Técnicas
1. **Pestaña 2: Captura en Campo (`modulos/mediciones_engine.py`):**
   * Inyectar selector desplegable opcional: `👷 Destajista / Cuadrilla responsable` (poblado desde `public.personal_obra`).
   * Campo numérico opcional: `Horas o Jornales invertidos` (default 1.0).
   * Guardar `id_personal` y `horas_o_jornales` en `public.mediciones_campo`.
2. **Pestaña 3: Estimaciones y Raya (`modulos/estimaciones_engine.py`):**
   * Reemplazar validaciones rígidas de semanas fijas por `st.date_input` libre (`periodo_inicio` y `periodo_fin` sin restricción de días).
   * **Subpanel "Liquidación de Raya Semanal":**
     * Tabla agregada por trabajador: agrupa las mediciones del periodo asignadas a cada destajista.
     * Cálculo de raya: `Jornales × Tarifa Base` o `Volumen × Tarifa Destajo`.
     * Botón para exportar recibo de raya en PDF o formato para imprimir.
   * **Telemetría Climática Silenciosa:**
     * Al registrar o cerrar una estimación, si el proyecto tiene `latitud` y `longitud` válidas, ejecutar llamada HTTP a `archive-api.open-meteo.com` (o API de pronóstico si las fechas son recientes).
     * Insertar promedios en `public.telemetria_clima`.
     * **Seguridad:** Envolver en `try/except` silencioso; si Open-Meteo no responde o no hay internet, la estimación se guarda con éxito sin interrumpir al usuario.
3. **Pestaña 1: Resumen Financiero (`modulos/dashboard_engine.py`):**
   * Detectar la `modalidad` del proyecto activo:
     * `publica`: Mostrar tarjetas contractuales (Presupuesto contratado vs Estimado acumulado vs Saldo por estimar vs % Avance físico).
     * `privada`: Mostrar tarjetas operativas (Presupuesto contratado vs Gasto erogado real en destajos y materiales vs Margen bruto vs % Utilidad real) y gráfica de distribución de costos.
     * `mixta`: Mostrar dos columnas: Bloque Contractual Oficial y Bloque Operativo de Rentabilidad Interna.

#### Definition of Done (DoD)
- [ ] Mediciones en campo se asocian opcionalmente a un destajista sin romper el flujo estándar.
- [ ] La pestaña 3 liquida la raya semanal por trabajador en periodos con duración de días libre.
- [ ] Telemetría climática almacena datos cuando hay coordenadas disponibles sin generar fallos si el servicio está inaccesible.
- [ ] Dashboard financiero refleja métricas coherentes según la modalidad del proyecto.
