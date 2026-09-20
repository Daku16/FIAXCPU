import os
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from PIL import Image

print("[1/5] Preparando marca de agua y recursos institucionales...")

# 1. Asegurar marca de agua atenuada (12% opacidad)
os.makedirs('doc_images', exist_ok=True)
if os.path.exists('doc_images/logo_etitc.png'):
    im = Image.open('doc_images/logo_etitc.png').convert("RGBA")
    alpha = im.split()[3]
    alpha = alpha.point(lambda p: int(p * 0.12)) # 12% opacidad para lectura óptima
    im.putalpha(alpha)
    im.save('doc_images/watermark_etitc_faded.png')
    print("Marca de agua institucional lista en doc_images/watermark_etitc_faded.png")

# Inicializar documento Word
doc = docx.Document()

# ----------------------------------------------------
# CONFIGURACIÓN DE PÁGINA Y MÁRGENES
# ----------------------------------------------------
section = doc.sections[0]
section.top_margin = Inches(1.0)
section.bottom_margin = Inches(1.0)
section.left_margin = Inches(1.0)
section.right_margin = Inches(1.0)

# Colores Institucionales y de la Aplicación
COLOR_NAVY = RGBColor(11, 35, 65)       # Azul Institucional ETITC
COLOR_BLUE = RGBColor(2, 132, 199)      # Cyan / Azul FIAX
COLOR_ELECTRIC = RGBColor(37, 99, 235)  # Azul Eléctrico
COLOR_GREEN = RGBColor(16, 185, 129)    # Verde Éxito
COLOR_RED = RGBColor(239, 68, 68)       # Rojo Alerta / Peligro
COLOR_AMBER = RGBColor(217, 119, 6)     # Ámbar / Naranja
COLOR_GRAY = RGBColor(100, 116, 139)    # Gris Secundario
COLOR_DARK = RGBColor(30, 41, 59)       # Texto Principal Oscuro

# ----------------------------------------------------
# MARCA DE AGUA ENCABEZADO (DrawingML Anchor Centrado)
# ----------------------------------------------------
header = section.header
p_head = header.paragraphs[0]
p_head.alignment = WD_PARAGRAPH_ALIGNMENT.RIGHT

# Texto en el encabezado institucional
r_h_text = p_head.add_run("ESCUELA TECNOLÓGICA INSTITUTO TÉCNICO CENTRAL  |  FACULTAD DE SISTEMAS\n")
r_h_text.font.name = "Segoe UI"
r_h_text.font.size = Pt(8.0)
r_h_text.font.color.rgb = COLOR_GRAY
r_h_text.font.bold = True

# Añadir marca de agua anclada flotante detrás del texto
if os.path.exists('doc_images/watermark_etitc_faded.png'):
    run_wm = p_head.add_run()
    pic_wm = run_wm.add_picture('doc_images/watermark_etitc_faded.png', width=Inches(5.2))
    inline = pic_wm._inline
    graphic = inline.graphic
    extent = inline.extent
    docPr = inline.docPr

    anchor_xml = f'''
    <wp:anchor {nsdecls('wp')} distT="0" distB="0" distL="0" distR="0" simplePos="0" relativeHeight="251658240" behindDoc="1" locked="0" layoutInCell="1" allowOverlap="1">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="page">
            <wp:align>center</wp:align>
        </wp:positionH>
        <wp:positionV relativeFrom="page">
            <wp:align>center</wp:align>
        </wp:positionV>
        <wp:extent cx="{extent.cx}" cy="{extent.cy}"/>
        <wp:effectExtent l="0" t="0" r="0" b="0"/>
        <wp:wrapNone/>
        <wp:docPr id="{docPr.id}" name="{docPr.name}"/>
    </wp:anchor>
    '''
    anchor = parse_xml(anchor_xml)
    anchor.append(graphic)
    inline.getparent().replace(inline, anchor)

# Pie de Página Institucional
footer = section.footer
p_foot = footer.paragraphs[0]
p_foot.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
r_foot = p_foot.add_run("FIAX CPU: Plataforma de Diagnóstico y Mantenimiento  |  Ingeniería de Software II  |  ETITC 2026")
r_foot.font.name = "Segoe UI"
r_foot.font.size = Pt(8.5)
r_foot.font.color.rgb = COLOR_GRAY

# ----------------------------------------------------
# FUNCIONES AUXILIARES DE FORMATEO
# ----------------------------------------------------
def add_custom_heading(doc, text, level=1, color=COLOR_NAVY):
    h = doc.add_heading(text, level=level)
    h.paragraph_format.space_before = Pt(14)
    h.paragraph_format.space_after = Pt(4)
    h.paragraph_format.keep_with_next = True
    for run in h.runs:
        run.font.name = "Segoe UI"
        run.font.color.rgb = color
        if level == 1:
            run.font.size = Pt(15)
            run.bold = True
        elif level == 2:
            run.font.size = Pt(12.5)
            run.bold = True
        elif level == 3:
            run.font.size = Pt(11)
            run.bold = True
    return h

def add_paragraph(doc, text, bold_prefix=None, space_after=5):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.bold = True
        r_pre.font.name = "Segoe UI"
        r_pre.font.size = Pt(10)
        r_pre.font.color.rgb = COLOR_NAVY
    r_text = p.add_run(text)
    r_text.font.name = "Segoe UI"
    r_text.font.size = Pt(10)
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
        r_t.font.size = Pt(9.0)
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
    run.font.size = Pt(8.0)
    run.font.color.rgb = RGBColor(15, 23, 42)

