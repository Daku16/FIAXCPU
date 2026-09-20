import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls

print("Iniciando la construcción del documento Word...")

doc = docx.Document()

# ----------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y MÁRGENES
# ----------------------------------------------------
for section in doc.sections:
    section.top_margin = Inches(1.0)
    section.bottom_margin = Inches(1.0)
    section.left_margin = Inches(1.0)
    section.right_margin = Inches(1.0)

# Colores de la paleta
COLOR_NAVY = RGBColor(11, 17, 32)       # #0B1120
COLOR_BLUE = RGBColor(2, 132, 199)      # #0284C7
COLOR_ELECTRIC = RGBColor(37, 99, 235)  # #2563EB
COLOR_GREEN = RGBColor(16, 185, 129)    # #10B981
COLOR_RED = RGBColor(239, 68, 68)       # #EF4444
COLOR_AMBER = RGBColor(217, 119, 6)     # #D97706
COLOR_GRAY = RGBColor(100, 116, 139)    # #64748B
COLOR_DARK = RGBColor(30, 41, 59)       # #1E293B

# ----------------------------------------------------
# FUNCIONES AUXILIARES DE ESTILIZADO
# ----------------------------------------------------
def add_custom_heading(doc, text, level=1, color=COLOR_BLUE):
    h = doc.add_heading(text, level=level)
    h.paragraph_format.space_before = Pt(14)
    h.paragraph_format.space_after = Pt(6)
    h.paragraph_format.keep_with_next = True
    for run in h.runs:
        run.font.name = "Segoe UI"
        run.font.color.rgb = color
        if level == 1:
            run.font.size = Pt(17)
            run.bold = True
        elif level == 2:
            run.font.size = Pt(14)
            run.bold = True
        elif level == 3:
            run.font.size = Pt(12)
            run.bold = True
    return h

def add_paragraph(doc, text, bold_prefix=None, space_after=6):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = "Segoe UI"
        r_pre.font.size = Pt(10.5)
        r_pre.font.color.rgb = COLOR_DARK
    r_text = p.add_run(text)
    r_text.font.name = "Segoe UI"
    r_text.font.size = Pt(10.5)
    r_text.font.color.rgb = COLOR_DARK
    return p

def add_code_block(doc, code_str, title=None):
    if title:
        p_t = doc.add_paragraph()
        p_t.paragraph_format.space_before = Pt(6)
        p_t.paragraph_format.space_after = Pt(2)
        r_t = p_t.add_run(f"Bloque de Código: {title}")
        r_t.bold = True
        r_t.font.name = "Segoe UI"
        r_t.font.size = Pt(9.5)
        r_t.font.color.rgb = COLOR_BLUE
        
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    table.columns[0].width = Inches(6.5)
    
    cell = table.cell(0, 0)
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
    tcPr.append(shd)
    
    borders = parse_xml(f'''
        <w:tcBorders {nsdecls("w")}>
            <w:top w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
            <w:left w:val="single" w:sz="24" w:space="0" w:color="0284C7"/>
            <w:bottom w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
            <w:right w:val="single" w:sz="4" w:space="0" w:color="E2E8F0"/>
        </w:tcBorders>
    ''')
    tcPr.append(borders)
    
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.05
    run = p.add_run(code_str.strip())
    run.font.name = "Consolas"
    run.font.size = Pt(8.5)
    run.font.color.rgb = RGBColor(15, 23, 42)

def add_image_with_caption(doc, img_path, caption, width=Inches(6.2)):
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(10)
        p_img.paragraph_format.space_after = Pt(3)
        run = p_img.add_run()
        run.add_picture(img_path, width=width)
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p_cap.paragraph_format.space_before = Pt(1)
        p_cap.paragraph_format.space_after = Pt(12)
        r_cap = p_cap.add_run(f"Ilustración: {caption}")
        r_cap.italic = True
        r_cap.font.name = "Segoe UI"
        r_cap.font.size = Pt(9.0)
        r_cap.font.color.rgb = COLOR_GRAY

