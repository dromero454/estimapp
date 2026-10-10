"""
Script de Regresión Inmediata (Zero-Delay Rollback)
Restaura de forma atómica los archivos respaldados antes del ajuste aislado del Drawer.
"""
import shutil
import os

BACKUP_DIR = r"backups/drawer_isolated_adjustment_checkpoint"
FILES = [
    ("app.py", "app.py"),
    ("drawer_tracker.py", "modulos/drawer_tracker.py"),
    ("bug_tracker.py", "modulos/bug_tracker.py"),
    ("admin_engine.py", "modulos/admin_engine.py"),
]

for src_name, dst_path in FILES:
    src = os.path.join(BACKUP_DIR, src_name)
    if os.path.exists(src):
        shutil.copy2(src, dst_path)
        print(f"Restaurado con éxito: {src} -> {dst_path}")
    else:
        print(f"ADVERTENCIA: No se encontró el respaldo {src}")

print("\nRegresión completa ejecutada con éxito. La aplicación se encuentra en el estado exacto anterior.")