def add_image_with_caption(doc, img_path, caption, width=Inches(6.0)):
    if os.path.exists(img_path):
        p_img = doc.add_paragraph()
        p_img.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p_img.paragraph_format.space_before = Pt(8)
        p_img.paragraph_format.space_after = Pt(2)
        run = p_img.add_run()
        run.add_picture(img_path, width=width)
        
        p_cap = doc.add_paragraph()
        p_cap.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        p_cap.paragraph_format.space_before = Pt(1)
        p_cap.paragraph_format.space_after = Pt(10)
        r_cap = p_cap.add_run(f"Figura: {caption}")
        r_cap.italic = True
        r_cap.font.name = "Segoe UI"
        r_cap.font.size = Pt(8.5)
        r_cap.font.color.rgb = COLOR_GRAY

print("[2/5] Construyendo Portada Institucional ETITC...")
# ----------------------------------------------------
# 1. PORTADA INSTITUCIONAL FORMAL
# ----------------------------------------------------
p_logo = doc.add_paragraph()
p_logo.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
p_logo.paragraph_format.space_before = Pt(10)
p_logo.paragraph_format.space_after = Pt(15)
if os.path.exists('doc_images/logo_etitc.png'):
    run_l = p_logo.add_run()
    run_l.add_picture('doc_images/logo_etitc.png', width=Inches(2.4))

p_inst = doc.add_paragraph()
p_inst.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
p_inst.paragraph_format.space_after = Pt(2)
r_inst = p_inst.add_run("ESCUELA TECNOLÓGICA INSTITUTO TÉCNICO CENTRAL\nESTABLECIMIENTO PÚBLICO DE EDUCACIÓN SUPERIOR")
r_inst.bold = True
r_inst.font.name = "Segoe UI"
r_inst.font.size = Pt(12)
r_inst.font.color.rgb = COLOR_NAVY

p_fac = doc.add_paragraph()
p_fac.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
p_fac.paragraph_format.space_after = Pt(25)
r_fac = p_fac.add_run("FACULTAD DE SISTEMAS — INGENIERÍA EN SISTEMAS\nINGENIERÍA DE SOFTWARE II")
r_fac.font.name = "Segoe UI"
r_fac.font.size = Pt(10.5)
r_fac.font.color.rgb = COLOR_GRAY

p_tit = doc.add_paragraph()
p_tit.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
p_tit.paragraph_format.space_before = Pt(15)
p_tit.paragraph_format.space_after = Pt(8)
r_tit = p_tit.add_run("FIAX CPU")
r_tit.bold = True
r_tit.font.name = "Segoe UI"
r_tit.font.size = Pt(28)
r_tit.font.color.rgb = COLOR_BLUE

p_subt = doc.add_paragraph()
p_subt.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
p_subt.paragraph_format.space_after = Pt(35)
r_subt = p_subt.add_run("Sistema Inteligente de Diagnóstico, Mantenimiento Preventivo y Solución Automatizada de Errores para Equipos Windows")
r_subt.font.name = "Segoe UI"
r_subt.font.size = Pt(12)
r_subt.font.color.rgb = COLOR_DARK

# Tabla de Autores e Información Institucional
table_cover = doc.add_table(rows=5, cols=2)
table_cover.alignment = WD_TABLE_ALIGNMENT.CENTER
table_cover.autofit = False
table_cover.columns[0].width = Inches(2.2)
table_cover.columns[1].width = Inches(4.3)

cover_info = [
    ("Grupo y Semestre:", "Grupo S10A — Décimo Semestre"),
    ("Autores / Desarrolladores:", "Erick Santiago García Sánchez\nEider Sebastián Ortiz Botina\nOscar David Gutiérrez Molina"),
    ("Docente Tutor:", "Fredy Arturo Ordoñez"),
    ("Lugar y Fecha:", "Bogotá D.C., Colombia — Septiembre de 2026"),
    ("Línea de Investigación:", "Sistemas Autónomos de Infraestructura TI y Arquitectura de Software")
]

for idx, (lbl, val) in enumerate(cover_info):
    row = table_cover.rows[idx]
    c1, c2 = row.cells[0], row.cells[1]
    
    p1 = c1.paragraphs[0]
    r1 = p1.add_run(lbl)
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

print("[3/5] Redactando Secciones 1 a 10 (Estructura Institucional)...")

