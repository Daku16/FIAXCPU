from functools import wraps
from flask import session, jsonify, request
from services.auth_service import AuthorizationService

def has_permission(required_permission):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user_id = session.get('user_id')
            if not user_id:
                return jsonify({"error": "No autorizado. Inicie sesión."}), 401
            
            if not AuthorizationService.user_has_permission(user_id, required_permission):
                return jsonify({"error": f"Acceso denegado. Requiere el permiso: {required_permission}"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator