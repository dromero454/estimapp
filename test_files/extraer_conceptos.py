import pandas as pd

# Asegúrate de que el Excel de Ingrid esté en la misma carpeta
file_path = "Estimacion 1 Normal -HGZ1-HEM OK.XLSX"
print("Extrayendo conceptos del catálogo oficial...")

try:
    df = pd.read_excel(file_path, sheet_name="CATALOGO", header=None)
    data = []
    current_especialidad = "01 GENERALES"

    # Encontrar dónde empiezan los datos
    start_row = 0
    for i, row in df.iterrows():
        if "Código" in str(row[0]) or "Concepto" in str(row[1]):
            start_row = i + 1
            break

    # Recorrer filas y estructurar
    for i in range(start_row, len(df)):
        row = df.iloc[i]
        codigo = str(row[0]).strip()
        concepto = str(row[1]).strip()
        
        # Detectar cabecera de especialidad
        if pd.isna(row[2]) and pd.isna(row[3]) and codigo != "nan" and concepto == "nan":
            current_especialidad = codigo
            continue

        if codigo != "nan" and concepto != "nan" and not pd.isna(row[2]):
            unidad = str(row[2]).strip()
            try:
                cantidad = float(row[3]) if not pd.isna(row[3]) else 0.0
                pu = float(row[4]) if not pd.isna(row[4]) else 0.0
            except:
                continue
                
            data.append({
                "Especialidad": current_especialidad, "Clave": codigo,
                "Descripcion": concepto, "Unidad": unidad,
                "Cantidad_Contratada": cantidad, "Precio_Unitario": pu
            })

    # Generar Plantilla para Catálogo de Proyecto
    df_proy = pd.DataFrame(data)
    df_proy.to_excel("Plantilla_Catalogo_Proyecto.xlsx", index=False)
    print(f"✅ 'Plantilla_Catalogo_Proyecto.xlsx' creada con {len(df_proy)} conceptos.")

    # Generar Plantilla para Biblioteca Maestra
    df_bib = df_proy.copy()
    df_bib = df_bib.rename(columns={"Precio_Unitario": "Precio_Referencial"})
    df_bib = df_bib.drop(columns=["Cantidad_Contratada"])
    df_bib.to_excel("Plantilla_Biblioteca_Global.xlsx", index=False)
    print(f"✅ 'Plantilla_Biblioteca_Global.xlsx' creada con {len(df_bib)} conceptos.")

except Exception as e:
    print(f"Error: {e}")