# ----------------------------------------------------
# 1. PORTADA FORMAL Y FICHA TÉCNICA
# ----------------------------------------------------
p_pre = doc.add_paragraph()
p_pre.paragraph_format.space_before = Pt(40)
r_pre = p_pre.add_run("PROYECTO DE FIN DE CARRERA - 10MO SEMESTRE DE INGENIERÍA DE SISTEMAS")
r_pre.bold = True
r_pre.font.name = "Segoe UI"
r_pre.font.size = Pt(10)
r_pre.font.color.rgb = COLOR_BLUE

p_title = doc.add_paragraph()
p_title.paragraph_format.space_before = Pt(15)
p_title.paragraph_format.space_after = Pt(10)
r_title = p_title.add_run("FIAX CPU: MANUAL TÉCNICO, ARQUITECTÓNICO Y EVIDENCIA VISUAL")
r_title.bold = True
r_title.font.name = "Segoe UI"
r_title.font.size = Pt(24)
r_title.font.color.rgb = COLOR_NAVY

p_sub = doc.add_paragraph()
p_sub.paragraph_format.space_after = Pt(30)
r_sub = p_sub.add_run("Plataforma Web de Diagnóstico Heurístico, Telemetría de Hardware Real en Vivo y Mantenimiento Asistido Automatizado")
r_sub.font.name = "Segoe UI"
r_sub.font.size = Pt(13)
r_sub.font.color.rgb = COLOR_GRAY

# Tabla de Metadatos
table_meta = doc.add_table(rows=5, cols=2)
table_meta.alignment = WD_TABLE_ALIGNMENT.CENTER
table_meta.autofit = False
table_meta.columns[0].width = Inches(2.2)
table_meta.columns[1].width = Inches(4.3)

meta_data = [
    ("Línea de Investigación:", "Sistemas Autónomos de Infraestructura TI y Arquitectura de Software"),
    ("Stack Tecnológico:", "Python 3.14+, Flask 3.1, SQLite 3 con PRAGMA foreign_keys, psutil, CSS3, JS Vanilla"),
    ("Mecanismo de Seguridad:", "Role-Based Access Control (RBAC Granular), PBKDF2-HMAC-SHA256, Auditoría ISO 27001"),
    ("Estudiante / Autor:", "Erick Garcia"),
    ("Versión del Sistema:", "v2.0 Web Architecture (Año 2026)")
]

for idx, (label, val) in enumerate(meta_data):
    row = table_meta.rows[idx]
    c1, c2 = row.cells[0], row.cells[1]
    
    p1 = c1.paragraphs[0]
    r1 = p1.add_run(label)
    r1.bold = True
    r1.font.name = "Segoe UI"
    r1.font.size = Pt(9.5)
    r1.font.color.rgb = COLOR_NAVY
    
    p2 = c2.paragraphs[0]
    r2 = p2.add_run(val)
    r2.font.name = "Segoe UI"
    r2.font.size = Pt(9.5)
    r2.font.color.rgb = COLOR_DARK
    
    for c in [c1, c2]:
        tcPr = c._tc.get_or_add_tcPr()
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="F8FAFC"/>')
        tcPr.append(shd)

doc.add_page_break()

# ----------------------------------------------------
# 2. INTRODUCCIÓN Y ARQUITECTURA DEL SISTEMA
# ----------------------------------------------------
add_custom_heading(doc, "1. Arquitectura del Sistema (Clean Architecture en Capas)", level=1)

add_paragraph(doc, "El sistema FIAX CPU (Fault Inspection & Automated eXecution for Computers) fue estructurado siguiendo el patrón de Arquitectura en Capas y el principio de Separación de Preocupaciones (SoC). Esto garantiza que la lógica de bajo nivel (inspección de hardware con psutil y llamadas a la Win32 API) esté desacoplada de la capa web de presentación y del motor de persistencia relacional.", bold_prefix="Resumen Estructural: ")

