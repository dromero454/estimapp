# ESTIMAPP v2.0 - REPORTE DE ESTATUS Y GUÍA PARA AGENTES FUTUROS (REPORTE #5)
**Fecha de Generación:** 14 de Octubre de 2026 (Sistema Diario de Mano de Obra, Semáforo de Desquite y Resolución Integral de BUG-008, BUG-011, BUG-013 y BUG-014)  
**Rama:** `development`  
**Autor:** Antigravity (Google DeepMind - Pair Programming con Desarrollador Principal)

---

## 1. Propósito y Resumen Ejecutivo

Este documento formaliza la resolución integral, validación automatizada y sincronización de arquitectura para el lote de tickets activos en Estimapp:
- **`BUG-014`**: Invalidación de caché (cache-busting) de miniaturas fotográficas en la Consola de Administrador.
- **`BUG-013`**: Cuadratura analítica del Dashboard (Total Acumulado vs Periodos Individuales) y erradicación del colapso tipográfico KaTeX (palabras pegadas) en alertas de semáforo.
- **`BUG-011`**: Selector de fechas de realización, edición en línea atómica y ordenamiento jerárquico a 3 niveles en Captura en Campo.
- **`BUG-008`**: Sistema Diario de Mano de Obra con Fechas Calendario, consolidación de salario diario único por fecha trabajada para personal por jornada, e instauración del **Semáforo de Desquite** (`🟢 Desquitado` vs `🔴 En déficit`) con emisión de recibos oficiales en PDF.

Adicionalmente, se actualizaron y sincronizaron los contratos maestros de especificación:
1. `data_model_v2.0.md` (Esquema relacional y columnas de PostgreSQL).
2. `especificaciones.md` (Contratos técnicos de las Tabs 1, 2 y 3).

Con estas intervenciones, **el 100% de los tickets reportados en el sistema (14 folios) se encuentran atendidos**: 9 Validados, 1 Descartado y 4 Corregidos listos para validación final por el Superadministrador.

---

## 2. Modificaciones al Modelo de Datos (PostgreSQL en Supabase Cloud)

### Tabla `mediciones_campo`
- **Columna Agregada**: `fecha DATE DEFAULT CURRENT_DATE`
- **Propósito**: Permitir el registro cronológico exacto de la fecha en que una cuadrilla o trabajador ejecutó una actividad o volumen dentro del periodo de corte de una estimación.
- **Retrocompatibilidad**: Se ejecutó un backfill masivo para poblar las filas históricas preexistentes con la fecha de su marca temporal de creación:
  ```sql
  ALTER TABLE mediciones_campo 
  ADD COLUMN IF NOT EXISTS fecha DATE DEFAULT CURRENT_DATE;

  UPDATE mediciones_campo 
  SET fecha = created_at::date 
  WHERE fecha IS NULL;
  ```
- **Índice Recomendado**: `idx_mediciones_campo_fecha` para optimizar agregaciones analíticas por fecha calendario.

---

## 3. Desglose Técnico por Incidencia Resuelta

### 🔹 BUG-014: Invalidación de Caché en Miniaturas de Evidencias (Consola de Administrador)
- **Módulos Afectados**: `modulos/drawer_tracker.py`, `modulos/admin_engine.py`
- **Causa Raíz**: 
  1. En el drawer de reporte de bugs, al pegar screenshots del portapapeles se utilizaban nombres genéricos estáticos (`screenshot_0.png`, `screenshot_1.png`). Al subir un ticket o reemplazar evidencias, la URL pública de Supabase Storage mantenía la misma ruta exacta.
  2. El navegador web y los servidores CDN de Supabase cacheaban la imagen original con encabezados `Cache-Control` prolongados, impidiendo que el Superadministrador viera las nuevas capturas subidas.
