from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

# Tablas Asociativas Muchos a Muchos
user_roles = db.Table('user_roles',
    db.Column('user_id', db.Integer, db.ForeignKey('usuarios.id', ondelete="CASCADE"), primary_key=True),
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True)
)

role_permissions = db.Table('role_permissions',
    db.Column('role_id', db.Integer, db.ForeignKey('roles.id', ondelete="CASCADE"), primary_key=True),
    db.Column('permission_id', db.Integer, db.ForeignKey('permisos.id', ondelete="CASCADE"), primary_key=True)
)

class User(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_completo = db.Column(db.String(100), nullable=False)
    correo = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    roles = db.relationship('Role', secondary=user_roles, lazy='subquery',
                            backref=db.backref('usuarios', lazy=True))
    sesiones = db.relationship('SesionDiagnostico', backref='usuario', lazy=True)
    auditorias = db.relationship('LogAuditoria', backref='usuario', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre_completo": self.nombre_completo,
            "correo": self.correo,
            "rol_id": self.roles[0].id if self.roles else None,
            "rol_nombre": self.roles[0].nombre if self.roles else 'Sin Rol',
            "estado": "ACTIVO",
            "created_at": self.created_at.strftime('%Y-%m-%d %H:%M:%S') if self.created_at else None
        }

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))

    permissions = db.relationship('Permission', secondary=role_permissions, lazy='subquery',
                                  backref=db.backref('roles', lazy=True))

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion,
            "permisos": [p.nombre for p in self.permissions]
        }

class Permission(db.Model):
    __tablename__ = 'permisos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))

    def to_dict(self):
        return {
            "id": self.id,
            "nombre": self.nombre,
            "descripcion": self.descripcion
        }

# --- ENTIDADES DE HARDWARE, DIAGNÓSTICO Y TELEMETRÍA (FIAX ENGINE) ---

class Equipo(db.Model):
    __tablename__ = 'equipos'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_equipo = db.Column(db.String(100), nullable=False)
    os_version = db.Column(db.String(150), nullable=False)
    arquitectura = db.Column(db.String(50))
    ram_total_gb = db.Column(db.Float)
    procesador = db.Column(db.String(150))
    ip_local = db.Column(db.String(50), default="127.0.0.1")
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    ultima_conexion = db.Column(db.DateTime, default=datetime.utcnow)

    sesiones = db.relationship('SesionDiagnostico', backref='equipo', cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "nombre_equipo": self.nombre_equipo,
            "os_version": self.os_version,
            "arquitectura": self.arquitectura,
            "ram_total_gb": self.ram_total_gb,
            "procesador": self.procesador,
            "ip_local": self.ip_local,
            "ultima_conexion": self.ultima_conexion.strftime('%Y-%m-%d %H:%M:%S') if self.ultima_conexion else None
        }

class SesionDiagnostico(db.Model):
    __tablename__ = 'sesiones_diagnostico'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    equipo_id = db.Column(db.Integer, db.ForeignKey('equipos.id', ondelete="CASCADE"), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="SET NULL"), nullable=True)
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)
    estado = db.Column(db.String(50), default='COMPLETADO')
    score_salud = db.Column(db.Integer, default=100) # 0 a 100
    resumen = db.Column(db.String(255))

    metricas = db.relationship('MetricaRendimiento', backref='sesion', uselist=False, cascade="all, delete-orphan", lazy=True)
    incidencias = db.relationship('IncidenciaDetectada', backref='sesion', cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "equipo_id": self.equipo_id,
            "usuario_id": self.usuario_id,
            "fecha_hora": self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_hora else None,
            "estado": self.estado,
            "score_salud": self.score_salud,
            "resumen": self.resumen,
            "metricas": self.metricas.to_dict() if self.metricas else None,
            "incidencias_count": len(self.incidencias) if self.incidencias else 0
        }

class MetricaRendimiento(db.Model):
    __tablename__ = 'metricas_rendimiento'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    diagnostico_id = db.Column(db.Integer, db.ForeignKey('sesiones_diagnostico.id', ondelete="CASCADE"), nullable=False)
    uso_cpu_porcentaje = db.Column(db.Float, nullable=False)
    uso_ram_porcentaje = db.Column(db.Float, nullable=False)
    ram_usada_gb = db.Column(db.Float)
    ram_libre_gb = db.Column(db.Float)
    disco_libre_gb = db.Column(db.Float)
    disco_usado_porcentaje = db.Column(db.Float)
    procesos_activos = db.Column(db.Integer)

    def to_dict(self):
        return {
            "id": self.id,
            "diagnostico_id": self.diagnostico_id,
            "uso_cpu_porcentaje": round(self.uso_cpu_porcentaje, 1),
            "uso_ram_porcentaje": round(self.uso_ram_porcentaje, 1),
            "ram_usada_gb": round(self.ram_usada_gb, 2) if self.ram_usada_gb else None,
            "ram_libre_gb": round(self.ram_libre_gb, 2) if self.ram_libre_gb else None,
            "disco_libre_gb": round(self.disco_libre_gb, 2) if self.disco_libre_gb else None,
            "disco_usado_porcentaje": round(self.disco_usado_porcentaje, 1) if self.disco_usado_porcentaje else None,
            "procesos_activos": self.procesos_activos
        }

class IncidenciaDetectada(db.Model):
    __tablename__ = 'incidencias_detectadas'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    diagnostico_id = db.Column(db.Integer, db.ForeignKey('sesiones_diagnostico.id', ondelete="CASCADE"), nullable=False)
    tipo_incidencia = db.Column(db.String(60), nullable=False)
    componente_afectado = db.Column(db.String(100), nullable=False)
    descripcion = db.Column(db.Text, nullable=False)
    nivel_severidad = db.Column(db.String(20), default='MEDIO') # BAJO, MEDIO, ALTO, CRITICO
    estado = db.Column(db.String(20), default='PENDIENTE') # PENDIENTE, EN_PROCESO, RESUELTA
    fecha_deteccion = db.Column(db.DateTime, default=datetime.utcnow)

    acciones = db.relationship('AccionCorrectiva', backref='incidencia', cascade="all, delete-orphan", lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "diagnostico_id": self.diagnostico_id,
            "tipo_incidencia": self.tipo_incidencia,
            "componente_afectado": self.componente_afectado,
            "descripcion": self.descripcion,
            "nivel_severidad": self.nivel_severidad,
            "estado": self.estado,
            "fecha_deteccion": self.fecha_deteccion.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_deteccion else None,
            "acciones": [a.to_dict() for a in self.acciones] if self.acciones else []
        }

class AccionCorrectiva(db.Model):
    __tablename__ = 'acciones_correctivas'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    incidencia_id = db.Column(db.Integer, db.ForeignKey('incidencias_detectadas.id', ondelete="CASCADE"), nullable=False)
    solucion_recomendada = db.Column(db.Text, nullable=False)
    tipo_accion = db.Column(db.String(50), default="SISTEMA") # LIMPIEZA_TEMP, FLUSH_DNS, OPTIMIZAR_RAM, COMANDO_SFC, DRIVER
    autorizada_por_usuario = db.Column(db.Integer, default=0) # 0 o 1
    ejecutada_con_exito = db.Column(db.Integer, default=0) # 0 o 1
    fecha_ejecucion = db.Column(db.DateTime, nullable=True)
    resultado_log = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "incidencia_id": self.incidencia_id,
            "solucion_recomendada": self.solucion_recomendada,
            "tipo_accion": self.tipo_accion,
            "autorizada_por_usuario": bool(self.autorizada_por_usuario),
            "ejecutada_con_exito": bool(self.ejecutada_con_exito),
            "fecha_ejecucion": self.fecha_ejecucion.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_ejecucion else None,
            "resultado_log": self.resultado_log
        }

class LogAuditoria(db.Model):
    __tablename__ = 'auditoria_logs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuarios.id', ondelete="SET NULL"), nullable=True)
    modulo = db.Column(db.String(50), nullable=False) # AUTH, DIAGNOSTICO, MANTENIMIENTO, USUARIOS, SEGURIDAD
    accion = db.Column(db.String(100), nullable=False)
    detalles = db.Column(db.Text)
    ip_origen = db.Column(db.String(45))
    nivel = db.Column(db.String(20), default="INFO") # INFO, WARNING, ERROR, CRITICAL
    fecha_hora = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "usuario_id": self.usuario_id,
            "usuario_nombre": self.usuario.nombre_completo if self.usuario else "Sistema / Anónimo",
            "modulo": self.modulo,
            "accion": self.accion,
            "detalles": self.detalles,
            "ip_origen": self.ip_origen,
            "nivel": self.nivel,
            "fecha_hora": self.fecha_hora.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_hora else None
        }