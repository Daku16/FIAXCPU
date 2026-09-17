from domain.models import Permission

class PermissionRepository:
    def find_by_name(self, name):
        return Permission.query.filter_by(nombre=name).first()

    def find_by_role_id(self, role_id):
        from domain.models import Role
        role = Role.query.get(role_id)
        return role.permissions if role else []