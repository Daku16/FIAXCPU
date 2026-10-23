import hashlib
from werkzeug.security import generate_password_hash, check_password_hash
from domain.models import db, User, Role
from domain.enums import RoleEnum

class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        """Genera hash seguro con PBKDF2/SHA256 y salt aleatorio."""
        return generate_password_hash(password, method='pbkdf2:sha256')

    @staticmethod
    def verify_password(stored_hash: str, password: str) -> bool:
        """Verifica la contraseña soportando hashes modernos y legacy sha256."""
        if not stored_hash or not password:
            return False
        # Compatibilidad con hash legacy SHA-256 plano
        if len(stored_hash) == 64 and all(c in '0123456789abcdefABCDEF' for c in stored_hash):
            if hashlib.sha256(password.encode()).hexdigest().lower() == stored_hash.lower():
                return True
        # Hash seguro werkzeug
        try:
            return check_password_hash(stored_hash, password)
        except Exception:
            return False

    @staticmethod
    def authenticate(correo: str, password: str):
        """Autentica a un usuario por correo (case-insensitive) y contraseña."""
        clean_correo = (correo or '').strip()
        user = User.query.filter(db.func.lower(User.correo) == clean_correo.lower()).first()
        if user and AuthService.verify_password(user.password_hash, password):
            return user
        return None

    @staticmethod
    def register(nombre: str, correo: str, password: str, role_name: str = RoleEnum.USUARIO.value):
        """Registra un nuevo usuario en la base de datos validando nombre y correo únicos."""
        nombre_clean = (nombre or '').strip()
        correo_clean = (correo or '').strip()

        # Validación 1: Correo electrónico duplicado
        if User.query.filter(db.func.lower(User.correo) == correo_clean.lower()).first():
            return None, "El correo electrónico ya se encuentra registrado."

        # Validación 2: Nombre de usuario duplicado
        if User.query.filter(db.func.lower(User.nombre_completo) == nombre_clean.lower()).first():
            return None, "El nombre de usuario ya se encuentra registrado."

        hashed_pw = AuthService.hash_password(password)
        new_user = User(nombre_completo=nombre_clean, correo=correo_clean, password_hash=hashed_pw)
        
        role = Role.query.filter_by(nombre=role_name).first()
        if role:
            new_user.roles.append(role)

        db.session.add(new_user)
        db.session.commit()
        return new_user, None

class AuthorizationService:
    @staticmethod
    def user_has_permission(user_id: int, required_permission) -> bool:
        """Verifica si el usuario posee un permiso a través de sus roles asignados."""
        user = db.session.get(User, user_id)
        if not user:
            return False
            
        req_perm_str = required_permission.value if hasattr(required_permission, 'value') else str(required_permission)

        # Recorre los roles del usuario y sus permisos asociados
        for role in user.roles:
            # Los administradores tienen acceso irrestricto
            if role.nombre == RoleEnum.ADMINISTRADOR.value:
                return True
            for perm in role.permissions:
                if perm.nombre == req_perm_str:
                    return True
        return False

    @staticmethod
    def get_user_role_name(user_id: int) -> str:
        """Obtiene el nombre del rol principal del usuario."""
        user = db.session.get(User, user_id)
        if user and user.roles:
            return user.roles[0].nombre
        return RoleEnum.USUARIO.value