# ----------------------------------------------------
# 1. ELEMENTOS PRELIMINARES
# ----------------------------------------------------
add_custom_heading(doc, "1. Elementos Preliminares", level=1)
add_custom_heading(doc, "1.1. Tabla de Contenido General", level=2)
add_paragraph(doc, "1. Elementos Preliminares (Tabla de Contenido, Índice de Figuras, Glosario)\n2. Introducción y Contexto (Antecedentes, Marco Tecnológico, Situación en Colombia)\n3. Objetivos del Proyecto (General y Específicos)\n4. Alcance del Proyecto (Funcionalidades, Exclusiones y Restricciones)\n5. Planteamiento del Problema y Justificación (Técnica, Social y Ambiental)\n6. Situación Actual del Área / Dominio en Colombia (Marco Legal y Brecha TI)\n7. Método de Desarrollo y Modelo de Ciclo de Vida (Modelo Incremental)\n8. Metodología de Trabajo (Extreme Programming - XP, Roles, Ceremonias)\n9. Requisitos del Sistema (20 Requisitos Funcionales y 8 No Funcionales)\n10. Ficha Técnica / Ficha de Caso Digital\n11. Dimensiones de Gestión del Proyecto (Alcance, Tiempo, Costo, Calidad, RRHH, Comunicaciones, Riesgos)\n12. Stakeholders y Clientes (Usuarios Domésticos, Técnicos TI, Evaluadores)\n13. Restricciones y Matriz de Gestión de Riesgos\n14. Descomposición en Actividades (EDT / WBS de 7 Paquetes)\n15. Estimación de Costos y Tiempos (Presupuesto $50'000.000 COP, Cronograma a 12 meses)\n16. Infraestructura Necesaria (Hardware, Software y Entornos)\n17. Orquestación de Microservicios y Módulos Internos\n18. Ventajas, Desventajas y Aplicabilidad\n19. Gestión del Cliente y Estrategias de Retroalimentación\n20. Evaluación de Viabilidad (Técnica, Económica y Operativa)\n21. Acta de Constitución del Proyecto (Project Charter)\n22. Arquitectura de Software, Evidencia de Código y Componentes Visuales\n23. Control de Cambios del Proyecto")

add_custom_heading(doc, "1.2. Glosario de Siglas y Términos Técnicos", level=2)
add_paragraph(doc, "• WMI (Windows Management Instrumentation): Infraestructura y conjunto de extensiones del SO Microsoft Windows que permite la extracción automatizada de métricas de hardware, rendimiento y servicios.\n• psutil (Process and System Utilities): Biblioteca multiplataforma de bajo nivel en Python que recupera información de uso de CPU, RAM, discos, red y procesos activos.\n• RBAC (Role-Based Access Control): Mecanismo de control de acceso basado en roles para gobernar los privilegios de usuarios administradores, técnicos y usuarios estándar.\n• Health Score: Indicador cuantitativo ponderado (15 a 100) calculado por el motor heurístico para evaluar objetivamente la degradación del equipo.\n• Working Set (RSS): Cantidad de memoria física RAM ocupada activamente por las páginas de un subproceso.\n• PBKDF2-HMAC-SHA256: Algoritmo criptográfico de derivación de claves con salting aleatorio para el resguardo de credenciales.")

# ----------------------------------------------------
# 2. INTRODUCCIÓN Y CONTEXTO
# ----------------------------------------------------
add_custom_heading(doc, "2. Introducción y Contexto", level=1)
add_paragraph(doc, "En la era digital actual, las computadoras personales con sistema operativo Windows se han consolidado como herramientas indispensables en entornos académicos, laborales y domésticos. Sin embargo, la falta de mantenimiento preventivo, la acumulación de archivos residuales, la desactualización de controladores y la presencia de ficheros corruptos provocan una degradación paulatina del rendimiento del sistema.", bold_prefix="2.1. Introducción General: ")
add_paragraph(doc, "FIAX CPU surge como una respuesta tecnológica orientada a democratizar el soporte técnico, permitiendo que usuarios sin habilidades especializadas puedan identificar, diagnosticar y corregir errores comunes en sus equipos con Windows 10 y 11 de forma intuitiva, automatizada y guiada.")

add_paragraph(doc, "Tradicionalmente, el mantenimiento preventivo y la resolución de fallas en Windows se realizan mediante herramientas nativas heterogéneas (como el Administrador de tareas, comprobadores de archivos de sistema por consola de comandos o Windows Update) o mediante la intervención de técnicos especializados. Las soluciones comerciales de terceros suelen ser intrusivas, contienen publicidad o abordan los problemas de forma aislada sin un marco unificado de auditoría.", bold_prefix="2.2. Antecedentes e Intentos Previos: ")

add_paragraph(doc, "El proyecto se fundamenta en la integración de APIs nativas de Microsoft Windows, llamadas Win32 API vía ctypes, psutil y algoritmos heurísticos implementados en Python 3.14+, combinados con una base de datos relacional embebida (SQLite 3 con PRAGMA foreign_keys = ON) y un frontend web reactivo.", bold_prefix="2.3. Tecnología Disponible / Marco Tecnológico: ")

# ----------------------------------------------------
# 3. OBJETIVOS DEL PROYECTO
# ----------------------------------------------------
add_custom_heading(doc, "3. Objetivos del Proyecto", level=1)
add_paragraph(doc, "Desarrollar una plataforma inteligente de diagnóstico, mantenimiento preventivo y solución automatizada de errores para estaciones de trabajo con Windows 10 y 11, capaz de evaluar la salud global del equipo, detectar anomalías de hardware y ejecutar correcciones asistidas con un solo clic, reduciendo la dependencia de soporte técnico externo.", bold_prefix="3.1. Objetivo General: ")

