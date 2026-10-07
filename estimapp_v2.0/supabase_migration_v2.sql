-- ============================================================================
-- ESTIMAPP v2.0 - SCRIPT DE MIGRACIÓN DDL PARA SUPABASE
-- ============================================================================

-- 1. EXTENSIÓN DE LA TABLA 'proyectos' (Geodatos Libres y Factores de Costo)
ALTER TABLE public.proyectos 
    ADD COLUMN IF NOT EXISTS modalidad TEXT DEFAULT 'publica' CHECK (modalidad IN ('publica', 'privada', 'mixta')),
    ADD COLUMN IF NOT EXISTS tipo_obra TEXT DEFAULT 'obra_nueva',
    ADD COLUMN IF NOT EXISTS porcentaje_indirectos NUMERIC DEFAULT 15.0,
    ADD COLUMN IF NOT EXISTS porcentaje_utilidad NUMERIC DEFAULT 15.0,
    ADD COLUMN IF NOT EXISTS porcentaje_herramienta NUMERIC DEFAULT 5.0,
    ADD COLUMN IF NOT EXISTS porcentaje_iva NUMERIC DEFAULT 16.0,
    ADD COLUMN IF NOT EXISTS formatted_address TEXT,
    ADD COLUMN IF NOT EXISTS pais VARCHAR(50) DEFAULT 'México',
    ADD COLUMN IF NOT EXISTS estado VARCHAR(100),
    ADD COLUMN IF NOT EXISTS municipio VARCHAR(100),
    ADD COLUMN IF NOT EXISTS codigo_postal VARCHAR(10),
    ADD COLUMN IF NOT EXISTS direccion_calle TEXT,
    ADD COLUMN IF NOT EXISTS latitud NUMERIC(9,6),
    ADD COLUMN IF NOT EXISTS longitud NUMERIC(9,6);

