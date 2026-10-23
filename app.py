from flask import Flask, render_template, redirect, url_for, session, request
from config import config_by_name
from domain.models import db, User, Role, Permission, Equipo, SesionDiagnostico
from domain.enums import RoleEnum, PermissionEnum
from services.role_service import RoleManagementService
from services.auth_service import AuthService
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.audit_service import AuditService
from controllers.auth_controller import auth_bp
from controllers.role_controller import role_bp
from controllers.fiax_controller import fiax_bp

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Inicializar Extensiones
    db.init_app(app)

    # Registrar Blueprints Modulares
    app.register_blueprint(auth_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(fiax_bp)

    # --- RUTAS DE NAVEGACIÓN Y VISTAS WEB ---

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        return render_template('login.html')

    @app.route('/dashboard')
    def dashboard():
        if 'user_id' not in session:
            return redirect(url_for('index'))

        user_role = session.get('user_role', RoleEnum.USUARIO.value)
        user_name = session.get('user_name', 'Usuario')
        
        # Obtener ficha del equipo anfitrión y último diagnóstico registrado
        equipo = TelemetryService.get_or_register_host_equipo()
        ultimo_diag = DiagnosticService.get_latest_diagnostic_summary()

        return render_template(
            'dashboard.html',
            user_name=user_name,
            user_role=user_role,
            user_id=session.get('user_id'),
            equipo=equipo.to_dict() if equipo else {},
            ultimo_diag=ultimo_diag
        )

    @app.route('/usuarios')
    def gestion_usuarios():
        if 'user_id' not in session:
            return redirect(url_for('index'))
        
        user_role = session.get('user_role', RoleEnum.USUARIO.value)
        if user_role != RoleEnum.ADMINISTRADOR.value:
            return redirect(url_for('dashboard'))

        return render_template(
            'usuarios.html',
            user_name=session.get('user_name'),
            user_role=user_role
        )

    @app.context_processor
    def inject_app_globals():
        return {
            'app_version': app.config.get('APP_VERSION', '1.1.0')
        }

    return app

app = create_app('dev')

def setup_initial_data():
    """Siembra de datos inicial con esquema relacional completo y equipo anfitrión."""
    with app.app_context():
        db.create_all()
        role_service = RoleManagementService()

        # 1. Crear Permisos del Sistema
        for p_enum in PermissionEnum:
            if not Permission.query.filter_by(nombre=p_enum.value).first():
                db.session.add(Permission(nombre=p_enum.value, descripcion=f"Permiso para {p_enum.value.lower()}"))
        db.session.commit()

        # 2. Crear Roles por Defecto
        admin_role = role_service.create_role(RoleEnum.ADMINISTRADOR.value, "Administrador con control total del sistema")
        tecnico_role = role_service.create_role(RoleEnum.TECNICO.value, "Técnico especialista en diagnóstico y optimización")
        usuario_role = role_service.create_role(RoleEnum.USUARIO.value, "Usuario estándar con acceso a salud de su equipo")

        # Asignar permisos a roles
        todos_permisos = Permission.query.all()
        admin_role.permissions = todos_permisos

        perms_tecnico = Permission.query.filter(Permission.nombre.in_([
            PermissionEnum.DIAGNOSTIC_RUN.value,
            PermissionEnum.FIX_EXECUTE.value,
            PermissionEnum.REPORT_READ.value,
            PermissionEnum.MAINTENANCE_RUN.value,
            PermissionEnum.AUDIT_READ.value,
            PermissionEnum.USER_READ.value
        ])).all()
        tecnico_role.permissions = perms_tecnico

        perms_usuario = Permission.query.filter(Permission.nombre.in_([
            PermissionEnum.DIAGNOSTIC_RUN.value,
            PermissionEnum.REPORT_READ.value,
            PermissionEnum.MAINTENANCE_RUN.value
        ])).all()
        usuario_role.permissions = perms_usuario

        db.session.commit()

        # 3. Usuario Administrador por Defecto
        if not User.query.filter_by(correo="admin@fiax.com").first():
            pass_hash = AuthService.hash_password("admin123")
            admin_user = User(nombre_completo="Erick Garcia", correo="admin@fiax.com", password_hash=pass_hash)
            admin_user.roles.append(admin_role)
            db.session.add(admin_user)
            db.session.commit()
            print("[INFO] Usuario Administrador admin@fiax.com creado.")

        # 4. Usuario Técnico de Demostración
        if not User.query.filter_by(correo="tecnico@fiax.com").first():
            pass_hash_tec = AuthService.hash_password("tecnico123")
            tec_user = User(nombre_completo="Carlos Mendoza (Técnico)", correo="tecnico@fiax.com", password_hash=pass_hash_tec)
            tec_user.roles.append(tecnico_role)
            db.session.add(tec_user)
            db.session.commit()
            print("[INFO] Usuario Técnico tecnico@fiax.com creado.")

        # 5. Registro automático del equipo físico actual y diagnóstico inicial
        equipo = TelemetryService.get_or_register_host_equipo()
        print(f"[INFO] Equipo local registrado: {equipo.nombre_equipo} ({equipo.procesador})")

        # Si no hay diagnósticos previos, ejecutar el primer análisis base
        if not SesionDiagnostico.query.first():
            admin_user = User.query.filter_by(correo="admin@fiax.com").first()
            user_id = admin_user.id if admin_user else None
            DiagnosticService.execute_complete_diagnosis(user_id=user_id)
            print("[INFO] Diagnóstico base inicial generado y persistido.")

if __name__ == '__main__':
    setup_initial_data()
    print("=" * 60)
    print("FIAX CPU WEB - Sistema Inteligente de Mantenimiento (10mo Semestre)")
    print("Servidor activo en: http://127.0.0.1:5000")
    print("Credenciales: admin@fiax.com / admin123 | tecnico@fiax.com / tecnico123")
    print("=" * 60)
    app.run(debug=True, port=5000)