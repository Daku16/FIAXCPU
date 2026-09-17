from flask import Blueprint, request, redirect, url_for, session, render_template, jsonify
from services.auth_service import AuthService
from services.audit_service import AuditService
from domain.enums import RoleEnum

auth_bp = Blueprint('auth_bp', __name__)

@auth_bp.route('/login', methods=['POST'])
def login():
    correo = request.form.get('correo', '').strip()
    password = request.form.get('password', '')

    user = AuthService.authenticate(correo, password)
    if user:
        session['user_id'] = user.id
        session['user_name'] = user.nombre_completo
        session['user_role'] = user.roles[0].nombre if user.roles else RoleEnum.USUARIO.value
        
        AuditService.registrar(
            accion="INICIO_SESION",
            modulo="AUTH",
            detalles=f"Usuario {user.correo} inició sesión exitosamente.",
            nivel="INFO",
            usuario_id=user.id
        )
        return redirect(url_for('dashboard'))

    AuditService.registrar(
        accion="INTENTO_FALLIDO_LOGIN",
        modulo="AUTH",
        detalles=f"Intento fallido de inicio de sesión para el correo: {correo}",
        nivel="WARNING"
    )
    return render_template('login.html', error_login="Credenciales inválidas. Verifique su correo y contraseña.")

@auth_bp.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'GET':
        return redirect(url_for('index'))

    nombre = request.form.get('nombre', '').strip()
    correo = request.form.get('correo', '').strip()
    password = request.form.get('password', '')
    confirm_pass = request.form.get('confirm_password', '')

    if not nombre or not correo or not password:
        return render_template('login.html', error_login="Todos los campos son obligatorios.")

    if password != confirm_pass:
        return render_template('login.html', error_login="Las contraseñas no coinciden.")

    nuevo_usuario, error = AuthService.register(nombre, correo, password, RoleEnum.USUARIO.value)
    if error:
        return render_template('login.html', error_login=error)

    session['user_id'] = nuevo_usuario.id
    session['user_name'] = nuevo_usuario.nombre_completo
    session['user_role'] = RoleEnum.USUARIO.value

    AuditService.registrar(
        accion="REGISTRO_USUARIO",
        modulo="AUTH",
        detalles=f"Nuevo usuario registrado públicamente: {correo}",
        nivel="INFO",
        usuario_id=nuevo_usuario.id
    )

    return redirect(url_for('dashboard'))

@auth_bp.route('/logout')
def logout():
    user_id = session.get('user_id')
    user_name = session.get('user_name')
    if user_id:
        AuditService.registrar(
            accion="CIERRE_SESION",
            modulo="AUTH",
            detalles=f"Usuario {user_name} cerró sesión.",
            nivel="INFO",
            usuario_id=user_id
        )
    session.clear()
    return redirect(url_for('index'))