add_custom_heading(doc, "3.2. Objetivos Específicos:", level=2)
add_paragraph(doc, "1. Levantar y priorizar los requisitos funcionales y no funcionales orientados a solventar la degradación progresiva en computadoras con Windows.\n2. Diseñar e implementar un motor heurístico de puntuación de salud (Health Score) que cuantifique el estrés de CPU, memoria RAM, almacenamiento y archivos temporales.\n3. Construir una arquitectura modular en capas que desacople la captura de telemetría, el control de acceso RBAC, la lógica de remediación y la persistencia relacional.\n4. Diseñar una interfaz gráfica intuitiva basada en Diseño Centrado en el Usuario (DCU) con alertas visuales inequívocas categorizadas por nivel de severidad.\n5. Validar el funcionamiento global mediante una suite de 12 pruebas automatizadas y experimentación sobre hardware físico real.")

# ----------------------------------------------------
# 4. ALCANCE DEL PROYECTO
# ----------------------------------------------------
add_custom_heading(doc, "4. Alcance del Proyecto", level=1)
add_paragraph(doc, "• Diagnóstico del equipo e identificación de errores de software y cuellos de botella en hardware.\n• Monitoreo continuo y en tiempo real del uso de CPU, memoria física instalada y espacio en disco.\n• Detección de archivos residuales en el directorio %TEMP% y acumulación de entradas corruptas en la caché DNS.\n• Ejecución de acciones correctivas asistidas (purga de temporales, flushdns, optimización de working set).\n• Registro de cada operación en una pista de auditoría inmutable bajo estándares ISO/IEC 27001.\n• Administración de cuentas de usuario bajo control de acceso granular basado en roles (RBAC).", bold_prefix="4.1. Alcance Funcional (Incluye): ")

add_paragraph(doc, "• Reparación de daños físicos de hardware (soldaduras, pistas rotas, sectores defectuosos mecánicos).\n• Recuperación de datos eliminados o servicios forenses avanzados.\n• Soporte para sistemas operativos no Windows (Linux, macOS, Android, iOS).\n• Administración remota masiva cliente-servidor para infraestructuras corporativas.", bold_prefix="4.2. Exclusiones Explícitas (No Incluye): ")

# ----------------------------------------------------
# 5. PLANTEAMIENTO DEL PROBLEMA Y JUSTIFICACIÓN
# ----------------------------------------------------
add_custom_heading(doc, "5. Planteamiento del Problema y Justificación", level=1)
add_paragraph(doc, "Los usuarios finales de estaciones de trabajo Windows experimentan de forma recurrente lentitud, sobrecalentamiento, bloqueos intempestivos y saturación de recursos. Esta degradación silenciosa genera pérdidas de productividad y gastos reiterados en servicios técnicos básicos. La ausencia de un asistente centralizado y comprensible dificulta el mantenimiento preventivo oportuno.", bold_prefix="5.1. Planteamiento del Problema: ")

add_paragraph(doc, "FIAX CPU se justifica técnicamente al sustituir herramientas intrusivas por una solución ligera y gobernada en capas. Socialmente, reduce la brecha digital al explicar los problemas en lenguaje sencillo. Ambientalmente, alarga la vida útil de los equipos de cómputo entre un 20% y 30%, mitigando la proliferación de residuos electrónicos (e-waste).", bold_prefix="5.2. Justificación: ")

# ----------------------------------------------------
# 6. MÉTODO DE DESARROLLO Y METODOLOGÍA
# ----------------------------------------------------
add_custom_heading(doc, "6. Metodología de Trabajo y Modelo de Ciclo de Vida", level=1)
add_paragraph(doc, "Se seleccionó el Modelo Incremental guiado por la metodología ágil Extreme Programming (XP), estructurado en incrementos funcionales acumulativos: Diagnóstico Básico, Monitoreo de Hardware, Detección de Inconsistencias, Motor Heurístico, Módulo de Remediación y Módulo de Reportes/Auditoría.")
add_paragraph(doc, "• Erick Santiago García Sánchez: Líder de Proyecto / Desarrollador Backend & Integración Hardware.\n• Eider Sebastián Ortiz Botina: Desarrollador Frontend / Diseñador UX & Especialista QA.\n• Oscar David Gutiérrez Molina: Ingeniero de Lógica Heurística / Integración de Algoritmos.", bold_prefix="Roles del Equipo de Trabajo: ")

# ----------------------------------------------------
# 7. REQUISITOS DEL SISTEMA
# ----------------------------------------------------
add_custom_heading(doc, "7. Requisitos Funcionales y No Funcionales del Sistema", level=1)
add_paragraph(doc, "• RF01: Iniciar escaneo heurístico completo a solicitud del usuario.\n• RF02: Capturar telemetría en tiempo real de núcleos de CPU, RAM usada/libre y capacidad de disco.\n• RF03: Identificar archivos residuales en el directorio temporal (%TEMP%) y tamaño acumulado.\n• RF04: Detectar problemas de resolución en la caché DNS local.\n• RF05: Calcular el Health Score del equipo acotado en el intervalo [15, 100].\n• RF06: Categorizar incidencias según severidad (BAJO, MEDIO, ALTO, CRITICO).\n• RF07: Ejecutar purga segura de temporales omitiendo archivos en uso por el sistema.\n• RF08: Ejecutar vaciado de caché DNS (ipconfig /flushdns) de forma transparente.\n• RF09: Optimizar memoria RAM recortando el Working Set de aplicaciones inactivas.\n• RF10: Registrar cada evento en la tabla de auditoría inmutable (auditoria_logs).\n• RF11: Autenticar usuarios con contraseñas cifradas en PBKDF2-HMAC-SHA256.\n• RF12: Gestionar roles y permisos mediante panel de administración RBAC.", bold_prefix="Requisitos Funcionales Principales: ")