add_image_with_caption(doc, "doc_images/01_arquitectura_sistema.png", "Diagrama de Arquitectura en Capas y Flujo de Datos del Sistema FIAX CPU")

add_custom_heading(doc, "Desglose de las Cinco Capas Arquitectónicas:", level=2)
add_paragraph(doc, "1. Capa de Presentación (Frontend Web): Desarrollada con HTML5 semántico, CSS3 con aceleración por GPU y JavaScript Vanilla utilizando Fetch API para comunicación asíncrona sin recargas de página.")
add_paragraph(doc, "2. Capa de Controladores (API REST & Blueprints): Compuesta por módulos independientes (auth_bp, fiax_bp, role_bp) que validan el cuerpo de las solicitudes y serializan las respuestas en formato JSON.")
add_paragraph(doc, "3. Capa de Seguridad y Autorización: Protege cada endpoint mediante decoradores personalizados (@login_required, @has_permission) y maneja criptografía PBKDF2-HMAC-SHA256 para contraseñas.")
add_paragraph(doc, "4. Capa de Servicios y Lógica de Negocio: Alberga el motor heurístico de cálculo de salud (Health Score), servicios de telemetría de hardware y rutinas físicas de mantenimiento.")
add_paragraph(doc, "5. Capa de Dominio y Persistencia: Gestionada por SQLAlchemy 2.0 ORM sobre SQLite 3 con forzamiento estricto de claves foráneas e integridad referencial.")

# ----------------------------------------------------
# 3. MODELO DE DATOS RELACIONAL Y PERSISTENCIA
# ----------------------------------------------------
add_custom_heading(doc, "2. Modelo de Datos Relacional y Esquema ORM", level=1)

add_paragraph(doc, "A diferencia de prototipos que almacenan métricas en archivos volátiles, FIAX CPU implementa un modelo relacional de tercera forma normal (3NF) que vincula al usuario con sus equipos físicos, sesiones de diagnóstico histórico, anomalías halladas y acciones correctivas aplicadas.", bold_prefix="Persistencia Estructurada: ")

add_image_with_caption(doc, "doc_images/02_modelo_datos_erd.png", "Diagrama Entidad-Relación (ERD) con Claves Foráneas e Integridad Referencial Activa")

add_custom_heading(doc, "Garantía de Integridad Referencial en SQLite:", level=2)
add_paragraph(doc, "Por defecto, SQLite desactiva la verificación de claves foráneas. Para evitar registros huérfanos o inconsistencias al eliminar entidades, se intercepta la conexión de bajo nivel mediante un listener de eventos:")

code_pragma = '''@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Garantiza que la integridad referencial y claves foráneas estén activas en SQLite."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()'''
add_code_block(doc, code_pragma, "domain/models.py - Activación de Foreign Keys")

add_custom_heading(doc, "Entidades Centrales de Hardware y Diagnóstico:", level=2)
code_models = '''class Equipo(db.Model):
    __tablename__ = 'equipos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_equipo = db.Column(db.String(100), nullable=False)
    os_version = db.Column(db.String(150), nullable=False)
    ram_total_gb = db.Column(db.Float)
    procesador = db.Column(db.String(150))
    ip_local = db.Column(db.String(50), default="127.0.0.1")

class SesionDiagnostico(db.Model):
    __tablename__ = 'sesiones_diagnostico'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="SET NULL"), nullable=True)
    score_salud = db.Column(db.Integer, default=100) # Rango de 15 a 100
    estado = db.Column(db.String(50), default='COMPLETADO')'''
add_code_block(doc, code_models, "domain/models.py - Entidades Equipo y SesionDiagnostico")