- **Solución Implementada**:
  1. **Nombres de Archivo Unívocos**: En `modulos/drawer_tracker.py` se inyectó una marca temporal en microsegundos: `screenshot_{idx}_{ts}.png`.
  2. **Token Cache-Buster Dinámico**: En `modulos/admin_engine.py`, en el renderizado de la galería de miniaturas y de imágenes en tamaño completo, se concatena el timestamp de actualización del ticket:
     ```python
     cb_token = int(time.time())
     if bug_actual.get("updated_at"):
         try:
             cb_token = int(datetime.datetime.fromisoformat(str(bug_actual["updated_at"]).replace("Z", "+00:00")).timestamp())
         except Exception:
             pass
     # url final: {img_url}?v={cb_token}
     ```
  3. Esto fuerza al navegador a refrescar la imagen inmediatamente si el ticket sufrió alguna modificación o resubida de evidencias.

---

### 🔹 BUG-013: Homologación del Dashboard y Corrección de Texto Colapsado en KaTeX
- **Módulo Afectado**: `modulos/dashboard_engine.py`
- **Causa Raíz**: 
  1. **Discrepancia en Gráfica de Dona**: Al calcular el `Total Acumulado`, la función `_calcular_df_distribucion` utilizaba un loop sobre `proy_mediciones` donde verificaba `if p_mod == "Por Jornada"`. Para personal por destajo, multiplicaba el volumen por 0.0, subestimando los destajos pagados respecto a la suma de las estimaciones individuales.
  2. **Colapso de Texto en Semáforos (KaTeX)**: En `st.error()` y `st.warning()`, al escribir `$val1) texto ($val2`, Streamlit interpreta los caracteres `$` no escapados como delimitadores de fórmulas matemáticas de LaTeX. El motor KaTeX ignora los espacios y formatea las palabras pegadas en cursiva matemática (`sobrepasaelpresupuestodemanodeobrapactado`).
- **Solución Implementada**:
  1. **Unificación Matemática de Distribución**: Se reestructuró `_calcular_df_distribucion("Total Acumulado")` para calcular matemáticamente la distribución de cada estimación individual (`_calcular_df_distribucion(est_id)`) y sumarlas vectorialmente (`Total Acumulado = Est 1 + Est 2 + ... + Est N`). Esto garantiza identidad matemática absoluta entre el desglose acumulado y las estimaciones unitarias.
  2. **Escape Preventivo de Símbolos de Dólar**: Se escaparon todos los símbolos `$` en los textos de advertencia del semáforo presupuestal: `\$ {val:,.2f}`. Con esto, Streamlit renderiza texto plano con espaciado natural e impecable tipografía.

---

### 🔹 BUG-011: Selector de Fechas de Realización y Edición en Línea en Captura de Campo
- **Módulos Afectados**: `modulos/mediciones_engine.py`, `modulos/db_engine.py`
- **Solución Implementada**:
  1. **Selector de Fecha Dinámico**: En la sección de asignación de mano de obra de Tab 2, se implementó una distribución balanceada de 3 columnas (`[1.5, 1.2, 1.0]`):
     - Columna 1: `Destajista / Trabajador responsable` (`st.selectbox`).
     - Columna 2: `Fecha de realización` (`st.date_input`), restringida dinámicamente entre el `periodo_inicio` y `periodo_fin` de la estimación activa.
     - Columna 3: `Jornadas invertidas` (`st.number_input`, visible si aplica por jornada).
  2. **Persistencia en Base de Datos**: Al capturar generadores, la fecha seleccionada se guarda en `mediciones_campo.fecha`.
  3. **Edición Directa en `st.data_editor`**: Se integró la columna `"Fecha"` (`st.column_config.DateColumn`) a la derecha de `"Destajista / Trabajador"`. Los cambios en fecha o trabajador realizados en la tabla son detectados mediante `st.session_state` y persistidos atómicamente en Supabase.
  4. **Ordenamiento Jerárquico a 3 Niveles**: El catálogo de mediciones del periodo se ordena de forma determinística por:
     `[Fecha (ascendente), Trabajador (alfabético), Clave de Concepto (alfabético)]`.

---