add_paragraph(doc, "• RNF01: Compatibilidad nativa exclusiva con Windows 10 y Windows 11.\n• RNF02: Tiempo de respuesta menor a 500 ms en consultas de telemetría.\n• RNF03: Interfaz intuitiva y accesible para usuarios sin formación técnica previa.\n• RNF04: Integridad referencial asegurada con PRAGMA foreign_keys = ON en SQLite.\n• RNF05: Operación con consumo de memoria menor a 80 MB en estado estacionario.", bold_prefix="Requisitos No Funcionales: ")

# ----------------------------------------------------
# 8. GESTIÓN DEL PROYECTO Y CRONOGRAMA
# ----------------------------------------------------
add_custom_heading(doc, "8. Dimensiones de Gestión, Presupuesto y Riesgos", level=1)
add_paragraph(doc, "El proyecto cuenta con un presupuesto global proyectado de $50'000.000 COP, distribuido en: Talento Humano (58.0% - $29'000.000), Infraestructura Cloud y Licenciamiento (26.4% - $13'200.000), Capacitación Especializada (7.6% - $3'800.000) y Reserva de Contingencia (8.0% - $4'000.000).")

# Matriz de Riesgos
table_risk = doc.add_table(rows=5, cols=4)
table_risk.alignment = WD_TABLE_ALIGNMENT.CENTER
table_risk.columns[0].width = Inches(1.0)
table_risk.columns[1].width = Inches(2.3)
table_risk.columns[2].width = Inches(1.2)
table_risk.columns[3].width = Inches(2.0)

r_hdr = table_risk.rows[0]
for idx, tit in enumerate(["Código", "Riesgo Identificado", "Impacto / Prob.", "Estrategia de Mitigación"]):
    p = r_hdr.cells[idx].paragraphs[0]
    r = p.add_run(tit)
    r.bold = True
    r.font.name = "Segoe UI"
    r.font.size = Pt(9)
    tcPr = r_hdr.cells[idx]._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="E2E8F0"/>')
    tcPr.append(shd)

risks_data = [
    ("R01", "Incompatibilidad con parches de Windows 11", "Alto / Media", "Uso exclusivo de APIs estables de Microsoft y psutil."),
    ("R02", "Bloqueo por permisos de administrador UAC", "Medio / Alta", "Captura de excepciones y mensajes guiados en la interfaz."),
    ("R03", "Archivos bloqueados en el directorio %TEMP%", "Bajo / Alta", "Omisión segura mediante cláusula try-except OSError."),
    ("R04", "Eliminación involuntaria del único Administrador", "Crítico / Baja", "Validación estricta en el controlador: count <= 1 -> 400.")
]

for idx, (c, r, ip, m) in enumerate(risks_data):
    row = table_risk.rows[idx + 1]
    for c_idx, val in enumerate([c, r, ip, m]):
        cell = row.cells[c_idx]
        p = cell.paragraphs[0]
        p.add_run(val).font.size = Pt(8.5)
        tcPr = cell._tc.get_or_add_tcPr()
        fill = "F8FAFC" if idx % 2 == 0 else "FFFFFF"
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>'))

doc.add_page_break()

print("[4/5] Redactando Secciones 22: Arquitectura, Modelos, Servicios y Evidencias Visuales...")

# ----------------------------------------------------
# 9. ARQUITECTURA Y MODELO DE DATOS (DETALLE TÉCNICO)
# ----------------------------------------------------
add_custom_heading(doc, "9. Arquitectura de Software y Modelo de Datos Relacional", level=1)

add_paragraph(doc, "FIAX CPU implementa una Arquitectura en Capas de alta cohesión y bajo acoplamiento. La capa de presentación web se comunica con los controladores mediante peticiones asíncronas JSON, los cuales delegan en servicios de dominio y resguardan las transacciones mediante SQLAlchemy ORM.")

add_image_with_caption(doc, "doc_images/01_arquitectura_sistema.png", "Diagrama de Arquitectura de 5 Capas de la Plataforma FIAX CPU")

add_image_with_caption(doc, "doc_images/02_modelo_datos_erd.png", "Diagrama Entidad-Relación de Base de Datos SQLite 3 (9 Tablas Relacionadas)")

code_db_init = '''# domain/models.py - Activación de Integridad Referencial en SQLite 3
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Fuerza la ejecución de PRAGMA foreign_keys = ON para evitar inconsistencias."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()'''
add_code_block(doc, code_db_init, "domain/models.py - Activación de Foreign Keys")

# ----------------------------------------------------
# 10. SEGURIDAD, RBAC Y CRIPTOGRAFÍA
# ----------------------------------------------------
add_custom_heading(doc, "10. Seguridad Criptográfica y Control de Acceso (RBAC)", level=1)

add_paragraph(doc, "La plataforma cuenta con control de acceso basado en roles (RBAC) con tres jerarquías: ADMINISTRADOR (control total), TECNICO (diagnóstico y remediación) y USUARIO (vista de salud). Cada acción crítica está resguardada por el decorador @has_permission.")