# ----------------------------------------------------
# 4. CONFIGURACIÓN Y ENTORNO
# ----------------------------------------------------
add_custom_heading(doc, "3. Configuración del Sistema y Umbrales Heurísticos", level=1)

add_paragraph(doc, "El archivo config.py centraliza los parámetros operativos del sistema, variables secretas de sesión y los umbrales numéricos a partir de los cuales el motor clasifica el estrés del hardware en advertencia o falla crítica.")

code_config = '''class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fiax_cpu_secret_key_2026_systems_eng')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fiax_cpu_web.db')
    
    # Umbrales Heurísticos de Hardware para FIAX Diagnostic Engine
    THRESHOLD_CPU_WARNING = 70.0   # Porcentaje
    THRESHOLD_CPU_CRITICAL = 85.0  # Porcentaje
    THRESHOLD_RAM_WARNING = 75.0   # Porcentaje
    THRESHOLD_RAM_CRITICAL = 88.0  # Porcentaje
    THRESHOLD_DISK_FREE_GB_CRITICAL = 10.0 # GB libres mínimos recomendados
    THRESHOLD_DISK_FREE_GB_WARNING = 25.0  # GB'''
add_code_block(doc, code_config, "config.py - Configuración y Umbrales Heurísticos")

# ----------------------------------------------------
# 5. SEGURIDAD Y CONTROL DE ACCESO (RBAC)
# ----------------------------------------------------
add_custom_heading(doc, "4. Seguridad, Hashing Criptográfico y RBAC", level=1)

add_paragraph(doc, "La seguridad del sistema está fundamentada en dos pilares: el almacenamiento no reversible de contraseñas mediante derivación de claves PBKDF2-HMAC-SHA256 con salt aleatorio, y un control de acceso basado en roles (RBAC) granular implementado a nivel de decoradores.")

code_sec = '''def has_permission(required_permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({"error": "No autorizado. Inicie sesión."}), 401
            
            req_perm_str = required_permission.value if hasattr(required_permission, 'value') else str(required_permission)
            if not AuthorizationService.user_has_permission(user_id, req_perm_str):
                return jsonify({"error": f"Acceso denegado. Requiere: {req_perm_str}"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator'''
add_code_block(doc, code_sec, "security/decorators.py - Decorador @has_permission")

# ----------------------------------------------------
# 6. TELEMETRÍA DE HARDWARE REAL
# ----------------------------------------------------
add_custom_heading(doc, "5. Telemetría de Hardware Real en Vivo (psutil)", level=1)

add_paragraph(doc, "FIAX CPU no utiliza valores aleatorios ni simulados. Su servicio TelemetryService se comunica con los subsistemas del sistema operativo anfitrión para extraer métricas fidedignas de carga del microprocesador, distribución de memoria física y los cinco subprocesos dominantes.")

add_image_with_caption(doc, "doc_images/10_ui_metric_cards_telemetria.png", "Tarjetas de Telemetría en Tiempo Real con Barras de Progreso e Indicadores de Estado")

code_telem = '''@staticmethod
def get_live_metrics():
    # CPU
    cpu_pct = psutil.cpu_percent(interval=0.1)
    cpu_cores_logical = psutil.cpu_count(logical=True) or 4
    
    # Memoria RAM
    mem = psutil.virtual_memory()
    ram_pct = mem.percent
    ram_used_gb = round((mem.total - mem.available) / (1024 ** 3), 2)
    ram_free_gb = round(mem.available / (1024 ** 3), 2)
    
    # Top 5 Procesos por uso de memoria RAM
    top_procs = []
    for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
        try:
            info = p.info
            mem_mb = round((info['memory_info'].rss / (1024 * 1024)), 1)
            top_procs.append({"pid": info['pid'], "name": info['name'], "memory_mb": mem_mb})
        except Exception:
            continue
    top_procs = sorted(top_procs, key=lambda x: x['memory_mb'], reverse=True)[:5]'''