### 🔹 BUG-008: Sistema Diario de Mano de Obra, Consolidación de Jornadas y Semáforo de Desquite
- **Módulos Afectados**: `modulos/estimaciones_engine.py`, `modulos/pdf_engine.py`
- **Requerimiento Clave del Negocio**:
  En obras de construcción, un trabajador contratado "Por Jornada" cobra un salario diario fijo (ej. $350/día) independientemente de si realiza 1, 3 o 5 actividades distintas en ese mismo día. Anteriormente, el sistema multiplicaba el salario por cada registro, cuadruplicando falsamente el gasto de nómina.
  Además, el residente requería un mecanismo visual para saber si el trabajador "desquitó" su sueldo diario, comparando el valor de mano de obra generado en sus actividades (`sum(volumen * P.U. mano de obra)`) contra su salario pactado.
- **Solución Implementada**:
  1. **Tabla de Destajos (Superior)**:
     - Incorpora columna `"Fecha"` a la izquierda del `"Trabajador"`.
     - Ordenamiento a 3 niveles: `[Fecha, Trabajador, Clave]`.
  2. **Tabla de Jornadas y Semáforo de Desquite (Inferior)**:
     - Las actividades se agrupan por `(Fecha, Trabajador)`.
     - Para cada día de trabajo, se calcula:
       - `total_valor_dia = sum(volumen * pu_mo)`
       - `ratio_desquite = (total_valor_dia / salario_diario) * 100`
       - Si `total_valor_dia >= salario_diario` ➔ `🟢 Desquitado (X%)`
       - Si `total_valor_dia < salario_diario` ➔ `🔴 En déficit (X%)`
     - **Unificación Visual de Celdas**: El badge del semáforo y el `"Salario Diario ($)"` se renderizan **únicamente en la primera fila del día** para ese trabajador. En las actividades subsiguientes del mismo día, ambas celdas quedan vacías (`""` / `None`), consolidando visual y financieramente 1 sola jornada pagada.
  3. **Consolidación en Tarjetas KPI**:
     - `Total por Jornadas` y `Jornadas Acumuladas` cuentan exactamente 1 jornada por fecha calendario única trabajada.
  4. **Emisión de Recibos en PDF (`modulos/pdf_engine.py`)**:
     - Tabla 1 (Destajos): Se añadió la columna `Fecha`.
     - Tabla 2 (Jornadas): Se adaptó la estructura diaria con `Fecha`, `Valor M.O. Producido ($)`, `Salario D. ($)` y `Estatus`.
     - Cédula de Firmas: Consolida el monto exacto neto ganado por cada trabajador en el periodo (evitando duplicar salarios diarios) con la leyenda `"Firma de Recibido:"`.

---

### 🔹 Refinamiento Integral Post-Revisión Superadmin: Cuadratura Financiera y Restricción de Fechas

Tras la revisión del Superadministrador, se abordaron dos solicitudes de precisión técnica:

1. **Alineación Estricta de Fechas en Tab 2 (BUG-011)**:
   - **Default a `periodo_inicio`**: El selector superior `st.date_input("📅 Fecha de realización")` ahora inicializa invariablemente en la fecha de apertura de la estimación activa (`d_min`), acotado con `min_value=d_min` y `max_value=d_max`.
   - **Restricción en `st.data_editor`**: Se configuró `st.column_config.DateColumn("Fecha", min_value=d_min, max_value=d_max, default=d_min)`, bloqueando la selección de fechas fuera del periodo en la tabla.
   - **Sanitización de Datos Históricos**: Las filas cargadas y el manejador de guardado inline restringen automáticamente cualquier fecha previa o editada al intervalo estricto `[periodo_inicio, periodo_fin]`.

