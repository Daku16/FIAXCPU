from domain.models import db, Role, User

class RoleRepository:
    def find_by_id(self, role_id):
        return Role.query.get(role_id)

    def find_by_name(self, name):
        return Role.query.filter_by(nombre=name).first()

    def find_by_user_id(self, user_id):
        user = User.query.get(user_id)
        return user.roles if user else []

    def save_role(self, role):
        db.session.add(role)
        db.session.commit()
        return role