add_code_block(doc, code_telem, "services/telemetry_service.py - get_live_metrics()")

# ----------------------------------------------------
# 7. MOTOR HEURÍSTICO Y HEALTH SCORE
# ----------------------------------------------------
add_custom_heading(doc, "6. Motor Heurístico y Algoritmo de Health Score", level=1)

add_paragraph(doc, "Para traducir el estado técnico de la estación a un índice comprensible tanto para usuarios como para administradores, se formuló matemáticamente el Health Score (H), acotado rigurosamente en el intervalo [15, 100]:")

add_paragraph(doc, "H = max(15, min(100, 100 - (P_cpu + P_ram + P_disco + P_temp + sum(w_k))))", bold_prefix="Ecuación de Salud: ")

add_image_with_caption(doc, "doc_images/11_ui_health_score_gauge.png", "Banner de Estado y Medidor Numérico de Health Score con Ficha Técnica")

code_diag = '''@staticmethod
def calculate_health_score(cpu_pct, ram_pct, disk_free_gb, temp_mb, incidents):
    score = 100.0
    if cpu_pct >= 85.0: score -= 18.0
    elif cpu_pct >= 70.0: score -= 9.0

    if ram_pct >= 88.0: score -= 22.0
    elif ram_pct >= 75.0: score -= 12.0
    elif ram_pct >= 60.0: score -= 5.0

    if disk_free_gb <= 15.0: score -= 25.0
    elif disk_free_gb <= 35.0: score -= 10.0

    if temp_mb >= 1000.0: score -= 10.0
    elif temp_mb >= 300.0: score -= 5.0

    for inc in incidents:
        sev = inc.get('severidad')
        if sev == "CRITICO": score -= 15.0
        elif sev == "ALTO":   score -= 10.0
        elif sev == "MEDIO":  score -= 5.0
        elif sev == "BAJO":   score -= 2.0

    return max(15, min(100, int(round(score))))'''
add_code_block(doc, code_diag, "services/diagnostic_service.py - calculate_health_score()")

# ----------------------------------------------------
# 8. MANTENIMIENTO ASISTIDO Y REMEDIACIÓN
# ----------------------------------------------------
add_custom_heading(doc, "7. Remediación Asistida y Optimización Física", level=1)

add_paragraph(doc, "MaintenanceService implementa tres rutinas de mantenimiento reales sobre el sistema operativo anfitrión:")
add_paragraph(doc, "1. Purga de Temporales: Escaneo y eliminación segura de archivos en %TEMP%, omitiendo archivos en uso por el kernel mediante control de excepciones.")
add_paragraph(doc, "2. Vaciado DNS: Invocación de ipconfig /flushdns a través de subprocess con la bandera CREATE_NO_WINDOW para evitar la apertura de consolas negras.")
add_paragraph(doc, "3. Optimización de Memoria: Recolección de basura con gc.collect() y recorte forzado del Working Set llamando a EmptyWorkingSet en kernel32.dll mediante ctypes.")

code_maint = '''@staticmethod
def clean_temporary_files():
    temp_dir = os.environ.get('TEMP') or os.environ.get('TMP')
    archivos_eliminados, bytes_liberados = 0, 0
    for entry in os.scandir(temp_dir):
        try:
            if entry.is_file(follow_symlinks=False):
                size = entry.stat().st_size
                os.remove(entry.path)
                bytes_liberados += size
                archivos_eliminados += 1
        except (PermissionError, FileNotFoundError, OSError):
            continue # Archivos en uso por Windows se omiten con seguridad
    return {"success": True, "mb_liberados": round(bytes_liberados / (1024*1024), 2)}'''
add_code_block(doc, code_maint, "services/maintenance_service.py - Limpieza de Temporales")

# ----------------------------------------------------
# 9. CATÁLOGO VISUAL DE COMPONENTES FRONTEND
# ----------------------------------------------------
add_custom_heading(doc, "8. Catálogo Exhaustivo de Componentes de Frontend", level=1)