2. **Resolución de Discrepancia Financiera ($2,685.00 vs $3,185.00 en BUG-013)**:
   - **Causa Raíz**: En Tab 3, un trabajador por jornada que realizó 2 actividades en la misma fecha recibió 1 salario diario de $500.00 MXN ($2,185 destajos + $500 jornada = $2,685.00). Sin embargo, el Dashboard sumaba ciegamente cada registro individual ($500 + $500 = $1,000), resultando en $3,185.00 MXN ($500 pesos duplicados).
   - **Corrección en Cascada**: Se sincronizó la consolidación diaria `(e_id, fecha, id_personal)` en `modulos/dashboard_engine.py`:
     - *Mano de Obra (Dona y Tabla)*: Bajó a **$2,685.00 MXN** (paridad 1:1 absoluta con Tab 3).
     - *Gasto Erogado Real (Tarjeta 3)*: Bajó de $32,311.10 a **$31,811.10 MXN**.
     - *Utilidad Bruta Real (Tarjeta 4)*: Aumentó de $4,018.20 a **$4,518.20 MXN**.
     - *Margen Real (Tarjeta 5)*: Subió de 11.1% a **12.4%**.

3. **Depuración de Interfaz en Tab 2 (Captura en Campo)**:
   - **Eliminación del Widget de Jornadas**: Se removió el selector manual de jornadas y la columna `"Jornadas"` en `st.data_editor`, simplificando la UI a un layout simétrico 50/50 (`👷 Destajista / Trabajador responsable` y `📅 Fecha de realización`).
   - **Preservación No Destructiva de la BD**: La columna `horas_o_jornales` en la tabla `mediciones_campo` de Supabase se preservó intacta (con default backend silencioso `1.0`) para mantener la integridad relacional y estabilidad histórica sin requerir DDL destructivo.

4. **Integración del KPI "Mano de Obra sin Asignar" en Tab 3 (Estimaciones y Pagos)**:
   - **Ingeniería de Costos y Flexibilidad Operativa**: Para evitar que mediciones capturadas sin trabajador asignado simulen un abaratamiento artificial de la obra, se incorporó el KPI `"Mano de Obra sin Asignar"` entre *Total por Jornadas* y *Jornadas Acumuladas*.
   - **Cuadratura 1:1 Inmaculada**: Al sumar Destajos ($2,061.80) + Jornadas ($500.00) + M.O. sin Asignar ($2,000.00) = **$4,561.80 MXN** en la Estimación #2, logrando correspondencia matemática exacta con los **$4,561.80 MXN** que muestra el Dashboard.
   - **Tooltip Interactivo y Aviso Contextual**: Se incluyó un tooltip explicativo y un banner informativo que orienta al usuario para vincular al personal en Captura de Campo cuando desee reflejarlo en la nómina liquidable.

5. **Contenedor Dedicado "Semáforo Inteligente" y Conciliación Financiera en Tab 1 (Dashboard)**:
   - **Layout Dual Superior**: Se reemplazó el contenedor único por dos bloques paralelos:
     - *Izquierda (60%)*: `🏛️ Resumen Global del Proyecto` con KPIs ordenados en dos niveles (Presupuesto Pactado, Gasto Reportable, Gasto Erogado Real, Utilidad Bruta Real y Margen Real).
     - *Derecha (40%)*: `🚦 Semáforo Inteligente` con panel unificado de 5 vectores de control en tiempo real (Techo Presupuestal Global, Mano de Obra, Conceptos con Sobregiro Físico > 100%, Insumos/Materiales y Erosión de Margen).
   - **Resolución de la Paradoja Presupuestal**:
     - *Gasto Erogado Real*: Su delta advierte explícitamente en rojo cuando rebasa el contrato original (`+$16,804.25 sobre pactado`).
     - *Utilidad Bruta Real*: Explicita mediante subetiqueta que el margen de $10,353.19 (11.9%) es operativo sobre el volumen cuantificado y está `Sujeta a adenda ($27,157.44 excedente)` para formalizarse como ganancia líquida ante el cliente.

---

## 4. Verificación Automatizada y Evidencias Visuales

