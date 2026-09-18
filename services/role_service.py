from domain.models import db, Role, User, Permission
from persistence.role_repository import RoleRepository
from persistence.permission_repository import PermissionRepository
from services.auth_service import AuthorizationService

class RoleManagementService:
    def __init__(self):
        self.role_repo = RoleRepository()
        self.perm_repo = PermissionRepository()

    def create_role(self, nombre, descripcion=""):
        existing = self.role_repo.find_by_name(nombre)
        if existing:
            return existing
        new_role = Role(nombre=nombre, descripcion=descripcion)
        return self.role_repo.save_role(new_role)

    def assign_permission_to_role(self, role_id, permission_name):
        role = self.role_repo.find_by_id(role_id)
        permission = self.perm_repo.find_by_name(permission_name)
        if role and permission and permission not in role.permissions:
            role.permissions.append(permission)
            db.session.commit()
        return role

    def assign_role_to_user(self, user_id, role_id):
        user = db.session.get(User, user_id)
        role = self.role_repo.find_by_id(role_id)
        if user and role and role not in user.roles:
            user.roles.append(role)
            db.session.commit()
        return user