add_paragraph(doc, "A continuación se documenta cada elemento interactivo de la interfaz web, detallando su código HTML, las reglas CSS que establecen sus colores exactos, su manejador JavaScript y la acción de backend que dispara.")

# --- Componente 1: Botón Logout Rojo ---
add_custom_heading(doc, "Componente 8.1: Botón Rojo de Cierre de Sesión (Sidebar)", level=2)
add_paragraph(doc, "Ubicado en la parte inferior de la barra lateral de navegación. Permite al usuario cerrar su sesión de trabajo activa en cualquier momento.")

add_image_with_caption(doc, "doc_images/03_ui_boton_logout_rojo.png", "Estados Visuales del Botón de Cierre de Sesión (Reposo vs Hover Rojo Intenso)")

code_btn1_html = '''<div class="sidebar-footer">
    <a href="/logout" class="btn-logout-sidebar">
        <i class="fa-solid fa-arrow-right-from-bracket"></i>
        <span>Cerrar Sesión Activa</span>
    </a>
</div>'''
add_code_block(doc, code_btn1_html, "HTML: templates/dashboard.html & templates/usuarios.html")

code_btn1_css = '''.btn-logout-sidebar {
    background-color: rgba(239, 68, 68, 0.12); /* Rojo translúcido */
    color: #f87171;                             /* Rojo claro en texto */
    border: 1px solid rgba(239, 68, 68, 0.35);  /* Borde rojo suave */
    padding: 12px;
    border-radius: 8px;
    font-weight: 700;
}
.btn-logout-sidebar:hover {
    background-color: #ef4444;                  /* Rojo sólido vibrante */
    color: white;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
}'''
add_code_block(doc, code_btn1_css, "CSS: Reglas del Botón Rojo de Logout")

# --- Componente 2: Botón Eliminar Rojo ---
add_custom_heading(doc, "Componente 8.2: Botón Rojo de Eliminación de Usuario (CRUD)", level=2)
add_paragraph(doc, "Integrado en la última columna de cada fila de la tabla de gestión de usuarios. Solicita confirmación y ejecuta una petición HTTP DELETE asíncrona.")

add_image_with_caption(doc, "doc_images/04_ui_boton_eliminar_rojo.png", "Botón Rojo de Eliminación con Reglas de Seguridad y Código de Protección")

code_btn2_css = '''.btn-delete {
    background-color: #dc2626; /* Rojo oscuro de peligro */
    color: white;
    border: none;
    padding: 7px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 700;
    font-size: 12px;
}
.btn-delete:hover {
    background-color: #b91c1c; /* Rojo intenso al pasar el cursor */
}'''
add_code_block(doc, code_btn2_css, "CSS: Estilos del Botón de Eliminación")

# --- Componente 3: Modal Emergente Rojo de Error ---
add_custom_heading(doc, "Componente 8.3: Modal Emergente Rojo de Credenciales Inválidas", level=2)
add_paragraph(doc, "Ventana emergente que bloquea la interacción en la vista de login cuando el usuario introduce credenciales no registradas o erróneas.")

add_image_with_caption(doc, "doc_images/05_ui_modal_error_rojo.png", "Modal Emergente de Error con Borde, Icono y Botón Aceptar en Rojo #ef4444")

code_btn3_css = '''.popup {
    background-color: #1e293b;
    padding: 25px;
    border-radius: 14px;
    border: 1px solid #ef4444;                     /* Borde rojo de alerta */
    box-shadow: 0 10px 25px rgba(239, 68, 68, 0.2);/* Resplandor rojo */
}
.popup-btn {
    background-color: #ef4444;                     /* Botón Aceptar rojo */
    color: white;
    padding: 10px 25px;
    border-radius: 6px;
}
.popup-btn:hover { background-color: #dc2626; }'''
add_code_block(doc, code_btn3_css, "CSS: Estilos del Popup Emergente de Error")