-- 2. TABLAS SATÉLITE COMPARTIDAS (Personal y Proveedores del Despacho)
CREATE TABLE IF NOT EXISTS public.proveedores (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre_comercial TEXT NOT NULL,
    contacto TEXT,
    telefono TEXT,
    giro TEXT DEFAULT 'Materiales', -- 'Materiales', 'Fletes / Retiro', 'Acabados'
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.personal_obra (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE,
    nombre TEXT NOT NULL,
    especialidad TEXT DEFAULT 'Albañilería', -- 'Albañilería', 'Pintura', 'Plomería'
    costo_jornal_base NUMERIC DEFAULT 0,
    telefono TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 3. DUAL PATH EN CATÁLOGOS (Biblioteca Maestra y Catálogo de Proyecto)
-- En Biblioteca: Desglose base de costos directos (sin utilidad)
ALTER TABLE public.biblioteca_conceptos
    ADD COLUMN IF NOT EXISTS costo_material NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_mano_obra NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_herramienta NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_indirecto NUMERIC DEFAULT 0;

-- En Catálogo: Desglose base + factor de utilidad específico del concepto
ALTER TABLE public.catalogo_conceptos
    ADD COLUMN IF NOT EXISTS costo_material NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_mano_obra NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_herramienta NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS costo_indirecto NUMERIC DEFAULT 0,
    ADD COLUMN IF NOT EXISTS porcentaje_utilidad NUMERIC DEFAULT 15.0;

-- Tabla de descomposición fina por insumo individual (Composición APU)
CREATE TABLE IF NOT EXISTS public.insumos_concepto (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_concepto BIGINT REFERENCES public.catalogo_conceptos(id) ON DELETE CASCADE,
    tipo_insumo TEXT NOT NULL CHECK (tipo_insumo IN ('material', 'mdeo', 'herramienta', 'subcontrato', 'indirecto')),
    descripcion_insumo TEXT NOT NULL,
    unidad VARCHAR(20) NOT NULL,
    cantidad_unitaria NUMERIC NOT NULL DEFAULT 1.0,
    costo_unitario NUMERIC NOT NULL,
    importe NUMERIC GENERATED ALWAYS AS (cantidad_unitaria * costo_unitario) STORED,
    id_proveedor BIGINT REFERENCES public.proveedores(id) ON DELETE SET NULL,
    id_personal BIGINT REFERENCES public.personal_obra(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 4. HITOS COMERCIALES Y TELEMETRÍA METEOROLÓGICA
CREATE TABLE IF NOT EXISTS public.hitos_cobro (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_proyecto BIGINT REFERENCES public.proyectos(id) ON DELETE CASCADE,
    concepto_hito TEXT NOT NULL,
    porcentaje NUMERIC NOT NULL,
    monto_pactado NUMERIC NOT NULL,
    estado TEXT DEFAULT 'Pendiente' CHECK (estado IN ('Pendiente', 'Cobrado')),
    fecha_cobro DATE,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.telemetria_clima (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    id_estimacion BIGINT REFERENCES public.estimaciones(id) ON DELETE CASCADE,
    temp_media_c NUMERIC,
    temp_max_c NUMERIC,
    precipitacion_mm NUMERIC,
    dias_lluvia INT2 DEFAULT 0,
    humedad_relativa_pct NUMERIC,
    fetched_at TIMESTAMPTZ DEFAULT now()
);

-- 5. AJUSTES EN MEDICIONES DE CAMPO (Asignación Opcional a Destajista)
ALTER TABLE public.mediciones_campo
    ADD COLUMN IF NOT EXISTS id_personal BIGINT REFERENCES public.personal_obra(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS horas_o_jornales NUMERIC DEFAULT 1.0;

-- 6. POLÍTICAS RLS (Row Level Security)
ALTER TABLE public.proveedores ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.personal_obra ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.insumos_concepto ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hitos_cobro ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.telemetria_clima ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Proveedores aislamiento usuario" ON public.proveedores
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Personal aislamiento usuario" ON public.personal_obra
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Insumos acceso vía concepto" ON public.insumos_concepto
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.catalogo_conceptos c
        JOIN public.proyectos p ON c.id_proyecto = p.id
        WHERE c.id = insumos_concepto.id_concepto AND p.user_id = auth.uid()
    ));

CREATE POLICY "Hitos acceso vía proyecto" ON public.hitos_cobro
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.proyectos p 
        WHERE p.id = hitos_cobro.id_proyecto AND p.user_id = auth.uid()
    ));

CREATE POLICY "Clima acceso vía estimacion" ON public.telemetria_clima
    FOR ALL USING (EXISTS (
        SELECT 1 FROM public.estimaciones e
        JOIN public.proyectos p ON e.id_proyecto = p.id
        WHERE e.id = telemetria_clima.id_estimacion AND p.user_id = auth.uid()
    ));

-- 7. VISTA ANALÍTICA UNIFICADA: FEATURE STORE PARA MACHINE LEARNING
CREATE OR REPLACE VIEW public.v_telemetria_rendimientos_ml AS
SELECT 
    m.id AS medicion_id,
    p.id AS proyecto_id,
    p.modalidad,
    p.tipo_obra,
    p.estado AS estado_republica,
    p.municipio,
    EXTRACT(MONTH FROM m.created_at) AS mes_ejecucion,
    c.especialidad,
    c.categoria,
    c.unidad,
    c.cantidad_contratada AS volumen_total_contratado,
    c.precio_unitario AS precio_unitario_teorico,
    po.id AS trabajador_id,
    po.especialidad AS oficio_trabajador,
    po.costo_jornal_base,
    tc.temp_media_c,
    tc.temp_max_c,
    tc.precipitacion_mm,
    tc.dias_lluvia,
    m.cantidad_total AS avance_fisico_observado,
    COALESCE(m.horas_o_jornales, 1.0) AS esfuerzo_invertido,
    ROUND((m.cantidad_total / NULLIF(m.horas_o_jornales, 0))::NUMERIC, 4) AS target_rendimiento_mdeo
FROM public.mediciones_campo m
JOIN public.catalogo_conceptos c ON m.id_concepto = c.id
JOIN public.proyectos p ON c.id_proyecto = p.id
LEFT JOIN public.personal_obra po ON m.id_personal = po.id
LEFT JOIN public.telemetria_clima tc ON m.id_estimacion = tc.id_estimacion
WHERE m.cantidad_total > 0;
