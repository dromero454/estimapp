import streamlit as st
from supabase import Client

def render_login_card(supabase: Client):
    """
    Renderiza la tarjeta de autenticación estilo Google Account
    con selector entre Iniciar Sesión, Crear Cuenta y Recuperar Contraseña.
    """
    st.markdown("""
    <style>
    .auth-container {
        max-width: 480px;
        margin: 2rem auto;
        padding: 2.5rem 2.2rem;
        background-color: #ffffff;
        border-radius: 18px;
        border: 1px solid #e0e2ec;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.06);
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    </style>
    """, unsafe_allow_html=True)

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    # Puente JS para convertir hash fragments (#access_token=...&type=recovery) en query params (?...)
    import streamlit.components.v1 as components
    components.html("""
    <script>
    (function() {
        function checkHash() {
            try {
                const win = window.parent || window;
                const hash = win.location.hash;
                if (hash && (hash.includes('access_token=') || hash.includes('type=recovery') || hash.includes('error='))) {
                    const cleanHash = hash.startsWith('#') ? hash.substring(1) : hash;
                    const doc = win.document;
                    const a = doc.createElement('a');
                    a.href = win.location.pathname + '?' + cleanHash;
                    a.target = '_self';
                    doc.body.appendChild(a);
                    a.click();
                }
            } catch(e) {
                console.error("Error al procesar hash:", e);
            }
        }
        checkHash();
        setInterval(checkHash, 300);
    })();
    </script>
    """, height=1, width=1)

    _, col_centro, _ = st.columns([1, 2.2, 1])

    with col_centro:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>Estimapp 🏗️</h2>", unsafe_allow_html=True)
            st.caption("<p style='text-align: center; margin-top: 0px;'>Control de avance físico y financiero de obra pública y privada</p>", unsafe_allow_html=True)
            st.markdown("---")

            if st.session_state["auth_mode"] == "login":
                if st.session_state.get("mensaje_post_recuperacion"):
                    st.success(st.session_state.pop("mensaje_post_recuperacion"))
                if st.session_state.get("error_recuperacion"):
                    st.error(st.session_state.pop("error_recuperacion"))

                st.markdown("#### Iniciar sesión")
                st.write("Usa tu cuenta de Estimapp")

                with st.form("form_login"):
                    email = st.text_input("Correo electrónico", placeholder="ejemplo@correo.com")
                    password = st.text_input("Contraseña", type="password", placeholder="••••••••")
                    
                    submit_login = st.form_submit_button("Siguiente", type="primary", use_container_width=True)
                    
                    if submit_login:
                        if not email.strip() or not password.strip():
                            st.error("Por favor ingresa tu correo y contraseña.")
                        else:
                            try:
                                res = supabase.auth.sign_in_with_password({"email": email.strip(), "password": password})
                                if res.user:
                                    st.session_state["user"] = res.user
                                    perf = supabase.table("perfiles").select("*").eq("id", res.user.id).execute()
                                    if perf.data:
                                        st.session_state["perfil"] = perf.data[0]
                                        st.session_state["es_admin"] = bool(perf.data[0].get("es_admin", False))
                                    else:
                                        st.session_state["perfil"] = {
                                            "nombre": res.user.email.split("@")[0],
                                            "apellido_paterno": "",
                                            "empresa_despacho": "Despacho"
                                        }
                                        st.session_state["es_admin"] = False
                                    st.success("¡Bienvenido!")
                                    st.rerun()
                            except Exception:
                                st.error("Credenciales incorrectas o usuario no registrado.")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                c_acc1, c_acc2 = st.columns(2)
                with c_acc1:
                    if st.button("Crear una cuenta", type="secondary", use_container_width=True):
                        st.session_state["auth_mode"] = "registro"
                        st.rerun()
                with c_acc2:
                    if st.button("¿Olvidaste tu contraseña?", type="tertiary", use_container_width=True):
                        st.session_state["auth_mode"] = "recuperar"
                        st.rerun()

            elif st.session_state["auth_mode"] == "recuperar":
                st.markdown("#### Recuperar contraseña")
                st.write("Ingresa tu correo registrado para recibir las instrucciones de recuperación.")

                with st.form("form_recuperar"):
                    correo_rec = st.text_input("Correo electrónico *", placeholder="tu_correo@dominio.com")
                    submit_rec = st.form_submit_button("Enviar enlace de recuperación", type="primary", use_container_width=True)

                    if submit_rec:
                        if not correo_rec.strip():
                            st.error("Por favor ingresa tu correo electrónico.")
                        else:
                            redirect_url = st.secrets.get("APP_URL", "http://localhost:8501")
                            try:
                                supabase.auth.reset_password_for_email(correo_rec.strip(), options={"redirect_to": redirect_url})
                            except Exception:
                                try:
                                    supabase.auth.reset_password_for_email(correo_rec.strip())
                                except Exception:
                                    pass
                            st.session_state["recuperar_enviado"] = True

                if st.session_state.get("recuperar_enviado"):
                    st.success("✉️ Si el correo está registrado en Estimapp, recibirás un enlace para restablecer tu contraseña en unos momentos. Revisa tu bandeja de entrada o spam.")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("← Volver a Iniciar Sesión", type="secondary", use_container_width=True):
                    st.session_state["recuperar_enviado"] = False
                    st.session_state["auth_mode"] = "login"
                    st.rerun()

            elif st.session_state["auth_mode"] == "restablecer":
                st.markdown("#### Cambiar contraseña")
                st.caption("Ingresa tu nueva contraseña para actualizar tus credenciales de acceso.")

                with st.form("form_restablecer_pass"):
                    pass_1 = st.text_input("Nueva Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
                    pass_2 = st.text_input("Confirmar Nueva Contraseña *", type="password", placeholder="Repite tu nueva contraseña")
                    btn_actualizar = st.form_submit_button("🔑 Actualizar Contraseña", type="primary", use_container_width=True)

                    if btn_actualizar:
                        if len(pass_1.strip()) < 6:
                            st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                        elif pass_1.strip() != pass_2.strip():
                            st.error("Las contraseñas no coinciden.")
                        else:
                            try:
                                res = supabase.auth.update_user({"password": pass_1.strip()})
                                if res.user:
                                    st.session_state["mensaje_post_recuperacion"] = "✅ ¡Tu contraseña se actualizó correctamente! Ahora puedes iniciar sesión con tu nueva clave."
                                    try:
                                        supabase.auth.sign_out()
                                    except Exception:
                                        pass
                                    st.session_state.pop("recovery_user", None)
                                    st.session_state["auth_mode"] = "login"
                                    st.rerun()
                            except Exception as e:
                                err_msg = str(e)
                                if "different from the old password" in err_msg.lower():
                                    st.error("La nueva contraseña debe ser diferente a la contraseña actual.")
                                else:
                                    st.error(f"Error al actualizar contraseña: {err_msg}")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("← Cancelar y volver al inicio de sesión", type="secondary", use_container_width=True):
                    try:
                        supabase.auth.sign_out()
                    except Exception:
                        pass
                    st.session_state.pop("recovery_user", None)
                    st.session_state["auth_mode"] = "login"
                    st.rerun()

            else:
                st.markdown("#### Crea una cuenta en Estimapp")
                st.write("Ingresa tus datos personales y de trabajo")

                with st.form("form_registro"):
                    st.markdown("**1. Información personal**")
                    c_n1, c_n2 = st.columns(2)
                    nombre = c_n1.text_input("Nombre(s) *", placeholder="Ingrid")
                    ap_pat = c_n2.text_input("Apellido paterno *", placeholder="González")

                    c_n3, c_n4 = st.columns(2)
                    ap_mat = c_n3.text_input("Apellido materno", placeholder="(Opcional)")
                    empresa = c_n4.text_input("Empresa o Despacho", placeholder="Ej: Tapial, Particular...")

                    st.markdown("**2. Credenciales de acceso**")
                    correo_reg = st.text_input("Correo electrónico *", placeholder="tu_correo@dominio.com")
                    c_p1, c_p2 = st.columns(2)
                    pass_1 = c_p1.text_input("Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
                    pass_2 = c_p2.text_input("Confirmar contraseña *", type="password", placeholder="Repite tu contraseña")

                    submit_reg = st.form_submit_button("Crear cuenta", type="primary", use_container_width=True)

                    if submit_reg:
                        if not nombre.strip() or not ap_pat.strip() or not correo_reg.strip() or not pass_1.strip():
                            st.error("Por favor completa los campos obligatorios (*).")
                        elif pass_1 != pass_2:
                            st.error("Las contraseñas no coinciden.")
                        elif len(pass_1) < 6:
                            st.error("La contraseña debe tener al menos 6 caracteres.")
                        else:
                            try:
                                auth_res = supabase.auth.sign_up({
                                    "email": correo_reg.strip(),
                                    "password": pass_1.strip()
                                })
                                
                                if auth_res.user:
                                    u_id = auth_res.user.id
                                    supabase.table("perfiles").insert({
                                        "id": u_id,
                                        "nombre": nombre.strip(),
                                        "apellido_paterno": ap_pat.strip(),
                                        "apellido_materno": ap_mat.strip(),
                                        "empresa_despacho": empresa.strip() if empresa.strip() else "Independiente",
                                        "rol": "usuario"
                                    }).execute()
                                    
                                    st.session_state["user"] = auth_res.user
                                    st.session_state["perfil"] = {
                                        "nombre": nombre.strip(),
                                        "apellido_paterno": ap_pat.strip(),
                                        "empresa_despacho": empresa.strip()
                                    }
                                    st.session_state["es_admin"] = False
                                    st.success("¡Cuenta creada exitosamente!")
                                    st.session_state["auth_mode"] = "login"
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar la cuenta: {e}")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("← Ya tengo una cuenta (Acceder)", type="secondary"):
                    st.session_state["auth_mode"] = "login"
                    st.rerun()


@st.dialog("👤 Mi Perfil y Cuenta", width="medium")
def render_user_profile_dialog(supabase: Client, user, perfil: dict):
    """
    Modal de configuración de usuario para:
    a) Visualización de correo.
    b) Edición de nombre y empresa/despacho en tabla 'perfiles'.
    c) Cambio de contraseña con supabase.auth.update_user.
    d) Cierre de ventana y logout.
    e) Eliminación definitiva de cuenta y datos asociados.
    """
    st.caption("Gestiona tu información de perfil, credenciales de acceso y preferencias de tu cuenta.")
    
    tab_info, tab_pass, tab_danger = st.tabs(["👤 Perfil y Empresa", "🔒 Contraseña", "⚠️ Eliminar mi Cuenta"])
    
    with tab_info:
        st.text_input("Correo electrónico (Solo lectura)", value=user.email, disabled=True, help="El correo es tu identificador único en el sistema.")
        
        with st.form("form_editar_perfil"):
            c1, c2 = st.columns(2)
            nom_edit = c1.text_input("Nombre(s) *", value=perfil.get("nombre") or "")
            ap_pat_edit = c2.text_input("Apellido Paterno *", value=perfil.get("apellido_paterno") or "")
            
            c3, c4 = st.columns(2)
            ap_mat_edit = c3.text_input("Apellido Materno", value=perfil.get("apellido_materno") or "")
            empresa_edit = c4.text_input("Empresa o Despacho", value=perfil.get("empresa_despacho") or "")
            
            btn_save = st.form_submit_button("💾 Guardar Cambios de Perfil", type="primary", use_container_width=True)
            if btn_save:
                if not nom_edit.strip() or not ap_pat_edit.strip():
                    st.error("Nombre y Apellido Paterno son obligatorios.")
                else:
                    try:
                        up_data = {
                            "nombre": nom_edit.strip(),
                            "apellido_paterno": ap_pat_edit.strip(),
                            "apellido_materno": ap_mat_edit.strip(),
                            "empresa_despacho": empresa_edit.strip() if empresa_edit.strip() else "Independiente"
                        }
                        supabase.table("perfiles").update(up_data).eq("id", user.id).execute()
                        st.session_state["perfil"] = {**perfil, **up_data}
                        st.success("✅ Perfil actualizado exitosamente.")
                        st.toast("✅ Perfil actualizado exitosamente.")
                    except Exception as e:
                        st.error(f"Error al actualizar perfil: {e}")

    with tab_pass:
        st.markdown("**Cambiar contraseña**")
        st.caption("Ingresa tu nueva contraseña para actualizar tus credenciales de acceso.")
        with st.form("form_cambiar_pass"):
            pass_1 = st.text_input("Nueva Contraseña *", type="password", placeholder="Mínimo 6 caracteres")
            pass_2 = st.text_input("Confirmar Nueva Contraseña *", type="password", placeholder="Repite tu nueva contraseña")
            btn_pass = st.form_submit_button("🔑 Actualizar Contraseña", type="primary", use_container_width=True)
            if btn_pass:
                if len(pass_1.strip()) < 6:
                    st.error("La nueva contraseña debe tener al menos 6 caracteres.")
                elif pass_1.strip() != pass_2.strip():
                    st.error("Las contraseñas no coinciden.")
                else:
                    try:
                        res = supabase.auth.update_user({"password": pass_1.strip()})
                        if res.user:
                            st.success("✅ Contraseña actualizada exitosamente.")
                    except Exception as e:
                        err_msg = str(e)
                        if "different from the old password" in err_msg.lower():
                            st.error("La nueva contraseña debe ser diferente a la contraseña actual.")
                        else:
                            st.error(f"Error al actualizar contraseña: {err_msg}")

    with tab_danger:
        st.markdown("**Eliminar Cuenta Definitivamente**")
        st.error("⚠️ Esta acción es permanente e irreversible. Se eliminarán por completo todos tus proyectos, catálogo de conceptos, estimaciones, mediciones en campo, biblioteca maestra y tu inicio de sesión.")
        
        conf = st.checkbox("Entiendo que esta acción es definitiva y confirmo que deseo eliminar mi cuenta de Estimapp.", key="chk_del_acc")
        if st.button("🗑️ Eliminar Mi Cuenta Permanentemente", type="primary", disabled=(not conf), use_container_width=True):
            try:
                # 1. Ejecutar RPC en base de datos
                try:
                    supabase.rpc("eliminar_cuenta_propia").execute()
                except Exception:
                    pass
                
                # 2. Cascada de respaldo del lado cliente
                proys = supabase.table("proyectos").select("id").eq("user_id", user.id).execute().data or []
                p_ids = [p["id"] for p in proys]
                if p_ids:
                    ests = supabase.table("estimaciones").select("id").in_("id_proyecto", p_ids).execute().data or []
                    e_ids = [e["id"] for e in ests]
                    if e_ids:
                        supabase.table("mediciones_campo").delete().in_("id_estimacion", e_ids).execute()
                    supabase.table("estimaciones").delete().in_("id_proyecto", p_ids).execute()
                    supabase.table("catalogo_conceptos").delete().in_("id_proyecto", p_ids).execute()
                    supabase.table("proyectos").delete().eq("user_id", user.id).execute()
                supabase.table("biblioteca_conceptos").delete().eq("user_id", user.id).execute()
                supabase.table("instituciones").delete().eq("user_id", user.id).execute()
                supabase.table("perfiles").delete().eq("id", user.id).execute()

                # 3. Cerrar sesión
                try: supabase.auth.sign_out()
                except Exception: pass
                st.cache_data.clear()
                st.session_state.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error durante la eliminación de cuenta: {e}")

    st.divider()
    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("Volver al Sistema", use_container_width=True):
            st.session_state["mostrar_dialogo_cuenta"] = False
            st.rerun()
    with c_btn2:
        if st.button("Salir (Cerrar Sesión)", type="secondary", use_container_width=True):
            try: supabase.auth.sign_out()
            except Exception: pass
            st.cache_data.clear()
            st.session_state.clear()
            st.rerun()