code_rbac = '''# security/decorators.py - Validación Granular de Permisos
def has_permission(required_permission):
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
add_code_block(doc, code_rbac, "security/decorators.py - Decorador @has_permission")

# ----------------------------------------------------
# 11. MOTOR HEURÍSTICO Y FÓRMULA DE SALUD
# ----------------------------------------------------
add_custom_heading(doc, "11. Motor Heurístico y Algoritmo de Health Score", level=1)

add_paragraph(doc, "El estado técnico del computador anfitrión se traduce en una escala cuantitativa de 15 a 100 puntos mediante la función de Health Score ponderada, penalizando cuellos de botella en hardware y severidad de incidencias halladas:")

add_paragraph(doc, "H = max(15, min(100, 100 - (P_cpu + P_ram + P_disco + P_temp + sum(w_k))))", bold_prefix="Formulación Matemática: ")

add_image_with_caption(doc, "doc_images/11_ui_health_score_gauge.png", "Ficha Técnica del Host y Medidor Numérico de Health Score")

code_score = '''# services/diagnostic_service.py - Algoritmo Heurístico Ponderado
@staticmethod
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
add_code_block(doc, code_score, "services/diagnostic_service.py - calculate_health_score()")

# ----------------------------------------------------
# 12. CATÁLOGO VISUAL DE COMPONENTES FRONTEND
# ----------------------------------------------------
add_custom_heading(doc, "12. Catálogo Visual de Componentes Frontend (Botón por Botón, Color y Acción)", level=1)

add_paragraph(doc, "En este apartado se detalla cada elemento visual de la plataforma, evidenciando el código HTML de su estructura, el código CSS que define su color exacto, su manejador JavaScript y el código de backend en Python que se activa al presionarlo.")

# --- Componente 1: Botón Logout Rojo ---
add_custom_heading(doc, "12.1. Botón Rojo de Cierre de Sesión (Sidebar & Header)", level=2)
add_paragraph(doc, "Permite finalizar de inmediato la sesión del usuario activo y eliminar las variables de autenticación en el servidor.")

add_image_with_caption(doc, "doc_images/03_ui_boton_logout_rojo.png", "Estados Visuales del Botón Rojo de Cierre de Sesión (.btn-logout-sidebar)")

code_c1_html = '''<!-- templates/dashboard.html - Líneas 933-938 -->
<div class="sidebar-footer">
    <a href="/logout" class="btn-logout-sidebar">
        <i class="fa-solid fa-arrow-right-from-bracket"></i>
        <span>Cerrar Sesión Activa</span>
    </a>
</div>'''
add_code_block(doc, code_c1_html, "HTML: Marcado del Botón de Logout")

code_c1_css = '''/* Reglas CSS que definen el color rojo #ef4444 */
.btn-logout-sidebar {
    background-color: rgba(239, 68, 68, 0.12); /* Fondo rojo translúcido */
    color: #f87171;                             /* Texto en rojo claro */
    border: 1px solid rgba(239, 68, 68, 0.35);  /* Borde rojo de advertencia */
    padding: 12px;
    border-radius: 8px;
    font-weight: 700;
}
.btn-logout-sidebar:hover {
    background-color: #ef4444;                  /* Rojo sólido puro al hover */
    color: white;
    box-shadow: 0 4px 15px rgba(239, 68, 68, 0.4);
}'''
add_code_block(doc, code_c1_css, "CSS: Reglas del Botón Rojo de Logout")

code_c1_py = '''# controllers/auth_controller.py - Endpoint /logout
@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    if user_id:
        AuditService.registrar(
            accion="CIERRE_SESION", modulo="AUTH",
            detalles=f"Usuario {user_name} cerró sesión.", usuario_id=user_id
        )
    session.clear() # Destruye las cookies y sesión
    return redirect(url_for('index')) # Redirige al login'''
add_code_block(doc, code_c1_py, "Python: Lógica de Cierre de Sesión y Auditoría")

# --- Componente 2: Botón Eliminar Rojo ---
add_custom_heading(doc, "12.2. Botón Rojo de Eliminación de Usuario (CRUD RBAC)", level=2)
add_paragraph(doc, "Dispara la solicitud asíncrona de eliminación permanente de una cuenta de usuario con protecciones de seguridad en el backend.")

add_image_with_caption(doc, "doc_images/04_ui_boton_eliminar_rojo.png", "Botón Rojo de Eliminación con Reglas de Seguridad y Validación")

code_c2_css = '''/* CSS: Botón Rojo de Peligro #dc2626 */
.btn-delete {
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
add_code_block(doc, code_c2_css, "CSS: Estilos del Botón de Eliminación")

code_c2_js = '''// templates/usuarios.html - Invocación Fetch DELETE
async function deleteUser(id) {
    if (!confirm("¿Está seguro de que desea eliminar este usuario del sistema?")) return;
    try {
        const res = await fetch(`/api/v1/users/${id}`, { method: 'DELETE' });
        const result = await res.json();
        if (res.ok) {
            loadUsers(); // Recarga dinámica de tabla
        } else {
            alert("Error: " + (result.error || "No se pudo eliminar el usuario."));
        }
    } catch (err) { alert("Error de conexión al servidor."); }
}'''
add_code_block(doc, code_c2_js, "JavaScript: Manejador Asíncrono de Eliminación")

code_c2_py = '''# controllers/role_controller.py - Protecciones en Endpoint DELETE
@role_bp.route('/users/<int:user_id>', methods=['DELETE'])
@has_permission(PermissionEnum.USER_CREATE)
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user: return jsonify({"error": "Usuario no encontrado."}), 404
    
    # 1. Protección contra auto-eliminación
    if user.id == session.get('user_id'):
        return jsonify({"error": "No puede eliminar su propia cuenta activa."}), 400
        
    # 2. Protección contra eliminación del único administrador
    es_admin = any(r.nombre == RoleEnum.ADMINISTRADOR.value for r in user.roles)
    if es_admin:
        admin_count = User.query.filter(User.roles.any(Role.nombre == RoleEnum.ADMINISTRADOR.value)).count()
        if admin_count <= 1:
            return jsonify({"error": "No se puede eliminar el único Administrador del sistema."}), 400
            
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Usuario eliminado exitosamente."})'''
add_code_block(doc, code_c2_py, "Python: Validaciones de Integridad y Protección")