Se ejecutaron tres rondas de validación automatizada mediante Playwright en modo Headless:
1. **Dashboard y Semáforo Inteligente (Tab 1)**: Se verificó la disposición visual en dos contenedores paralelos, la ausencia de caracteres de escape y las 5 alertas en tiempo real (`scratch/screenshots_verification_oct14_round3/01_tab1_semaforo_inteligente_clean.png`).
2. **Barra de 5 KPIs y Liquidación (Tab 3)**: Se confirmó la presencia del KPI *Mano de Obra sin Asignar* con tooltip, el cálculo de jornadas consolidadas y las tablas de destajos y desquite (`scratch/screenshots_verification_oct14_round3/02_tab3_5_kpis_centrado.png`).
3. **Captura en Campo (Tab 2)**: Se validó el layout 50/50 y la columna *Fecha* dentro de los límites del periodo (`scratch/screenshots_verification_oct14_round2/02_tab2_table_scrolled.png`).

---

## 5. Matriz de Estado Actual del Repositorio de Bugs

| Folio | Categoría | Estado | Resumen de Resolución |
|---|---|---|---|
| `BUG-001` | Interfaz y Visualización | **Validado** | Ajuste fino del drawer y layout |
| `BUG-002` | Interfaz y Visualización | **Validado** | Alineación del formulario de incidencias |
| `BUG-003` | Interfaz y Visualización | **Validado** | Estabilidad del sticky header |
| `BUG-004` | Cálculos y Fórmulas | **Validado** | Normalización de unidades en presupuesto |
| `BUG-005` | Cálculos y Fórmulas | **Descartado** | Descartado por Superadmin (duplicado/fuera de alcance) |
| `BUG-006` | Otro | **Validado** | Giro dinámico "Otros" en proveedores |
| `BUG-007` | Cálculos y Fórmulas | **Validado** | Consecutivos y texto no técnico en baja de personal |
| `BUG-008` | Cálculos y Fórmulas | **Corregido** | Sistema diario de M.O., semáforo de desquite, KPI "Mano de Obra sin Asignar" y cuadratura 1:1 |
| `BUG-009` | Exportación de Archivos | **Validado** | Sanitización NaN en importador Excel y categoría en tracker |
| `BUG-010` | Interfaz y Visualización | **Validado** | Selector de periodo en panel de telemetría |
| `BUG-011` | Cálculos y Fórmulas | **Validado** | Validado por Superadmin (fechas [inicio, fin] y editor inline en Tab 2) |
| `BUG-012` | Interfaz y Visualización | **Validado** | Cierre seguro del Drawer al cambiar de pestaña |
| `BUG-013` | Cálculos y Fórmulas | **Corregido** | Contenedor dedicado "Semáforo Inteligente" con 5 vectores y resolución de paradoja presupuestal |
| `BUG-014` | Interfaz y Visualización | **Validado** | Validado por Superadmin (cache-busting de miniaturas en consola admin) |

### 5.4 Perfeccionamiento Visual de Tab 1: Resumen Global de Ancho Completo y Semáforo Dinámico en Tabla

#### 1. Diagnóstico y Nueva Arquitectura Visual
Tras evaluar la disposición previa en dos columnas paralelas (`col_resumen` y `col_semaforo`), el desarrollador determinó que el contenedor de `Resumen Global del Proyecto` posee un atractivo visual superior cuando abarca el **100% del ancho del viewport**, permitiendo presentar los 5 KPIs alineados horizontalmente sin saturación visual.
Para preservar todas las alertas financieras inteligentes sin duplicar bloques, se condensaron los 5 vectores del semáforo directamente dentro de una nueva columna denominada **`Estatus`** en la tabla del contenedor `Distribución de Costos y Margen del Despacho`, logrando reactividad temporal instantánea al interactuar con el selector de estimaciones.

#### 2. Matriz de Umbrales y Lógica del Semáforo Condensado en Tabla (`Estatus`) - Opción 1 Implementada
Se unificaron las leyendas a estados universales, legibles e inmediatos, incorporando la cifra base presupuestada o porcentaje meta entre paréntesis como referencia directa:

