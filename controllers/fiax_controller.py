import os
import threading
import time

from flask import Blueprint, current_app, jsonify, request, session
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.maintenance_service import MaintenanceService
from services.audit_service import AuditService
from services.comparison_service import ComparisonService
from domain.models import IncidenciaDetectada, SesionDiagnostico, LogAuditoria
from security.decorators import has_permission, login_required
from domain.enums import PermissionEnum

fiax_bp = Blueprint('fiax_bp', __name__, url_prefix='/api/v1/fiax')

@fiax_bp.route('/telemetria', methods=['GET'])
@login_required
def get_telemetria():
    """Retorna telemetría viva de hardware y sistema operativo."""
    try:
        metrics = TelemetryService.get_live_metrics()
        equipo = TelemetryService.get_hardware_profile()
    except Exception as exc:
        return jsonify({"success": False, "error": f"No se pudieron leer las métricas: {exc}"}), 503
    return jsonify({
        "success": True,
        "equipo": equipo,
        "metricas": metrics
    })

@fiax_bp.route('/diagnostico/ejecutar', methods=['POST'])
@has_permission(PermissionEnum.DIAGNOSTIC_RUN)
def ejecutar_diagnostico():
    """Dispara un análisis heurístico completo del sistema."""
    user_id = session.get('user_id')
    resultado = DiagnosticService.execute_complete_diagnosis(user_id=user_id)
    if resultado.get('success'):
        return jsonify(resultado), 200
    return jsonify(resultado), 500

@fiax_bp.route('/incidencias', methods=['GET'])
@login_required
def get_incidencias():
    """Consulta incidencias registradas en la base de datos."""
    estado_filtro = request.args.get('estado')
    sesion_id = request.args.get('sesion_id')
    query = IncidenciaDetectada.query.order_by(IncidenciaDetectada.id.desc())
    if estado_filtro:
        query = query.filter_by(estado=estado_filtro)
    if sesion_id:
        query = query.filter_by(diagnostico_id=sesion_id)
    
    incidencias = query.limit(50).all()
    
    pendientes_count = IncidenciaDetectada.query.filter_by(estado='PENDIENTE').count()
    resueltas_count = IncidenciaDetectada.query.filter_by(estado='RESUELTA').count()

    return jsonify({
        "success": True,
        "incidencias": [i.to_dict() for i in incidencias],
        "pendientes_count": pendientes_count,
        "resueltas_count": resueltas_count
    })

@fiax_bp.route('/incidencias/<int:incidencia_id>/resolver', methods=['POST'])
@has_permission(PermissionEnum.FIX_EXECUTE)
def resolver_incidencia(incidencia_id):
    """Aplica la acción correctiva asistida para una incidencia."""
    user_id = session.get('user_id')
    resultado = MaintenanceService.resolve_incident(incidencia_id, user_id=user_id)
    if resultado.get('success'):
        return jsonify(resultado), 200
    return jsonify(resultado), 400

@fiax_bp.route('/mantenimiento/optimizar', methods=['POST'])
@has_permission(PermissionEnum.MAINTENANCE_RUN)
def optimizacion_rapida():
    """Ejecuta temporales, dns, memoria o global y devuelve la comparación antes/después."""
    data = request.get_json(silent=True) or {}
    tipo = data.get('tipo') or request.args.get('tipo', 'global')
    resultado = MaintenanceService.run_procedure(tipo, user_id=session.get('user_id'))
    # Un procedimiento que no pudo completarse también devuelve su comparación.
    return jsonify(resultado), 200 if 'comparacion' in resultado else 400

@fiax_bp.route('/estado-actual', methods=['GET'])
@login_required
def estado_actual():
    """Estado del equipo que se usará como punto de partida de un procedimiento."""
    return jsonify({"success": True, "estado": ComparisonService.build_rows(*[ComparisonService.capture_state()] * 2)})

@fiax_bp.route('/comparaciones', methods=['GET'])
@has_permission(PermissionEnum.REPORT_READ)
def get_comparaciones():
    """Historial de comparaciones entre estado inicial y final."""
    return jsonify({"success": True, "comparaciones": ComparisonService.history()})

@fiax_bp.route('/sistema/cerrar', methods=['POST'])
@login_required
def cerrar_aplicacion():
    """Detiene la versión de escritorio, que no tiene otra ventana desde la cual cerrarse."""
    if not current_app.config.get('ALLOW_SHUTDOWN'):
        return jsonify({"error": "Disponible solo en la versión de escritorio."}), 404
    threading.Thread(target=lambda: (time.sleep(0.5), os._exit(0)), daemon=True).start()
    return jsonify({"success": True})

@fiax_bp.route('/auditoria', methods=['GET'])
@has_permission(PermissionEnum.AUDIT_READ)
def get_auditoria():
    """Consulta los eventos más recientes de la pista de auditoría."""
    logs = AuditService.obtener_ultimos_logs(limite=50)
    return jsonify({
        "success": True,
        "logs": [l.to_dict() for l in logs]
    })

@fiax_bp.route('/historial', methods=['GET'])
@login_required
def get_historial():
    """Consulta las sesiones de diagnóstico históricas."""
    sesiones = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).limit(20).all()
    return jsonify({
        "success": True,
        "sesiones": [s.to_dict() for s in sesiones]
    })
