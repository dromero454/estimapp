# PROTOCOLO INTEGRAL DE GESTIÓN Y RESOLUCIÓN AGÉNTICA DE BUGS (ESTIMAPP)

---

## 1. Filosofía y Propósito del Sistema de Calidad
Estimapp cuenta con un sistema simbiótico de **Control de Calidad (QA), Telemetría y Resolución Continua de Incidencias** diseñado para operar entre el **Desarrollador / Superadministrador** (criterio humano y de negocio) y los **Agentes de Inteligencia Artificial** (inspección de código, parches de software y validación automatizada).

El Bug Tracker no es un repositorio pasivo de quejas; es un motor vivo integrado en la misma aplicación que permite auditar fallos, adjuntar evidencias (archivos tradicionales o capturas del portapapeles con `Ctrl + V`), ejecutar diagnósticos técnicos y validar soluciones en tiempo real sin salir del flujo de trabajo.

---

## 2. Matriz Oficial de Estados y Niveles de Autoridad

La tabla `public.reportes_bugs` cuenta con una restricción estricta en Postgres (`reportes_bugs_estado_check`) que admite exactamente seis estados oficiales de ciclo de vida:

| Estado | Color / Distintivo | Asignado por | Propósito y Regla de Negocio |
| :--- | :---: | :---: | :--- |
| **`Abierto`** | 🔴 Rojo | Usuario / Admin | Incidencia nueva reportada desde cualquier módulo de la aplicación. |
| **`En Revisión`** | 🟡 Amarillo | **Exclusivo Superadmin** | El Superadmin probó la solución, detectó fallos o requiere ajustes, y devuelve el ticket al agente con observaciones en `comentarios_revision`. |
| **`Corregido`** | 🟢 Verde | **Exclusivo Agente IA** | El agente analizó la causa raíz, implementó el parche de código, validó con Playwright y redactó la bitácora técnica en `notas_resolucion`. |
| **`Bajo Consideración`** | 🟠 Naranja | **Agente o Superadmin** | **Pausa Analítica y Triaje**: Reportes ambiguos, dañinos, anti-patrones de obra o fuera de alcance que requieren dictamen humano antes de codificar. |
| **`Validado`** | 🔵 Azul | **EXCLUSIVO Superadmin** | La corrección fue probada en vivo por el Superadmin y aprobada con 100% de satisfacción. **El agente NUNCA puede auto-marcar un ticket como Validado**. |
| **`Descartado`** | 🟣 Morado / Gris | **EXCLUSIVO Superadmin** | El reporte fue rechazado definitivamente (no procede, duplicado o descartado tras estar `Bajo Consideración`). |

---

## 3. Protocolo de Triaje Agéntico (Paso 0 Obligatorio para el Agente)

Cuando el desarrollador indique: *"Resuelve los bugs abiertos"* o *"Revisa los tickets pendientes"*, o variaciones de las frases anteriores, el agente **DEBE ejecutar obligatoriamente una fase previa de triaje antes de redactar código o planes de trabajo**.

### 3.1 Criterios Heurísticos para marcar o proponer `Bajo Consideración`:
1. **Ambigüedad Crítica / Ininteligible**:
   - Descripciones vacías, de una sola frase vaga (*"no jala la tabla"*, *"se ve raro"*) sin pasos para reproducir ni capturas de pantalla adjuntas.
2. **Anti-Patrones Contables y de Obra**:
   - Peticiones de usuarios que buscan "comodidad" a costa de destruir la disciplina del negocio:
     - Captura de importes o rendimientos negativos en la Raya.
     - Modificación directa de volúmenes contratados desde la captura de campo (violación del catálogo contractual).
     - Fechas de estimación o generador anteriores a la fecha de inicio del contrato.
3. **Riesgos de Arquitectura, Rendimiento o Seguridad**:
   - Eliminación de alertas de confirmación en cascada.
   - Peticiones de descargas masivas desmedidas que saturen la memoria de Streamlit.
   - Cualquier intento de saltarse el aislamiento de datos (RLS) o controles de sesión.
4. **"Feature Creep" y Peticiones Fuera de Alcance**:
   - Solicitudes que confunden el Bug Tracker con módulos ajenos a Estimapp (ej. timbrado fiscal ante el SAT, modelado BIM 3D, cálculos estructurales).
5. **Violación a la Ley de Obras Públicas**:
   - Peticiones para alterar fórmulas normativas de amortización de anticipo o retenciones de fondo de garantía.

