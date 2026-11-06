from flask import Blueprint, current_app, request, jsonify, session
from services.role_service import RoleManagementService
from services.auth_service import AuthService
from services.audit_service import AuditService
from security.decorators import has_permission, login_required
from domain.enums import PermissionEnum, RoleEnum
from domain.models import db, User, Role

role_bp = Blueprint('role_bp', __name__, url_prefix='/api/v1')
role_service = RoleManagementService()


def _json_body():
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


def _text(data, key, default=''):
    value = data.get(key, default)
    return value.strip() if isinstance(value, str) else default


def _password_error(password):
    min_len = current_app.config['PASSWORD_MIN_LENGTH']
    if not isinstance(password, str) or len(password) < min_len:
        return f"La contraseña debe tener al menos {min_len} caracteres."
    return None


def _is_only_admin(user):
    if not any(r.nombre == RoleEnum.ADMINISTRADOR.value for r in user.roles):
        return False
    return User.query.filter(User.roles.any(Role.nombre == RoleEnum.ADMINISTRADOR.value)).count() <= 1

# ---------------------------------------------------------
# CRUD DE USUARIOS CON RBAC Y AUDITORÍA
# ---------------------------------------------------------

# READ: Obtener lista completa de usuarios y roles
@role_bp.route('/users', methods=['GET'])
@has_permission(PermissionEnum.USER_READ)
def get_users():
    users = User.query.all()
    roles = Role.query.all()
    
    lista_usuarios = [u.to_dict() for u in users]
    lista_roles = [r.to_dict() for r in roles]
    return jsonify({"usuarios": lista_usuarios, "roles": lista_roles})

# CREATE: Crear un nuevo usuario administrativo
@role_bp.route('/users', methods=['POST'])
@has_permission(PermissionEnum.USER_CREATE)
def create_user():
    data = _json_body()
    nombre = _text(data, 'nombre')
    correo = _text(data, 'correo')
    password = data.get('password', '')
    role_id = data.get('role_id')

    if not nombre or not correo or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    password_error = _password_error(password)
    if password_error:
        return jsonify({"error": password_error}), 400

    if User.query.filter(db.func.lower(User.correo) == correo.lower()).first():
        return jsonify({"error": "El correo electrónico ya está registrado."}), 400

    if User.query.filter(db.func.lower(User.nombre_completo) == nombre.lower()).first():
        return jsonify({"error": "Ya existe un usuario con este nombre completo."}), 400

    pass_hash = AuthService.hash_password(password)
    nuevo_usuario = User(nombre_completo=nombre, correo=correo, password_hash=pass_hash)
    
    rol = None
    if role_id:
        rol = db.session.get(Role, role_id)
    if not rol:
        rol = Role.query.filter_by(nombre=RoleEnum.USUARIO.value).first()
    if rol:
        nuevo_usuario.roles.append(rol)
        
    db.session.add(nuevo_usuario)
    db.session.commit()

    AuditService.registrar(
        accion="CREAR_USUARIO",
        modulo="USUARIOS",
        detalles=f"Usuario creado administrativamente: {correo} con rol {rol.nombre if rol else 'N/A'}",
        nivel="INFO"
    )

    return jsonify({"message": "Usuario creado exitosamente.", "usuario": nuevo_usuario.to_dict()}), 201

