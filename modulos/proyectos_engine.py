import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import json
from supabase import Client
from modulos.db_engine import extraer_nombres_archivos

MODALIDADES_MAP = {
    "Obra Pública": "publica",
    "Obra Privada": "privada",
    "Mixta / Integral": "mixta"
}
MODALIDADES_INV = {v: k for k, v in MODALIDADES_MAP.items()}

TIPOS_OBRA_MAP = {
    "Obra Nueva": "obra_nueva",
    "Mantenimiento": "mantenimiento",
    "Remodelación": "remodelacion",
    "Infraestructura": "infraestructura"
}
TIPOS_OBRA_INV = {v: k for k, v in TIPOS_OBRA_MAP.items()}


@st.cache_data(ttl=3600, show_spinner=False)
def obtener_geolocalizacion_ip() -> dict:
    """
    Obtiene la ubicación aproximada basada en la IP pública para contextualizar
    las búsquedas geográficas de Nominatim. Retorna código de país (ej: 'mx')
    y coordenadas aproximadas con timeout defensivo estricto (<2.5s).
    """
    try:
        req = urllib.request.Request(
            "http://ip-api.com/json/",
            headers={"User-Agent": "Estimapp/2.0"}
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == "success":
            return {
                "country_code": str(data.get("countryCode", "MX")).lower(),
                "country": data.get("country", "México"),
                "region": data.get("regionName", ""),
                "city": data.get("city", ""),
                "lat": float(data.get("lat", 19.24)),
                "lon": float(data.get("lon", -103.72))
            }
    except Exception:
        pass
    return {
        "country_code": "mx",
        "country": "México",
        "region": "",
        "city": "",
        "lat": 19.24,
        "lon": -103.72
    }


def resolver_geocodificacion_nominatim(direccion_query: str) -> dict:
    """
    Geocodifica una dirección usando OpenStreetMap / Nominatim.
    Prioriza el contexto geográfico por IP del usuario (código de país y viewbox)
    para máxima precisión de sugerencias locales, con fallback global defensivo.
    """
    if not direccion_query or not direccion_query.strip():
        return {"error": "Por favor ingresa una dirección o referencia válida para buscar."}

    query_encoded = urllib.parse.quote(direccion_query.strip())
    ip_info = obtener_geolocalizacion_ip()

    # 1. Búsqueda con sesgo por IP (código de país y cuadrante viewbox)
    cc = ip_info.get("country_code", "mx")
    lat_ip = ip_info.get("lat")
    lon_ip = ip_info.get("lon")

    url_biased = f"https://nominatim.openstreetmap.org/search?q={query_encoded}&format=json&addressdetails=1&limit=1&countrycodes={cc}"
    if lat_ip is not None and lon_ip is not None:
        min_lon = round(lon_ip - 2.5, 4)
        max_lat = round(lat_ip + 2.5, 4)
        max_lon = round(lon_ip + 2.5, 4)
        min_lat = round(lat_ip - 2.5, 4)
        url_biased += f"&viewbox={min_lon},{max_lat},{max_lon},{min_lat}&bounded=0"

    data = None
    try:
        req = urllib.request.Request(url_biased, headers={"User-Agent": "Estimapp/2.0"})
        with urllib.request.urlopen(req, timeout=6) as response:
            data = json.loads(response.read().decode("utf-8"))
    except Exception:
        data = None

    # 2. Si no hay coincidencias con el sesgo local, reintentar búsqueda global sin restricciones
    if not data:
        try:
            url_global = f"https://nominatim.openstreetmap.org/search?q={query_encoded}&format=json&addressdetails=1&limit=1"
            req = urllib.request.Request(url_global, headers={"User-Agent": "Estimapp/2.0"})
            with urllib.request.urlopen(req, timeout=6) as response:
                data = json.loads(response.read().decode("utf-8"))
        except Exception as ex:
            return {"error": f"Fallo al contactar servicio de geocodificación: {str(ex)}"}

    if not data:
        return {"error": "No se encontraron coordenadas en OpenStreetMap para la dirección ingresada."}

    item = data[0]
    addr = item.get("address", {})

    municipio = (
        addr.get("city")
        or addr.get("town")
        or addr.get("municipality")
        or addr.get("county")
        or addr.get("village")
        or ""
    )
    estado = (
        addr.get("state")
        or addr.get("province")
        or addr.get("region")
        or ""
    )
    pais = addr.get("country", "México")
    codigo_postal = addr.get("postcode", "")

    calle_partes = [
        addr.get("road", ""),
        addr.get("house_number", ""),
        addr.get("neighbourhood", "") or addr.get("suburb", "")
    ]
    calle = ", ".join([p for p in calle_partes if p]).strip()

    return {
        "success": True,
        "latitud": round(float(item.get("lat")), 6),
        "longitud": round(float(item.get("lon")), 6),
        "formatted_address": item.get("display_name", ""),
        "municipio": municipio,
        "estado": estado,
        "pais": pais,
        "codigo_postal": str(codigo_postal),
        "direccion_calle": calle or direccion_query.strip()
    }


def render_proyectos_tab(supabase: Client, user_id: str, lista_proyectos: list, get_proyectos_cache_fn):
    """
    Renderiza la pestaña Tab 8: Gestión Integral de Proyectos de Obra.
    Soporta modalidades ('publica', 'privada', 'mixta'), factores financieros de costo,
    geocodificación abierta con Nominatim (OSM) y edición en celda.
    """
    st.markdown("### Gestión de Proyectos 🏢")
    st.caption("Administración de obras públicas, privadas y mixtas con georreferenciación WGS84 y factores financieros de costo.")

    if "proy_form_counter" not in st.session_state:
        st.session_state["proy_form_counter"] = 0
    p_counter = st.session_state["proy_form_counter"]

    if "ed_proy_counter" not in st.session_state:
        st.session_state["ed_proy_counter"] = 0

    col_p_alta, col_p_baja = st.columns([1, 1])

    # -------------------------------------------------------------
    # SECCIÓN 1: FORMULARIO DE ALTA DE PROYECTO
    # -------------------------------------------------------------
    with col_p_alta:
        with st.expander("➕ Dar de alta nuevo proyecto", expanded=False):
            # 1.1 Datos Generales del Contrato
            nombre_obra = st.text_input(
                "Nombre de la Obra *",
                placeholder="Inserte aquí el nombre oficial completo de la obra...",
                key=f"proy_nom_{p_counter}"
            )

            c_mod, c_tipo = st.columns(2)
            with c_mod:
                modalidad_lbl = st.selectbox(
                    "Modalidad de Contratación *",
                    options=list(MODALIDADES_MAP.keys()),
                    index=0,
                    key=f"proy_mod_{p_counter}",
                    help="Determina el tipo de control contable: contractual oficial, control de margen privado o mixto."
                )
                modalidad_val = MODALIDADES_MAP[modalidad_lbl]
            with c_tipo:
                tipo_obra_lbl = st.selectbox(
                    "Tipo de Obra *",
                    options=list(TIPOS_OBRA_MAP.keys()),
                    index=0,
                    key=f"proy_tipo_{p_counter}"
                )
                tipo_obra_val = TIPOS_OBRA_MAP[tipo_obra_lbl]

            descripcion_sintetica = st.text_area(
                "Descripción sintética / Alcance",
                placeholder="Escriba un resumen del alcance de los trabajos a ejecutar...",
                key=f"proy_desc_{p_counter}"
            )

            # 1.2 Factores Financieros de Costo
            st.markdown("###### 📊 Factores y Márgenes Financieros de Obra")
            c_f1, c_f2, c_f3, c_f4 = st.columns(4)
            with c_f1:
                pct_ind = st.number_input(
                    "% Indirectos",
                    min_value=0.0,
                    value=15.0,
                    step=1.0,
                    format="%.2f",
                    key=f"proy_ind_{p_counter}",
                    help="Factor general de gastos indirectos de obra."
                )
            with c_f2:
                pct_uti = st.number_input(
                    "% Utilidad",
                    min_value=0.0,
                    value=15.0,
                    step=1.0,
                    format="%.2f",
                    key=f"proy_uti_{p_counter}",
                    help="Margen de utilidad comercial base para catálogo."
                )
            with c_f3:
                pct_her = st.number_input(
                    "% Herramienta",
                    min_value=0.0,
                    value=5.0,
                    step=0.5,
                    format="%.2f",
                    key=f"proy_her_{p_counter}",
                    help="Porcentaje de herramienta menor y equipo de seguridad."
                )
            with c_f4:
                pct_iva = st.number_input(
                    "% IVA",
                    min_value=0.0,
                    value=16.0,
                    step=1.0,
                    format="%.2f",
                    key=f"proy_iva_{p_counter}",
                    help="Tasa de IVA aplicable."
                )

            # 1.3 Georreferenciación Abierta con OpenStreetMap (Nominatim)
            st.markdown("###### 📍 Ubicación y Georreferenciación (OpenStreetMap)")
            c_geo_inp, c_geo_btn = st.columns([3, 1])
            with c_geo_inp:
                query_direccion = st.text_input(
                    "Buscar dirección de la obra en mapa:",
                    placeholder="Ej: Av. Constitución 123, Colima, México",
                    key=f"proy_geo_query_{p_counter}"
                )
            with c_geo_btn:
                st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
                btn_buscar_geo = st.button(
                    "🔍 Buscar Dirección",
                    key=f"btn_search_osm_{p_counter}",
                    use_container_width=True
                )

            # Variable de sesión para retener geodatos resueltos
            geo_state_key = f"geo_data_res_{p_counter}"
            if btn_buscar_geo:
                with st.spinner("Consultando OpenStreetMap (Nominatim)..."):
                    res_geo = resolver_geocodificacion_nominatim(query_direccion)
                    if res_geo.get("success"):
                        st.session_state[geo_state_key] = res_geo
                        st.session_state[f"proy_mun_{p_counter}"] = res_geo.get("municipio", "")
                        st.session_state[f"proy_edo_{p_counter}"] = res_geo.get("estado", "")
                        st.session_state[f"proy_lat_{p_counter}"] = float(res_geo.get("latitud", 0.0))
                        st.session_state[f"proy_lon_{p_counter}"] = float(res_geo.get("longitud", 0.0))
                        st.session_state[f"proy_pais_{p_counter}"] = res_geo.get("pais", "México")
                        st.session_state[f"proy_cp_{p_counter}"] = res_geo.get("codigo_postal", "")
                        st.session_state[f"proy_calle_{p_counter}"] = res_geo.get("direccion_calle", "")
                        st.toast("📍 Coordenadas y municipio resueltos con éxito.")
                    else:
                        st.warning(f"⚠️ {res_geo.get('error')}")

            geo_actual = st.session_state.get(geo_state_key, {})

            if f"proy_mun_{p_counter}" not in st.session_state:
                st.session_state[f"proy_mun_{p_counter}"] = ""
            if f"proy_edo_{p_counter}" not in st.session_state:
                st.session_state[f"proy_edo_{p_counter}"] = ""
            if f"proy_lat_{p_counter}" not in st.session_state:
                st.session_state[f"proy_lat_{p_counter}"] = 0.0
            if f"proy_lon_{p_counter}" not in st.session_state:
                st.session_state[f"proy_lon_{p_counter}"] = 0.0
            if f"proy_pais_{p_counter}" not in st.session_state:
                st.session_state[f"proy_pais_{p_counter}"] = "México"
            if f"proy_cp_{p_counter}" not in st.session_state:
                st.session_state[f"proy_cp_{p_counter}"] = ""
            if f"proy_calle_{p_counter}" not in st.session_state:
                st.session_state[f"proy_calle_{p_counter}"] = ""

            c_g1, c_g2 = st.columns(2)
            with c_g1:
                municipio = st.text_input(
                    "Municipio / Alcaldía",
                    placeholder="Ej: Colima, Cuauhtémoc...",
                    key=f"proy_mun_{p_counter}"
                )
                estado = st.text_input(
                    "Estado / Entidad",
                    placeholder="Ej: Colima, Jalisco...",
                    key=f"proy_edo_{p_counter}"
                )
            with c_g2:
                latitud = st.number_input(
                    "Latitud WGS84 (Telemetría Clima)",
                    format="%.6f",
                    disabled=True,
                    key=f"proy_lat_{p_counter}",
                    help="Coordenada geográfica resuelta por OpenStreetMap para Open-Meteo y modelos de Machine Learning (solo lectura)."
                )
                longitud = st.number_input(
                    "Longitud WGS84 (Telemetría Clima)",
                    format="%.6f",
                    disabled=True,
                    key=f"proy_lon_{p_counter}",
                    help="Coordenada geográfica resuelta por OpenStreetMap para Open-Meteo y modelos de Machine Learning (solo lectura)."
                )

            c_g3, c_g4 = st.columns(2)
            with c_g3:
                pais = st.text_input("País", key=f"proy_pais_{p_counter}")
            with c_g4:
                codigo_postal = st.text_input("Código Postal", key=f"proy_cp_{p_counter}")

            direccion_calle = st.text_input(
                "Calle y Número / Referencias",
                placeholder="Calle, número exterior y colonia...",
                key=f"proy_calle_{p_counter}"
            )
            formatted_address = geo_actual.get("formatted_address", "")

            # 1.4 Metadatos Oficiales y Contractuales
            st.markdown("###### 📑 Metadatos Oficiales y Supervisión")
            c1, c2 = st.columns(2)
            with c1:
                ubicacion_corta = st.text_input("Ubicación resumida", placeholder="Ej: Villa de Álvarez, Colima", key=f"proy_ubi_{p_counter}")
            with c2:
                unidad_inmueble = st.text_input("Unidad médica / Inmueble", placeholder="Ej: HGZ-01, UMF-19...", key=f"proy_uni_{p_counter}")

            c3, c4 = st.columns(2)
            with c3:
                contrato_no = st.text_input("N° de Contrato", placeholder="Ej: C5M0077", key=f"proy_cont_{p_counter}")
            with c4:
                concurso_no = st.text_input("N° de Concurso / Licitación", placeholder="Ej: LO-50-GYR-050GYR080-N-15-2025", key=f"proy_conc_{p_counter}")

            c5, c6 = st.columns(2)
            with c5:
                contratista = st.text_input("Contratista / Empresa", placeholder="Razón social o nombre del contratista...", key=f"proy_cta_{p_counter}")
            with c6:
                residente = st.text_input("Residente de Obra / Supervisor", placeholder="Nombre del responsable de supervisión...", key=f"proy_res_{p_counter}")

            st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
            btn_guardar_proy = st.button("💾 Guardar Proyecto", type="primary", use_container_width=True, key=f"btn_save_proy_{p_counter}")

            if btn_guardar_proy:
                if not nombre_obra or not nombre_obra.strip():
                    st.error("⚠️ El nombre de la obra es obligatorio.")
                else:
                    try:
                        nuevo_payload = {
                            "user_id": user_id,
                            "nombre_obra": nombre_obra.strip(),
                            "modalidad": modalidad_val,
                            "tipo_obra": tipo_obra_val,
                            "porcentaje_indirectos": round(float(pct_ind), 2),
                            "porcentaje_utilidad": round(float(pct_uti), 2),
                            "porcentaje_herramienta": round(float(pct_her), 2),
                            "porcentaje_iva": round(float(pct_iva), 2),
                            "descripcion_sintetica": descripcion_sintetica.strip() if descripcion_sintetica else None,
                            "ubicacion": ubicacion_corta.strip() if ubicacion_corta else (municipio or None),
                            "unidad": unidad_inmueble.strip() if unidad_inmueble else None,
                            "contrato_no": contrato_no.strip() if contrato_no else None,
                            "concurso_no": concurso_no.strip() if concurso_no else None,
                            "contratista": contratista.strip() if contratista else None,
                            "residente_obra": residente.strip() if residente else None,
                            "formatted_address": formatted_address.strip() if formatted_address else None,
                            "pais": pais.strip() if pais else "México",
                            "estado": estado.strip() if estado else None,
                            "municipio": municipio.strip() if municipio else None,
                            "codigo_postal": codigo_postal.strip() if codigo_postal else None,
                            "direccion_calle": direccion_calle.strip() if direccion_calle else None,
                            "latitud": round(float(latitud), 6) if latitud != 0.0 else None,
                            "longitud": round(float(longitud), 6) if longitud != 0.0 else None,
                        }

                        supabase.table("proyectos").insert(nuevo_payload).execute()
                        get_proyectos_cache_fn.clear()
                        st.session_state["proy_form_counter"] += 1
                        st.session_state.pop(geo_state_key, None)
                        st.success(f"✅ Proyecto '{nombre_obra.strip()}' registrado exitosamente.")
                        st.rerun()
                    except Exception as ex_ins_p:
                        st.error(f"Error al registrar proyecto: {ex_ins_p}")

    # -------------------------------------------------------------
    # SECCIÓN 2: BORRADO DEFENSIVO DE PROYECTOS
    # -------------------------------------------------------------
    proy_dict_delete = {
        f"#{idx} — {p['nombre_obra'][:60]}... ({p.get('modalidad', 'publica')})": p["id"]
        for idx, p in enumerate(lista_proyectos, start=1)
    } if lista_proyectos else {}

    with col_p_baja:
        with st.expander("🗑 Eliminar Proyecto", expanded=False):
            if not proy_dict_delete:
                st.info("No hay proyectos registrados para eliminar.")
            else:
                proy_del_sel = st.selectbox(
                    "Seleccionar proyecto a borrar:",
                    list(proy_dict_delete.keys()),
                    key=f"del_proy_sel_{st.session_state.get('del_proy_counter', 0)}"
                )
                st.warning("⚠️ Eliminar un proyecto borrará en cascada todo su catálogo, estimaciones, mediciones, hitos y telemetría.")
                
                del_counter = st.session_state.get('del_proy_counter', 0)
                chk_del = st.checkbox(
                    "Confirmo la eliminación definitiva del proyecto",
                    key=f"chk_del_proy_{del_counter}"
                )
                btn_del_proy = st.button(
                    "Eliminar Proyecto Definitivamente",
                    type="primary",
                    disabled=not chk_del,
                    key=f"btn_action_del_proy_{del_counter}"
                )

                if btn_del_proy and chk_del:
                    id_proy_del = proy_dict_delete[proy_del_sel]
                    try:
                        # 1. Recolectar evidencias físicas de Storage antes del borrado
                        archivos_ev_proy = []
                        try:
                            res_est_p = supabase.table("estimaciones").select("id").eq("id_proyecto", id_proy_del).execute()
                            est_ids = [e["id"] for e in (res_est_p.data or [])]
                            if est_ids:
                                res_m_p = supabase.table("mediciones_campo").select("url_foto, url_croquis").in_("id_estimacion", est_ids).execute()
                                for m_row in (res_m_p.data or []):
                                    for url_k in ["url_foto", "url_croquis"]:
                                        val_u = m_row.get(url_k)
                                        if val_u and "/" in val_u:
                                            archivos_ev_proy.append(val_u.split("/")[-1])
                        except Exception:
                            pass

                        # 2. Borrar primero en BD (Postgres ejecuta CASCADE atómicamente)
                        supabase.table("proyectos").delete().eq("id", id_proy_del).execute()

                        # 3. Solo tras éxito en BD, purgar evidencias de Storage
                        if archivos_ev_proy:
                            for chunk_ev in [archivos_ev_proy[i:i+50] for i in range(0, len(archivos_ev_proy), 50)]:
                                try:
                                    supabase.storage.from_("evidencias").remove(chunk_ev)
                                except Exception:
                                    pass

                        get_proyectos_cache_fn.clear()
                        st.session_state["del_proy_counter"] = del_counter + 1
                        st.success("✅ Proyecto y todos sus datos dependientes eliminados correctamente.")
                        st.rerun()
                    except Exception as ex_del_p:
                        st.error(f"Error al eliminar proyecto: {ex_del_p}")

    # -------------------------------------------------------------
    # SECCIÓN 3: TABLA INTERACTIVA Y EDICIÓN EN CELDA (st.data_editor)
    # -------------------------------------------------------------
    if lista_proyectos:
        st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)
        st.markdown("##### Proyectos Registrados en la Plataforma:")
        st.caption("💡 *Haz doble clic sobre cualquier campo para actualizar los datos oficiales de la obra o sus factores de costo.*")

        df_p = pd.DataFrame(lista_proyectos)
        df_p.insert(0, "#", range(1, len(df_p) + 1))

        # Normalizar columnas numéricas y de texto
        df_p["modalidad"] = df_p.get("modalidad", "publica").fillna("publica").map(lambda x: MODALIDADES_INV.get(x, x))
        df_p["tipo_obra"] = df_p.get("tipo_obra", "obra_nueva").fillna("obra_nueva").map(lambda x: TIPOS_OBRA_INV.get(x, x))
        df_p["porcentaje_indirectos"] = pd.to_numeric(df_p.get("porcentaje_indirectos", 15.0), errors="coerce").fillna(15.0).round(2)
        df_p["porcentaje_utilidad"] = pd.to_numeric(df_p.get("porcentaje_utilidad", 15.0), errors="coerce").fillna(15.0).round(2)

        for col_txt in ["nombre_obra", "municipio", "estado", "contrato_no", "contratista", "residente_obra"]:
            if col_txt in df_p.columns:
                df_p[col_txt] = df_p[col_txt].fillna("").astype(str)
            else:
                df_p[col_txt] = ""

        cols_mostrar = [
            "#", "nombre_obra", "modalidad", "tipo_obra",
            "porcentaje_indirectos", "porcentaje_utilidad",
            "municipio", "estado", "contrato_no", "contratista", "residente_obra"
        ]

        ed_proy_key = f"editor_proyectos_{st.session_state['ed_proy_counter']}"

        edited_proy = st.data_editor(
            df_p[cols_mostrar],
            column_config={
                "#": st.column_config.NumberColumn("#", disabled=True),
                "nombre_obra": st.column_config.TextColumn("Nombre de la Obra", required=True),
                "modalidad": st.column_config.SelectboxColumn("Modalidad", options=list(MODALIDADES_MAP.keys()), required=True),
                "tipo_obra": st.column_config.SelectboxColumn("Tipo de Obra", options=list(TIPOS_OBRA_MAP.keys()), required=True),
                "porcentaje_indirectos": st.column_config.NumberColumn("% Indirectos", format="%.2f%%", min_value=0.0, step=0.5),
                "porcentaje_utilidad": st.column_config.NumberColumn("% Utilidad", format="%.2f%%", min_value=0.0, step=0.5),
                "municipio": st.column_config.TextColumn("Municipio"),
                "estado": st.column_config.TextColumn("Estado"),
                "contrato_no": st.column_config.TextColumn("Contrato N°"),
                "contratista": st.column_config.TextColumn("Contratista"),
                "residente_obra": st.column_config.TextColumn("Residente / Supervisor")
            },
            use_container_width=True,
            hide_index=True,
            key=ed_proy_key
        )

        if ed_proy_key in st.session_state and st.session_state[ed_proy_key].get("edited_rows", {}):
            error_p_msg = None
            cambios_p_guardados = 0

            for row_str, col_vals in list(st.session_state[ed_proy_key]["edited_rows"].items()):
                try:
                    r_idx = int(row_str)
                except ValueError:
                    continue

                if r_idx >= len(lista_proyectos):
                    continue

                id_proy_mod = lista_proyectos[r_idx]["id"]
                up_p = {}

                if "nombre_obra" in col_vals:
                    val_nom = col_vals["nombre_obra"]
                    if val_nom is None or not str(val_nom).strip():
                        error_p_msg = "El nombre de la obra es obligatorio y no puede quedar vacío."
                        break
                    up_p["nombre_obra"] = str(val_nom).strip()

                if "modalidad" in col_vals:
                    lbl_m = col_vals["modalidad"]
                    up_p["modalidad"] = MODALIDADES_MAP.get(lbl_m, "publica")

                if "tipo_obra" in col_vals:
                    lbl_t = col_vals["tipo_obra"]
                    up_p["tipo_obra"] = TIPOS_OBRA_MAP.get(lbl_t, "obra_nueva")

                if "porcentaje_indirectos" in col_vals:
                    try:
                        up_p["porcentaje_indirectos"] = round(float(col_vals["porcentaje_indirectos"]), 2)
                    except:
                        pass

                if "porcentaje_utilidad" in col_vals:
                    try:
                        up_p["porcentaje_utilidad"] = round(float(col_vals["porcentaje_utilidad"]), 2)
                    except:
                        pass

                for campo in ["municipio", "estado", "contrato_no", "contratista", "residente_obra"]:
                    if campo in col_vals:
                        up_p[campo] = str(col_vals[campo] or "").strip()

                if up_p:
                    try:
                        supabase.table("proyectos").update(up_p).eq("id", id_proy_mod).execute()
                        cambios_p_guardados += 1
                    except Exception as e:
                        error_p_msg = f"Error al actualizar el proyecto: {e}"
                        break

            if error_p_msg:
                st.toast(f"⚠️ {error_p_msg}", icon="⚠️")
                st.session_state["ed_proy_counter"] += 1
                st.session_state.pop(ed_proy_key, None)
                st.rerun()
            elif cambios_p_guardados > 0:
                get_proyectos_cache_fn.clear()
                st.toast("✅ Datos de la obra actualizados.", icon="✅")
                st.session_state["ed_proy_counter"] += 1
                st.session_state.pop(ed_proy_key, None)
                st.rerun()