# --- Componente 3: Modal Emergente Rojo de Error ---
add_custom_heading(doc, "12.3. Modal Emergente Rojo de Credenciales Inválidas", level=2)
add_paragraph(doc, "Ventana emergente que bloquea la interacción en el login al producirse un fallo de autenticación.")

add_image_with_caption(doc, "doc_images/05_ui_modal_error_rojo.png", "Modal Emergente de Error con Borde, Icono y Botón Rojo #ef4444")

code_c3_css = '''/* CSS: Modal Rojo de Advertencia */
.popup {
    background-color: #1e293b;
    padding: 25px;
    border-radius: 14px;
    border: 1px solid #ef4444;                     /* Borde rojo */
    box-shadow: 0 10px 25px rgba(239, 68, 68, 0.2);/* Resplandor rojo */
}
.popup-icon {
    font-size: 40px;
    color: #ef4444;                                 /* Icono rojo */
    margin-bottom: 10px;
}
.popup-btn {
    background-color: #ef4444;                     /* Botón aceptar rojo */
    color: white;
    padding: 10px 25px;
    border-radius: 6px;
    font-weight: bold;
}
.popup-btn:hover { background-color: #dc2626; }'''
add_code_block(doc, code_c3_css, "CSS: Estilos del Modal Rojo de Error")

# --- Componente 4: Botón Azul Diagnóstico ---
add_custom_heading(doc, "12.4. Botón Azul de Ejecución de Diagnóstico Heurístico", level=2)
add_paragraph(doc, "Activa el escaneo en vivo del hardware, despliega el modal animado con etapas de inspección y actualiza las métricas en pantalla.")

add_image_with_caption(doc, "doc_images/06_ui_boton_diagnostico_azul.png", "Botón Azul con Gradiente y Modal de Diagnóstico en Curso")

code_c4_css = '''/* CSS: Gradiente Azul de Acción Primaria */
.btn-primary {
    background: linear-gradient(135deg, #0284c7, #2563eb); /* Gradiente cyan-azul */
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
add_code_block(doc, code_c4_css, "CSS: Gradiente Azul del Botón Primario")

# --- Componente 5: Botón Verde Mantenimiento ---
add_custom_heading(doc, "12.5. Botón Verde de Mantenimiento Rápido en Un Clic", level=2)
add_paragraph(doc, "Lanza de forma secuencial la purga de temporales, vaciado de caché DNS y optimización física de memoria RAM.")

add_image_with_caption(doc, "doc_images/07_ui_boton_mantenimiento_verde.png", "Botón Verde Esmeralda de Mantenimiento Global y Rutinas Físicas")

code_c5_css = '''/* CSS: Verde Esmeralda #10b981 */
.btn-success {
    background-color: #10b981; /* Verde esmeralda */
    color: white;
    padding: 10px 18px;
    border-radius: 8px;
    font-weight: 700;
    border: none;
    cursor: pointer;
}
.btn-success:hover {
    background-color: #059669; /* Verde oscuro al hover */
}'''
add_code_block(doc, code_c5_css, "CSS: Estilos del Botón Verde de Mantenimiento")

code_c5_py = '''# services/maintenance_service.py - Rutinas de Limpieza Real
@staticmethod
def clean_temporary_files():
    temp_dir = os.environ.get('TEMP') or os.environ.get('TMP')
    archivos_eliminados, bytes_liberados = 0, 0
    for entry in os.scandir(temp_dir):
        try:
            if entry.is_file(follow_symlinks=False):
                size = entry.stat().st_size
                os.remove(entry.path) # Purga física de archivo
                bytes_liberados += size
                archivos_eliminados += 1
        except Exception: continue
    return {"success": True, "mb_liberados": round(bytes_liberados/(1024*1024), 2)}

@staticmethod
def flush_dns_cache():
    res = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True,
                         creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    return {"success": True, "mensaje": res.stdout.strip()}

