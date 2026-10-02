import openpyxl
from openpyxl.cell.cell import MergedCell

def clean_pjf_template(input_file, output_file):
    print("Cargando archivo extendido... (Esto tomará unos segundos)")
    wb = openpyxl.load_workbook(input_file)
    
    # 1. Pestaña CARATULA
    ws_car = wb['CARATULA DICIEMBRE 2025']
    
    # Textos a limpiar (dejando en blanco)
    cells_to_clear = ['H2', 'C4', 'C5', 'F5', 'H3', 'F8', 'D22', 'I12', 'C31']
    for coord in cells_to_clear:
        if not isinstance(ws_car[coord], MergedCell):
            ws_car[coord].value = None

    # Inyección de comodines "COMPLETAR"
    completar_fields = {
        'L13': 'COMPLETAR CONTRATISTA',
        'M15': 'COMPLETAR RFC',
        'M16': 'COMPLETAR REGISTRO',
        'A45': 'COMPLETAR NOMBRE 1',
        'E45': 'COMPLETAR NOMBRE 2',
        'H45': 'COMPLETAR NOMBRE 3',
        'J45': 'COMPLETAR NOMBRE 4'
    }
    for coord, text in completar_fields.items():
        if not isinstance(ws_car[coord], MergedCell):
            ws_car[coord].value = text
            
    # 2. Pestaña ESTADO DE CUENTA
    ws_est_cta = wb['ESTADO DE CUENTA AGOSTO 2026']
    if not isinstance(ws_est_cta['E6'], MergedCell): 
        ws_est_cta['E6'].value = "COMPLETAR TEL"
    
    # Limpiar estimaciones historicas (Filas 14 a 26 aprox)
    for r in range(14, 27):
        for c in ['A', 'B', 'C', 'I']: # Se omiten D, E, G, J por tener fórmulas
            if not isinstance(ws_est_cta[f"{c}{r}"], MergedCell):
                ws_est_cta[f"{c}{r}"].value = None

    # 3. Pestaña RESUMEN
    ws_res = wb['RESUMEN AGOSTO 2026']
    if not isinstance(ws_res['B7'], MergedCell): 
        ws_res['B7'].value = "COMPLETAR DOMICILIO"
    
    # Limpiar partidas (Filas 18 a 30)
    for r in range(18, 30):
        for c in ['A', 'B']: 
            if not isinstance(ws_res[f"{c}{r}"], MergedCell):
                ws_res[f"{c}{r}"].value = None

    # 4. Pestaña ESTIMACIÓN (Barrido infinito)
    ws_est = wb['ESTIMACIÓN AGOSTO 2026']
    print(f"Limpiando {ws_est.max_row} filas de conceptos...")
    for r in range(13, ws_est.max_row + 1):
        cell_pu = ws_est[f"F{r}"] 
        # Si la col F tiene un precio unitario duro (no fórmula), es un concepto
        if isinstance(cell_pu.value, (int, float)) and not str(cell_pu.value).startswith('='):
            for c in ['A', 'B', 'E', 'F', 'G', 'I', 'J']:
                if not isinstance(ws_est[f"{c}{r}"], MergedCell):
                    ws_est[f"{c}{r}"].value = None

    # 5. Pestaña REPORTE FOTOGRAFICO (Barrido infinito)
    ws_fotos = wb['REPORTE FOTOGRAFICO']
    print("Eliminando imágenes y leyendas...")
    ws_fotos._images = [] 
    
    for r in range(13, ws_fotos.max_row + 1):
        cell_a = ws_fotos[f"A{r}"]
        if cell_a.value and not str(cell_a.value).startswith('='):
            texto = str(cell_a.value).upper()
            if not any(kw in texto for kw in ['ESTIMACIÓN', 'HOJA', 'DE', 'PERIODO', 'CLAVE', 'EDIFICIO', 'TOTAL']):
                if not isinstance(cell_a, MergedCell):
                    cell_a.value = None

    wb.save(output_file)
    print(f"✅ Plantilla maestra hiper-paginada y sanitizada guardada como: {output_file}")

if __name__ == '__main__':
    # Sustituye por el nombre de tu archivo al que le pegaste las 30 páginas
    clean_pjf_template('ESTIMACIÓN POLIZA MENOR  2026-Agosto.xlsx', 'Plantilla_PJF_Maestra.xlsx')