| Rubro Financiero | Base Contractual / Meta | Leyenda de Estado (`Estatus`) | Condición de Activación |
| :--- | :--- | :--- | :--- |
| **Materiales** | Costo Base Contractual (`proy_mat_presupuestado`) | `🔴 Excedido (Presup: $XX,XXX.XX)`<br>`🟢 En rango (Presup: $XX,XXX.XX)` | Acumulado > Costo Base<br>Acumulado ≤ Costo Base |
| **Mano de Obra / Destajos** | Presupuesto Pactado (`proy_mo_presupuestada`) | `🔴 Excedido (Presup: $XX,XXX.XX)`<br>`🟢 En rango (Presup: $XX,XXX.XX)` | Acumulado > Presupuesto Pactado<br>Acumulado ≤ Presupuesto Pactado |
| **Herramienta y Equipo** | % Objetivo del Proyecto (`pct_herr_proy`) | `🔴 Excedido (Meta: X.X%)`<br>`🟢 En rango (Meta: ≤ X.X%)` | % Actual > Meta del proyecto<br>% Actual ≤ Meta del proyecto |
| **Gastos Indirectos** | % Objetivo del Proyecto (`pct_ind_proy`) | `🔴 Excedido (Meta: X.X%)`<br>`🟢 En rango (Meta: ≤ X.X%)` | % Actual > Meta del proyecto<br>% Actual ≤ Meta del proyecto |
| **Margen de Utilidad** | Margen Objetivo del Proyecto (`pct_util_proy`) | `🔴 Pérdida (X.X%)`<br>`🟡 Bajo meta (Meta: X.X%)`<br>`🟢 En meta (Meta: ≥ X.X%)` | Margen < 0% (Déficit)<br>0% ≤ Margen < Meta del proyecto<br>Margen ≥ Meta del proyecto |

#### 3. Actualización de Deltas en KPIs de Cabecera y Solución de Iconografía SVG
1. **Gasto Reportable**: Incorporación de delta diferencial respecto al Presupuesto Pactado (`monto_estimado_global - monto_contratado_total`). Si existe excedente, se resalta en **ROJO** (`delta_color="inverse"`: `↑ +$27,157.44 sobre pactado`).
2. **Gasto Erogado Real**: Inversión de paleta (`delta_color="inverse"`), advirtiendo en **ROJO** el sobregiro real respecto al techo contratado (`↑ +$16,804.25 sobre pactado`).
3. **Margen Real (Tricolor Inteligente con Flechas SVG y Amarillo Idéntico a Advertencia)**:
   - **Rojo**: Si el margen es estrictamente negativo (< 0%). Flecha hacia abajo `↓`.
   - **Amarillo/Ámbar Exacto**: Si el margen es positivo pero inferior a la meta del proyecto (ej. 11.9% vs 15.0% meta). Utiliza exactamente la paleta de `st.warning()`: fondo pastel `rgba(255, 255, 18, 0.25)` y texto marrón/ámbar `rgb(146, 108, 5)` (`#926C05`).
   - **Verde**: Si el margen iguala o supera la meta contractual. Flecha hacia arriba `↑`.
   - **Corrección de Cuadro Negro en Iconos SVG**: En Streamlit, los íconos de delta poseen dos nodos `<path>`: el primero es un rectángulo invisible de 24x24 (`fill="none"`) y el segundo es la flecha. Se corrigió la regla CSS utilizando `path:first-child { fill: none !important; }` y `path:last-child { fill: currentColor !important; }`, erradicando el cuadro sólido opaco y mostrando una flecha nítida hacia abajo (`↓`) o arriba (`↑`).
4. **Banner Inferior Compacto de Conceptos Sobregirados**:
   - Preserva el formato nativo Streamlit (`st.warning()`) al fondo del contenedor global con redacción limpia y sin saturar claves individuales:
     `⚠️ 2 Conceptos Sobregirados, revisa la sección de Desglose por Estimación y Concepto para obtener más detalles.`

### 5.5 Integración del IVA: 6º KPI en Cabecera y Barra de Liquidación Fiscal (Opción B)
1. **Desacople Estratégico de la Dona**:
   - La gráfica de dona interactiva se preserva **estrictamente al 100% del costo operativo interno** (`Materiales` + `Mano de Obra` + `Herramienta` + `Indirectos` + `Utilidad`), evitando distorsiones por impuestos de paso.
2. **6º KPI en Resumen Global (`Total con I.V.A.`)**:
   - Ubicado estratégicamente entre *Presupuesto Pactado* (Col 1) y *Gasto Reportable* (Col 3).
   - Muestra el monto total facturable acumulado con IVA (`$100,597.05`).
   - Delta dinámico inteligente: si el proyecto tiene IVA configurado muestra `+$13,875.46 (16.0% IVA)` en gris neutro; si la tasa es 0% o nula, indica `⚪ Sin IVA aplicable (0%)`.
   - Selector CSS ajustado a `:nth-child(6)` para que el KPI de *Margen Real* conserve su alineación y pastilla ámbar/amarilla warning con flecha SVG.
3. **Barra de Liquidación Contable/Fiscal al Pie de la Tabla**:
   - Ubicada inmediatamente debajo de la tabla en el contenedor de distribución, tanto para modalidad `privada` como `mixta`.
   - Se actualiza reactivamente al cambiar el selectbox (*Total Acumulado*, *Estimación #1*, *Estimación #2*, etc.), desglosando en una cinta de diseño sutil:
     `🏷️ Subtotal: $XX,XXX.XX` | `🏛️ IVA: +$X,XXX.XX (X.X%)` | `💳 Total c/IVA: $XX,XXX.XX`.

### 5.6 Tab de Proyectos: Integración de los 4 Factores Financieros en Tabla Editable y Tooltips Objetivo
1. **Tooltips del Formulario de Alta de Proyectos**:
   - Se actualizaron los textos de ayuda (`help=...`) de los cuatro factores financieros (`% Indirectos`, `% Utilidad`, `% Herramienta`, `% IVA`) para clarificar explícitamente que son **valores objetivo** para el control financiero, la fijación de metas operativas y la facturación de estimaciones.
2. **Edición en Celda de los 4 Factores en `st.data_editor`**:
   - Se incorporaron las 4 columnas en el orden exacto del formulario:
     `% Indirectos` $\rightarrow$ `% Utilidad` $\rightarrow$ `% Herramienta` $\rightarrow$ `% IVA`.
   - Todas cuentan con formato porcentual (`%.2f%%`), paso de `0.5%` y valor mínimo de `0.0%`.
   - El bucle de guardado atómico detecta cambios en cualquiera de los 4 factores, persiste en `proyectos` e invalida la caché `get_proyectos_cache_fn.clear()`, sincronizando instantáneamente las metas y cálculos en el **Resumen Financiero (Tab 1)**.

---

## 6. Recomendaciones para el Superadministrador y Agentes Futuros

1. **Revisión y Aprobación Final de Tickets**:
   El Superadministrador puede acceder a la Consola de Administrador (`Tab 5: Consola de Incidencias`), verificar los dos tickets finales (`BUG-008` y `BUG-013`) en estado `'Corregido'` y, tras su conformidad con las pantallas auditadas, promoverlos a `'Validado'`. Con ello se alcanzará el **100% de tickets validados/cerrados** en la plataforma.
2. **Inviolabilidad de RLS**:
   Cualquier consulta nueva sobre `mediciones_campo` o `personal_obra` debe incluir el filtrado explícito por `user_id` o pertenencia del proyecto a la sesión activa.
3. **Mantenimiento de KaTeX y HTML**:
   Al redactar cadenas de texto dinámicas para `st.markdown()`, si se utilizan etiquetas HTML con `unsafe_allow_html=True`, los símbolos de moneda `$` no deben ser escapados con `\$`, ya que el navegador los renderizará literalmente.