# --- Componente 4: Botón Azul Diagnóstico ---
add_custom_heading(doc, "Componente 8.4: Botón Azul de Diagnóstico Heurístico", level=2)
add_paragraph(doc, "Botón principal de acción en el encabezado del Dashboard. Dispara la evaluación completa del sistema y despliega una ventana modal interactiva con etapas de análisis.")

add_image_with_caption(doc, "doc_images/06_ui_boton_diagnostico_azul.png", "Botón Azul con Gradiente y Modal de Diagnóstico en Curso con Spinner Animado")

code_btn4_css = '''.btn-primary {
    background: linear-gradient(135deg, #0284c7, #2563eb); /* Gradiente azul */
    color: white;
    border: none;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: 700;
    box-shadow: 0 4px 12px rgba(2, 132, 199, 0.3);        /* Sombra cyan */
}
.btn-primary:hover {
    background: linear-gradient(135deg, #0369a1, #1d4ed8);
}'''
add_code_block(doc, code_btn4_css, "CSS: Gradiente Azul del Botón Primario")

# --- Componente 5: Botón Verde Mantenimiento ---
add_custom_heading(doc, "Componente 8.5: Botón Verde de Mantenimiento Rápido", level=2)
add_paragraph(doc, "Ubicado en la pestaña de Optimización y Limpieza. Ejecuta en una sola petición la purga de temporales, vaciado de caché DNS y recorte de memoria RAM.")

add_image_with_caption(doc, "doc_images/07_ui_boton_mantenimiento_verde.png", "Botón Verde Esmeralda de Mantenimiento Global y Rutinas Físicas Asociadas")

code_btn5_css = '''.btn-success {
    background-color: #10b981; /* Verde esmeralda */
    color: white;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: 700;
    border: none;
    cursor: pointer;
}
.btn-success:hover {
    background-color: #059669; /* Verde oscuro */
}'''
add_code_block(doc, code_btn5_css, "CSS: Estilos del Botón Verde de Mantenimiento")

# --- Componente 6: Botón Ámbar Editar ---
add_custom_heading(doc, "Componente 8.6: Botón Ámbar / Naranja de Edición de Usuario", level=2)
add_paragraph(doc, "Permite a los administradores modificar el nombre, correo o nivel de privilegios asignado a una cuenta existente.")

add_image_with_caption(doc, "doc_images/08_ui_boton_editar_naranja.png", "Botón Ámbar de Edición y Formulario Modal de Actualización de Usuario")

code_btn6_css = '''.btn-edit {
    background-color: #d97706; /* Color ámbar/naranja */
    color: white;
    border: none;
    padding: 7px 12px;
    border-radius: 6px;
    font-weight: 700;
    font-size: 12px;
}
.btn-edit:hover {
    background-color: #b45309; /* Naranja más oscuro */
}'''
add_code_block(doc, code_btn6_css, "CSS: Estilos del Botón de Edición")

# --- Componente 7: Badges de Severidad ---
add_custom_heading(doc, "Componente 8.7: Matriz de Insignias de Severidad de Incidencias", level=2)
add_paragraph(doc, "Permite a los técnicos priorizar la atención de cuellos de botella mediante una codificación cromática inequívoca:")

add_image_with_caption(doc, "doc_images/09_ui_badges_severidad.png", "Matriz Cromática de Severidad e Insignias de Estado de Incidencia")

code_btn7_css = '''/* Rojo para CRÍTICO */
.badge-sev.CRITICO { background-color: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; }
/* Naranja para ALTO */
.badge-sev.ALTO    { background-color: rgba(249, 115, 22, 0.25); color: #fb923c; border: 1px solid #f97316; }
/* Amarillo para MEDIO */
.badge-sev.MEDIO   { background-color: rgba(245, 158, 11, 0.25); color: #fbbf24; border: 1px solid #f59e0b; }
/* Azul para BAJO */
.badge-sev.BAJO    { background-color: rgba(59, 130, 246, 0.25);  color: #60a5fa; border: 1px solid #3b82f6; }'''
add_code_block(doc, code_btn7_css, "CSS: Clases de Severidad de Incidencias")