### 3.2 Formato del Reporte de Triaje Inicial del Agente:
Antes de presentar el plan técnico de solución, el agente debe abrir su intervención alertando al desarrollador:
```markdown
### ⚠️ Alerta de Triaje de Incidencias:
He auditado los tickets entrantes y propongo pausar los siguientes en **`Bajo Consideración`**:
- **`BUG-XXX`**: [Motivo concreto: ambigüedad crítica, anti-patrón de obra, etc.]

Procedo a estructurar y ejecutar el plan de trabajo únicamente para los tickets válidos:
- **`BUG-YYY`**: [Descripción técnica del plan...]
```

---

## 4. La Barra Lateral Derecha de Seguimiento (Drawer "To-Go")

La barra lateral derecha es la **Lista de To-Do Activa** del Superadministrador dentro de la aplicación principal:

1. **Filtro Exclusivo de Trabajo Activo**:
   - Solo extrae tickets en estados: `Abierto`, `En Revisión`, `Corregido` y `Bajo Consideración`.
   - Los tickets `Validado` y `Descartado` salen automáticamente del Drawer para mantener la lista limpia y enfocada.
2. **Estado "Todo al Día"**:
   - Si no existen tickets en dichos cuatro estados, el Drawer despliega el banner minimalista:
     `🎉 ¡Todo al día! No hay tickets pendientes de revisión o resolución en este momento.`
3. **Regla de Oro Arquitectónica**:
   - En [app.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/app.py), `render_bug_tracking_drawer()` DEBE residir siempre al **final del archivo** (después de las 8 pestañas).
   - Esto blinda los índices delta de Streamlit (`st.tabs`), evitando que las pestañas parpadeen o se dupliquen verticalmente al abrir o cerrar el panel.
4. **Transición Suave**:
   - Las animaciones de entrada (`drawerSlideIn`) y salida (`translateX(100%)`) deben ejecutarse en 0.22s - 0.25s con curvas cúbicas sin usar `display: none` precipitado.

---

## 5. Reglas de Backend, Base de Datos y Storage (Cero Huérfanos)

1. **Identificadores y Folios**:
   - Folio estrictamente correlativo (`BUG-001`, `BUG-002`, ...). La función `compactar_y_sincronizar_folios_bugs()` en [modulos/admin_engine.py](file:///c:/Users/disco/OneDrive/Escritorio/estimapp/modulos/admin_engine.py) garantiza la correlatividad sin saltos ante eliminaciones.
2. **Estructura en Storage (`bugs`)**:
   - Todas las evidencias residen en el bucket `bugs` bajo la ruta relativa `{folio}/{nombre_archivo}`.
3. **Regla de Purga Automática Previa (Inviolable)**:
   - Si un ticket recibe nuevas evidencias o capturas del portapapeles durante una actualización, el sistema debe **eliminar primero de Storage todos los archivos previos** del ticket antes de subir los nuevos.
   - Se prohíbe dejar archivos en Storage que no figuren en la columna `archivos_adjuntos` de la base de datos (0 huérfanos).
4. **Preservación de Bitácora**:
   - `notas_resolucion`: Bitácora técnica del agente (causa raíz, módulos alterados, decisiones técnicas).
   - `comentarios_revision`: Bitácora del Superadmin (observaciones, feedback humano, validación).
   - Ambas columnas deben preservarse y actualizarse concurrentemente junto al timestamp `updated_at`.

---

## 6. Protocolo de Pruebas Automatizadas E2E (Playwright)

Ningún agente puede marcar un ticket como `Corregido` sin haber cumplido el siguiente ciclo:
1. **Reproducción del Fallo**: Identificar el comportamiento erróneo mediante inspección de código y/o reproducción automatizada.
2. **Aplicación del Parche**: Modificar los archivos modulares correspondientes respetando las directrices de `AGENTS.md`.
3. **Prueba E2E con Playwright**:
   - Ejecutar un script en `./scratch/` con Playwright Headless utilizando las credenciales de `secrets.toml`.
   - Validar que la interfaz responde correctamente, que el conteo de pestañas (`div[role="tablist"]`) es exactamente 1 (sin duplicidad) y que el flujo de usuario es exitoso.
4. **Actualización del Registro**: Pasar el ticket a `'Corregido'` en `public.reportes_bugs`, documentar la bitácora técnica en `notas_resolucion` y registrar el timestamp actual.
