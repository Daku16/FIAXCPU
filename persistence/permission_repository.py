from domain.models import db, Permission, Role

class PermissionRepository:
    def find_by_name(self, name):
        return Permission.query.filter_by(nombre=name).first()

    def find_by_role_id(self, role_id):
        role = db.session.get(Role, role_id)
        return role.permissions if role else []