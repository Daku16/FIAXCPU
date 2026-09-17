from flask import request, session
from domain.models import db, LogAuditoria

class AuditService:
    @staticmethod
    def registrar(accion: str, modulo: str, detalles: str = "", nivel: str = "INFO", usuario_id: int = None, ip_origen: str = None):
        """Registra un evento en la pista de auditoría del sistema."""
        try:
            if usuario_id is None and session:
                usuario_id = session.get('user_id')
                
            if ip_origen is None:
                try:
                    ip_origen = request.remote_addr if request else "127.0.0.1"
                except Exception:
                    ip_origen = "127.0.0.1"

            log = LogAuditoria(
                usuario_id=usuario_id,
                modulo=modulo,
                accion=accion,
                detalles=detalles,
                ip_origen=ip_origen,
                nivel=nivel
            )
            db.session.add(log)
            db.session.commit()
            return log
        except Exception as e:
            # La auditoría nunca debe romper la ejecución principal si hay un fallo
            try:
                db.session.rollback()
            except Exception:
                pass
            print(f"[AUDIT_ERROR] No se pudo registrar auditoría: {e}")
            return None

    @staticmethod
    def obtener_ultimos_logs(limite: int = 50):
        """Recupera los eventos de auditoría más recientes."""
        return LogAuditoria.query.order_by(LogAuditoria.id.desc()).limit(limite).all()

