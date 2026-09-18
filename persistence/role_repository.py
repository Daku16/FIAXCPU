from domain.models import db, Role, User

class RoleRepository:
    def find_by_id(self, role_id):
        return db.session.get(Role, role_id)

    def find_by_name(self, name):
        return Role.query.filter_by(nombre=name).first()

    def find_by_user_id(self, user_id):
        user = db.session.get(User, user_id)
        return user.roles if user else []

    def save_role(self, role):
        db.session.add(role)
        db.session.commit()
        return role