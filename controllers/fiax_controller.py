from flask import Blueprint, jsonify, request, session
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.maintenance_service import MaintenanceService
from services.audit_service import AuditService
from domain.models import IncidenciaDetectada, SesionDiagnostico, LogAuditoria
from security.decorators import has_permission, login_required
from domain.enums import PermissionEnum

fiax_bp = Blueprint('fiax_bp', __name__, url_prefix='/api/v1/fiax')

@fiax_bp.route('/telemetria', methods=['GET'])
@login_required
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
    """Ejecuta rutinas de optimización individuales (temporales, dns, memoria) o integral (global)."""
    user_id = session.get('user_id')
    
    data = request.get_json(silent=True) or {}
    tipo = data.get('tipo') or request.args.get('tipo', 'global')

    if tipo == 'temporales':
        res_temp = MaintenanceService.clean_temporary_files()
        AuditService.registrar(
            accion="LIMPIEZA_TEMPORALES",
            modulo="MANTENIMIENTO",
            detalles=f"Purga de temporales: {res_temp.get('mb_liberados')} MB liberados ({res_temp.get('archivos_eliminados')} archivos).",
            nivel="INFO",
            usuario_id=user_id
        )
        return jsonify({
            "success": True,
            "tipo": "temporales",
            "mensaje": res_temp.get('mensaje') or f"Limpieza completada: {res_temp.get('mb_liberados')} MB liberados.",
            "resultados": {"temporales": res_temp}
        })

    elif tipo == 'dns':
        res_dns = MaintenanceService.flush_dns_cache()
        AuditService.registrar(
            accion="VACIADO_CACHE_DNS",
            modulo="MANTENIMIENTO",
            detalles="Vaciado y refresco de caché DNS en el sistema anfitrión.",
            nivel="INFO",
            usuario_id=user_id
        )
        return jsonify({
            "success": True,
            "tipo": "dns",
            "mensaje": res_dns.get('mensaje') or "Se vació correctamente la caché de resolución DNS.",
            "resultados": {"dns": res_dns}
        })

    elif tipo == 'memoria':
        res_mem = MaintenanceService.optimize_memory()
        AuditService.registrar(
            accion="OPTIMIZACION_MEMORIA",
            modulo="MANTENIMIENTO",
            detalles=f"Compactación de Working Set y liberación de páginas de RAM. Reducción: {res_mem.get('reduccion_porcentaje')}%.",
            nivel="INFO",
            usuario_id=user_id
        )
        return jsonify({
            "success": True,
            "tipo": "memoria",
            "mensaje": res_mem.get('mensaje') or "Optimización de memoria RAM completada.",
            "resultados": {"memoria": res_mem}
        })

    # 'global' por defecto
    res_temp = MaintenanceService.clean_temporary_files()
    res_dns = MaintenanceService.flush_dns_cache()
    res_mem = MaintenanceService.optimize_memory()

    AuditService.registrar(
        accion="OPTIMIZACION_INTEGRAL",
        modulo="MANTENIMIENTO",
        detalles=f"Optimización rápida ejecutada. Temporales: {res_temp.get('mb_liberados')} MB. RAM reducida en {res_mem.get('reduccion_porcentaje')}%.",
        nivel="INFO",
        usuario_id=user_id
    )

    return jsonify({
        "success": True,
        "tipo": "global",
        "mensaje": "Optimización integral completada exitosamente.",
        "resultados": {
            "temporales": res_temp,
            "dns": res_dns,
            "memoria": res_mem
        }
    })

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
