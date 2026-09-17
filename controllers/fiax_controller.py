from flask import Blueprint, jsonify, request, session
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.maintenance_service import MaintenanceService
from services.audit_service import AuditService
from domain.models import IncidenciaDetectada, SesionDiagnostico, LogAuditoria
from security.decorators import has_permission
from domain.enums import PermissionEnum

fiax_bp = Blueprint('fiax_bp', __name__, url_prefix='/api/v1/fiax')

@fiax_bp.route('/telemetria', methods=['GET'])
def get_telemetria():
    """Retorna telemetría viva de hardware y sistema operativo."""
    metrics = TelemetryService.get_live_metrics()
    equipo = TelemetryService.get_hardware_profile()
    return jsonify({
        "success": True,
        "equipo": equipo,
        "metricas": metrics
    })

@fiax_bp.route('/diagnostico/ejecutar', methods=['POST'])
def ejecutar_diagnostico():
    """Dispara un análisis heurístico completo del sistema."""
    user_id = session.get('user_id')
    resultado = DiagnosticService.execute_complete_diagnosis(user_id=user_id)
    if resultado.get('success'):
        return jsonify(resultado), 200
    return jsonify(resultado), 500

@fiax_bp.route('/incidencias', methods=['GET'])
def get_incidencias():
    """Consulta incidencias registradas en la base de datos."""
    estado_filtro = request.args.get('estado')
    query = IncidenciaDetectada.query.order_by(IncidenciaDetectada.id.desc())
    if estado_filtro:
        query = query.filter_by(estado=estado_filtro)
    
    incidencias = query.limit(50).all()
    return jsonify({
        "success": True,
        "incidencias": [i.to_dict() for i in incidencias]
    })

@fiax_bp.route('/incidencias/<int:incidencia_id>/resolver', methods=['POST'])
def resolver_incidencia(incidencia_id):
    """Aplica la acción correctiva asistida para una incidencia."""
    user_id = session.get('user_id')
    resultado = MaintenanceService.resolve_incident(incidencia_id, user_id=user_id)
    if resultado.get('success'):
        return jsonify(resultado), 200
    return jsonify(resultado), 400

@fiax_bp.route('/mantenimiento/optimizar', methods=['POST'])
def optimizacion_rapida():
    """Ejecuta una rutina integral de optimización: temporales, DNS y memoria."""
    user_id = session.get('user_id')
    
    res_temp = MaintenanceService.clean_temporary_files()
    res_dns = MaintenanceService.flush_dns_cache()
    res_mem = MaintenanceService.optimize_memory()

    AuditService.registrar(
        accion="OPTIMIZACION_INTEGRAL",
        modulo="MANTENIMIENTO",
        detalles=f"Optimización manual ejecutada. Temporales: {res_temp.get('mb_liberados')} MB. RAM reducida en {res_mem.get('reduccion_porcentaje')}%.",
        nivel="INFO",
        usuario_id=user_id
    )

    return jsonify({
        "success": True,
        "mensaje": "Optimización del sistema completada exitosamente.",
        "resultados": {
            "temporales": res_temp,
            "dns": res_dns,
            "memoria": res_mem
        }
    })

@fiax_bp.route('/auditoria', methods=['GET'])
def get_auditoria():
    """Consulta los eventos más recientes de la pista de auditoría."""
    logs = AuditService.obtener_ultimos_logs(limite=50)
    return jsonify({
        "success": True,
        "logs": [l.to_dict() for l in logs]
    })

@fiax_bp.route('/historial', methods=['GET'])
def get_historial():
    """Consulta las sesiones de diagnóstico históricas."""
    sesiones = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).limit(20).all()
    return jsonify({
        "success": True,
        "sesiones": [s.to_dict() for s in sesiones]
    })
