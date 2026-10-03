import streamlit as st
from supabase import Client

def render_login_card(supabase: Client):
    """
    Renderiza la tarjeta de autenticación estilo Google Account
    con selector entre Iniciar Sesión y Crear Cuenta.
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

    _, col_centro, _ = st.columns([1, 2.2, 1])

    with col_centro:
        with st.container(border=True):
            st.markdown("<h2 style='text-align: center; margin-bottom: 0px;'>Estimapp 🏗️</h2>", unsafe_allow_html=True)
            st.caption("<p style='text-align: center; margin-top: 0px;'>Control de avance físico y financiero de obra pública</p>", unsafe_allow_html=True)
            st.markdown("---")

            if st.session_state["auth_mode"] == "login":
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
                                    else:
                                        st.session_state["perfil"] = {
                                            "nombre": res.user.email.split("@")[0],
                                            "apellido_paterno": "",
                                            "empresa_despacho": "Despacho"
                                        }
                                    st.success("¡Bienvenido!")
                                    st.rerun()
                            except Exception:
                                st.error("Credenciales incorrectas o usuario no registrado.")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("Crear una cuenta", type="secondary"):
                    st.session_state["auth_mode"] = "registro"
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
                                    st.success("¡Cuenta creada exitosamente!")
                                    st.session_state["auth_mode"] = "login"
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Error al registrar la cuenta: {e}")

                st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
                if st.button("← Ya tengo una cuenta (Acceder)", type="secondary"):
                    st.session_state["auth_mode"] = "login"
                    st.rerun()