# ----------------------------------------------------
# 10. PRUEBAS AUTOMATIZADAS Y RESULTADOS
# ----------------------------------------------------
add_custom_heading(doc, "9. Batería de Pruebas Automatizadas y Validación", level=1)

add_paragraph(doc, "La calidad y resiliencia de la plataforma se certificó mediante una suite formal de 12 pruebas unitarias e integrales en tests/test_fiax.py, ejecutadas sin simuladores sobre el hardware anfitrión.")

add_image_with_caption(doc, "doc_images/12_test_results_summary.png", "Resumen de Ejecución Exitosa de las 12 Pruebas Unitarias del Sistema (100% OK)")

table_tests = doc.add_table(rows=13, cols=3)
table_tests.alignment = WD_TABLE_ALIGNMENT.CENTER
table_tests.autofit = False
table_tests.columns[0].width = Inches(1.2)
table_tests.columns[1].width = Inches(2.2)
table_tests.columns[2].width = Inches(3.1)

# Header
hdr = table_tests.rows[0]
for idx, title in enumerate(["ID Test", "Nombre de Prueba", "Criterio de Validación"]):
    p = hdr.cells[idx].paragraphs[0]
    r = p.add_run(title)
    r.bold = True
    r.font.name = "Segoe UI"
    r.font.size = Pt(9.5)
    r.font.color.rgb = COLOR_NAVY
    tcPr = hdr.cells[idx]._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="E2E8F0"/>')
    tcPr.append(shd)

tests_data = [
    ("test_01", "login_success", "Redirección 302 hacia /dashboard con credenciales de admin"),
    ("test_02", "login_invalid_password", "Respuesta 200 con modal de credenciales inválidas ante clave errónea"),
    ("test_03", "registration_and_logout", "Validación de contraseñas desiguales y limpieza de sesión"),
    ("test_04", "hardware_telemetry", "Lectura de CPU, RAM, disco y procesos reales con psutil"),
    ("test_05", "health_score_calc", "Score de 100 en reposo y score <= 40 bajo estrés crítico"),
    ("test_06", "complete_diagnosis", "Persistencia atómica de sesión, métricas e incidencias"),
    ("test_07", "maintenance_routines", "Purga de temporales, flush DNS y optimización de RAM exitosas"),
    ("test_08", "resolve_incident", "Actualización de estado de la incidencia a RESUELTA en BD"),
    ("test_09", "audit_logging", "Registro inmutable en auditoria_logs con IP y fecha UTC"),
    ("test_10", "rbac_access_control", "Bloqueo 401 a anónimos y autorización según rol asignado"),
    ("test_11", "user_crud_protections", "Inhabilidad de auto-eliminarse o eliminar al único admin"),
    ("test_12", "template_rendering", "Protección de rutas /dashboard y /usuarios sin login previo")
]

for idx, (t_id, t_name, t_crit) in enumerate(tests_data):
    row = table_tests.rows[idx + 1]
    for c_idx, val in enumerate([t_id, t_name, t_crit]):
        cell = row.cells[c_idx]
        p = cell.paragraphs[0]
        r = p.add_run(val)
        r.font.name = "Segoe UI"
        r.font.size = Pt(8.5)
        tcPr = cell._tc.get_or_add_tcPr()
        fill = "F8FAFC" if idx % 2 == 0 else "FFFFFF"
        shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>')
        tcPr.append(shd)

# Guardar documento final
output_filename = "MANUAL_TECNICO_FIAX_CPU.docx"
doc.save(output_filename)
print(f"¡Documento Word generado exitosamente como '{output_filename}'!")