# UPDATE: Modificar datos y rol de un usuario
@role_bp.route('/users/<int:user_id>', methods=['PUT'])
@has_permission(PermissionEnum.USER_CREATE)
def update_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado."}), 404

    data = _json_body()
    nuevo_nombre = _text(data, 'nombre', user.nombre_completo)
    if nuevo_nombre and nuevo_nombre.lower() != user.nombre_completo.lower():
        existente_nombre = User.query.filter(
            db.func.lower(User.nombre_completo) == nuevo_nombre.lower(),
            User.id != user_id
        ).first()
        if existente_nombre:
            return jsonify({"error": "El nombre completo ya está en uso por otro usuario."}), 400
        user.nombre_completo = nuevo_nombre
    
    nuevo_correo = _text(data, 'correo', user.correo)
    if nuevo_correo and nuevo_correo.lower() != user.correo.lower():
        existente = User.query.filter(
            db.func.lower(User.correo) == nuevo_correo.lower(),
            User.id != user_id
        ).first()
        if existente:
            return jsonify({"error": "El correo electrónico ya está en uso por otro usuario."}), 400
        user.correo = nuevo_correo
    
    if data.get('password'):
        password_error = _password_error(data.get('password'))
        if password_error:
            db.session.rollback()
            return jsonify({"error": password_error}), 400
        user.password_hash = AuthService.hash_password(data.get('password'))

    role_id = data.get('role_id')
    if role_id:
        rol = db.session.get(Role, role_id)
        if rol:
            if rol.nombre != RoleEnum.ADMINISTRADOR.value and _is_only_admin(user):
                db.session.rollback()
                return jsonify({"error": "No se puede quitar el rol al único Administrador del sistema."}), 400
            user.roles = [rol]

    db.session.commit()

    AuditService.registrar(
        accion="MODIFICAR_USUARIO",
        modulo="USUARIOS",
        detalles=f"Usuario modificado: ID #{user.id} ({user.correo})",
        nivel="INFO"
    )

    return jsonify({"message": "Usuario actualizado correctamente.", "usuario": user.to_dict()})

# DELETE: Eliminar un usuario
@role_bp.route('/users/<int:user_id>', methods=['DELETE'])
@has_permission(PermissionEnum.USER_CREATE)
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Usuario no encontrado."}), 404

    if user.id == session.get('user_id'):
        return jsonify({"error": "No puede eliminar su propia cuenta activa."}), 400

    # Proteger contra la eliminación del único Administrador
    if _is_only_admin(user):
        return jsonify({"error": "No se puede eliminar el único Administrador del sistema."}), 400

    correo_eliminado = user.correo
    db.session.delete(user)
    db.session.commit()

    AuditService.registrar(
        accion="ELIMINAR_USUARIO",
        modulo="USUARIOS",
        detalles=f"Usuario eliminado del sistema: {correo_eliminado}",
        nivel="WARNING"
    )

    return jsonify({"message": "Usuario eliminado exitosamente."})

# ---------------------------------------------------------
# GESTIÓN DE ROLES Y PERMISOS
# ---------------------------------------------------------

@role_bp.route('/roles', methods=['GET'])
@login_required
def get_roles():
    roles = Role.query.all()
    return jsonify([r.to_dict() for r in roles])

@role_bp.route('/roles', methods=['POST'])
@has_permission(PermissionEnum.ROLE_ASSIGN)
def create_role():
    data = _json_body()
    nombre = _text(data, 'nombre')
    if not nombre:
        return jsonify({"error": "El nombre del rol es obligatorio."}), 400
    role = role_service.create_role(nombre, _text(data, 'descripcion'))
    return jsonify(role.to_dict()), 201

@role_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@has_permission(PermissionEnum.ROLE_ASSIGN)
def assign_role(user_id):
    role_id = _json_body().get('role_id')
    user = role_service.assign_role_to_user(user_id, role_id)
    if not user or not db.session.get(Role, role_id):
        return jsonify({"error": "Usuario o rol no encontrado."}), 404
    return jsonify({"message": f"Rol asignado correctamente al usuario {user.nombre_completo}"}), 200

@role_bp.route('/roles/<int:role_id>/permissions', methods=['GET'])
@login_required
def get_role_permissions(role_id):
    from persistence.permission_repository import PermissionRepository
    perm_repo = PermissionRepository()
    perms = perm_repo.find_by_role_id(role_id)
    return jsonify([{"id": p.id, "nombre": p.nombre} for p in perms]), 200