@staticmethod
def optimize_memory():
    import ctypes
    gc.collect() # Recolección de basura Python
    for proc in psutil.process_iter(['pid']):
        try:
            handle = ctypes.windll.kernel32.OpenProcess(0x001F0FFF, False, proc.info['pid'])
            if handle:
                ctypes.windll.psapi.EmptyWorkingSet(handle) # Recorte de Working Set Win32
                ctypes.windll.kernel32.CloseHandle(handle)
        except Exception: pass
    return {"success": True, "mensaje": "Working Set optimizado exitosamente"}'''
add_code_block(doc, code_c5_py, "Python: Implementación de Remediación FÍSICA de Sistema")

# --- Componente 6: Botón Ámbar Editar ---
add_custom_heading(doc, "12.6. Botón Ámbar / Naranja de Edición de Usuario", level=2)
add_paragraph(doc, "Abre el formulario modal de edición cargando los valores actuales de la cuenta para modificar nombre, credenciales o rol asignado.")

add_image_with_caption(doc, "doc_images/08_ui_boton_editar_naranja.png", "Botón Ámbar de Edición y Formulario Modal de Modificación")

code_c6_css = '''/* CSS: Botón Ámbar / Naranja #d97706 */
.btn-edit {
    background-color: #d97706; /* Color ámbar/naranja */
    color: white;
    border: none;
    padding: 7px 12px;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 700;
    font-size: 12px;
}
.btn-edit:hover {
    background-color: #b45309; /* Naranja más oscuro al hover */
}'''
add_code_block(doc, code_c6_css, "CSS: Estilos del Botón de Edición")

# --- Componente 7: Badges de Severidad ---
add_custom_heading(doc, "12.7. Matriz Cromática de Insignias de Severidad", level=2)
add_paragraph(doc, "Clasifica visualmente las anomalías en cuatro niveles normalizados:")

add_image_with_caption(doc, "doc_images/09_ui_badges_severidad.png", "Insignias de Severidad e Indicadores de Estado de Incidencia")

code_c7_css = '''/* CSS: 4 Niveles de Severidad */
.badge-sev.CRITICO { background-color: rgba(239, 68, 68, 0.25); color: #f87171; border: 1px solid #ef4444; }
.badge-sev.ALTO    { background-color: rgba(249, 115, 22, 0.25); color: #fb923c; border: 1px solid #f97316; }
.badge-sev.MEDIO   { background-color: rgba(245, 158, 11, 0.25); color: #fbbf24; border: 1px solid #f59e0b; }
.badge-sev.BAJO    { background-color: rgba(59, 130, 246, 0.25);  color: #60a5fa; border: 1px solid #3b82f6; }'''
add_code_block(doc, code_c7_css, "CSS: Clases de Severidad de Incidencias")

# --- Componente 8: Tarjetas de Telemetría ---
add_custom_heading(doc, "12.8. Tarjetas de Telemetría con Barras de Progreso Dinámicas", level=2)
add_paragraph(doc, "Monitorea continuamente la estación física con actualización asíncrona cada 8 segundos:")

add_image_with_caption(doc, "doc_images/10_ui_metric_cards_telemetria.png", "Tarjetas de Telemetría en Tiempo Real con psutil")

# ----------------------------------------------------
# 13. PRUEBAS AUTOMATIZADAS Y CERTIFICACIÓN
# ----------------------------------------------------
add_custom_heading(doc, "13. Batería de Pruebas Automatizadas y Certificación Técnica", level=1)

add_paragraph(doc, "La estabilidad y cumplimiento normativo de la plataforma se certificó mediante 12 pruebas unitarias e integrales en tests/test_fiax.py, ejecutadas sin simuladores sobre la estación física real.")

add_image_with_caption(doc, "doc_images/12_test_results_summary.png", "Certificación Técnica: 12/12 Pruebas Unitarias Pasadas (100% OK en 4.071s)")

# ----------------------------------------------------
# 14. CONTROL DE CAMBIOS
# ----------------------------------------------------
add_custom_heading(doc, "14. Control de Cambios del Proyecto", level=1)

table_ctrl = doc.add_table(rows=3, cols=6)
table_ctrl.alignment = WD_TABLE_ALIGNMENT.CENTER
table_ctrl.columns[0].width = Inches(0.8)
table_ctrl.columns[1].width = Inches(0.6)
table_ctrl.columns[2].width = Inches(2.2)
table_ctrl.columns[3].width = Inches(1.3)
table_ctrl.columns[4].width = Inches(1.0)
table_ctrl.columns[5].width = Inches(1.0)

hdr_c = table_ctrl.rows[0]
for idx, tit in enumerate(["Fecha", "Versión", "Descripción del Cambio", "Elaboró", "Revisó", "Aprobó"]):
    p = hdr_c.cells[idx].paragraphs[0]
    p.add_run(tit).bold = True
    tcPr = hdr_c.cells[idx]._tc.get_or_add_tcPr()
    tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="E2E8F0"/>'))

ctrl_data = [
    ("21/08/2026", "01", "Primera entrega y definición de requerimientos del sistema", "E. García, E. Ortiz, O. Gutiérrez", "Docente Fredy Ordoñez", "Docente ETITC"),
    ("20/09/2026", "02", "Documento técnico y código de componentes de entrega final corte 1", "E. García, E. Ortiz, O. Gutiérrez", "Docente Fredy Ordoñez", "Docente ETITC")
]

for idx, row_vals in enumerate(ctrl_data):
    row = table_ctrl.rows[idx + 1]
    for c_idx, val in enumerate(row_vals):
        row.cells[c_idx].paragraphs[0].add_run(val).font.size = Pt(8.5)
        tcPr = row.cells[c_idx]._tc.get_or_add_tcPr()
        fill = "F8FAFC" if idx % 2 == 0 else "FFFFFF"
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill}"/>'))

print("[5/5] Guardando documento Word definitivo...")
final_path = "MANUAL_TECNICO_FIAX_CPU.docx"
doc.save(final_path)
print(f"¡Documento institucional generado exitosamente como '{final_path}'!")

