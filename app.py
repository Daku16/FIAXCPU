import os
from urllib.parse import urlparse

from flask import Flask, render_template, redirect, url_for, session, request, jsonify
from config import config_by_name
from domain.models import db, User, Role, Permission, SesionDiagnostico
from domain.enums import RoleEnum, PermissionEnum
from runtime_paths import load_or_create_secret, resource_path, is_frozen, user_data_dir
from services.role_service import RoleManagementService
from services.auth_service import AuthService
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from controllers.auth_controller import auth_bp
from controllers.role_controller import role_bp
from controllers.fiax_controller import fiax_bp


def create_app(config_name='default', instance_path=None):
    if instance_path is None and is_frozen():
        instance_path = user_data_dir()

    app = Flask(
        __name__,
        template_folder=resource_path('templates'),
        static_folder=resource_path('static'),
        instance_path=instance_path,
    )
    app.config.from_object(config_by_name[config_name])
    os.makedirs(app.instance_path, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        app.config['SECRET_KEY'] = load_or_create_secret(app.instance_path)

    # Inicializar Extensiones
    db.init_app(app)

    # Registrar Blueprints Modulares
    app.register_blueprint(auth_bp)
    app.register_blueprint(role_bp)
    app.register_blueprint(fiax_bp)

    @app.before_request
    def reject_cross_site_writes():
        """La API local no debe poder invocarse desde otros sitios abiertos en el navegador."""
        if request.method not in ('POST', 'PUT', 'PATCH', 'DELETE'):
            return None
        origin = request.headers.get('Origin')
        cross_site = (
            urlparse(origin).netloc != request.host if origin
            else request.headers.get('Sec-Fetch-Site') == 'cross-site'
        )
        if cross_site:
            return jsonify({"error": "Origen de la solicitud no permitido."}), 403
        return None

    @app.before_request
    def refresh_session_identity():
        """Mantiene rol y existencia del usuario sincronizados con la base de datos."""
        user_id = session.get('user_id')
        if not user_id or request.endpoint == 'static':
            return
        user = db.session.get(User, user_id)
        if not user:
            session.clear()
            return
        session['user_name'] = user.nombre_completo
        session['user_role'] = user.roles[0].nombre if user.roles else RoleEnum.USUARIO.value

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('X-Frame-Options', 'DENY')
        return response

    # --- RUTAS DE NAVEGACIÓN Y VISTAS WEB ---

    @app.route('/healthz')
    def healthz():
        return jsonify({"app": "fiax-cpu", "version": app.config['APP_VERSION']})

    @app.route('/')
    def index():
        if 'user_id' in session:
            return redirect(url_for('dashboard'))
        first_run = User.query.first() is None
        return render_template(
            'login.html',
            first_run=first_run,
            active_tab='registro' if first_run else 'login'
        )

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
            'app_version': app.config['APP_VERSION'],
            'allow_shutdown': app.config.get('ALLOW_SHUTDOWN', False)
        }

    return app


app = create_app(os.environ.get('FIAX_ENV', 'dev'))


def setup_initial_data(target_app=None):
    """Siembra de datos inicial con esquema relacional completo y equipo anfitrión."""
    target_app = target_app or app
    with target_app.app_context():
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
        admin_role.permissions = Permission.query.all()

        tecnico_role.permissions = Permission.query.filter(Permission.nombre.in_([
            PermissionEnum.DIAGNOSTIC_RUN.value,
            PermissionEnum.FIX_EXECUTE.value,
            PermissionEnum.REPORT_READ.value,
            PermissionEnum.MAINTENANCE_RUN.value,
            PermissionEnum.AUDIT_READ.value,
            PermissionEnum.USER_READ.value
        ])).all()

        usuario_role.permissions = Permission.query.filter(Permission.nombre.in_([
            PermissionEnum.DIAGNOSTIC_RUN.value,
            PermissionEnum.REPORT_READ.value,
            PermissionEnum.MAINTENANCE_RUN.value
        ])).all()

        db.session.commit()

        # 3. Cuentas de demostración (nunca en la versión instalable)
        if target_app.config.get('SEED_DEMO_USERS'):
            demo_users = (
                ("admin@fiax.com", "Erick Garcia", "admin123", admin_role),
                ("tecnico@fiax.com", "Carlos Mendoza (Técnico)", "tecnico123", tecnico_role),
            )
            for correo, nombre, password, role in demo_users:
                if not User.query.filter_by(correo=correo).first():
                    user = User(nombre_completo=nombre, correo=correo, password_hash=AuthService.hash_password(password))
                    user.roles.append(role)
                    db.session.add(user)
                    db.session.commit()
                    print(f"[INFO] Usuario de demostración {correo} creado.")

        # 4. Registro automático del equipo físico actual y diagnóstico inicial
        equipo = TelemetryService.get_or_register_host_equipo()
        print(f"[INFO] Equipo local registrado: {equipo.nombre_equipo} ({equipo.procesador})")

        # Si no hay diagnósticos previos, ejecutar el primer análisis base
        if not SesionDiagnostico.query.first():
            admin_user = User.query.filter(User.roles.any(Role.nombre == RoleEnum.ADMINISTRADOR.value)).first()
            DiagnosticService.execute_complete_diagnosis(user_id=admin_user.id if admin_user else None)
            print("[INFO] Diagnóstico base inicial generado y persistido.")


if __name__ == '__main__':
    setup_initial_data()
    print("=" * 60)
    print("FIAX CPU WEB - Sistema Inteligente de Mantenimiento (10mo Semestre)")
    print("Servidor activo en: http://127.0.0.1:5000")
    if app.config.get('SEED_DEMO_USERS'):
        print("Credenciales: admin@fiax.com / admin123 | tecnico@fiax.com / tecnico123")
    print("=" * 60)
    # El depurador de Werkzeug permite ejecutar código: se activa solo con FLASK_DEBUG=1.
    app.run(host='127.0.0.1', port=5000, debug=app.config['DEBUG'])
