from flask import Blueprint, request, jsonify, session
from services.role_service import RoleManagementService
from services.auth_service import AuthService
from services.audit_service import AuditService
from security.decorators import has_permission
from domain.enums import PermissionEnum, RoleEnum
from domain.models import db, User, Role

role_bp = Blueprint('role_bp', __name__, url_prefix='/api/v1')
role_service = RoleManagementService()

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
    data = request.json or {}
    nombre = data.get('nombre', '').strip()
    correo = data.get('correo', '').strip()
    password = data.get('password', '')
    role_id = data.get('role_id')

    if not nombre or not correo or not password:
        return jsonify({"error": "Todos los campos son obligatorios."}), 400

    if User.query.filter_by(correo=correo).first():
        return jsonify({"error": "El correo electrónico ya está registrado."}), 400

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

    data = request.json or {}
    user.nombre_completo = data.get('nombre', user.nombre_completo).strip()
    
    nuevo_correo = data.get('correo', user.correo).strip()
    if nuevo_correo and nuevo_correo != user.correo:
        existente = User.query.filter(User.correo == nuevo_correo, User.id != user_id).first()
        if existente:
            return jsonify({"error": "El correo electrónico ya está en uso por otro usuario."}), 400
        user.correo = nuevo_correo
    
    if data.get('password'):
        user.password_hash = AuthService.hash_password(data.get('password'))

    role_id = data.get('role_id')
    if role_id:
        rol = db.session.get(Role, role_id)
        if rol:
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
    es_admin = any(r.nombre == RoleEnum.ADMINISTRADOR.value for r in user.roles)
    if es_admin:
        admin_count = User.query.filter(User.roles.any(Role.nombre == RoleEnum.ADMINISTRADOR.value)).count()
        if admin_count <= 1:
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
def get_roles():
    roles = Role.query.all()
    return jsonify([r.to_dict() for r in roles])

@role_bp.route('/roles', methods=['POST'])
@has_permission(PermissionEnum.ROLE_ASSIGN)
def create_role():
    data = request.json or {}
    role = role_service.create_role(data.get('nombre'), data.get('descripcion', ''))
    return jsonify(role.to_dict()), 201

@role_bp.route('/users/<int:user_id>/roles', methods=['POST'])
@has_permission(PermissionEnum.ROLE_ASSIGN)
def assign_role(user_id):
    data = request.json or {}
    role_id = data.get('role_id')
    user = role_service.assign_role_to_user(user_id, role_id)
    return jsonify({"message": f"Rol asignado correctamente al usuario {user.nombre_completo}"}), 200

@role_bp.route('/roles/<int:role_id>/permissions', methods=['GET'])
def get_role_permissions(role_id):
    from persistence.permission_repository import PermissionRepository
    perm_repo = PermissionRepository()
    perms = perm_repo.find_by_role_id(role_id)
    return jsonify([{"id": p.id, "nombre": p.nombre} for p in perms]), 200