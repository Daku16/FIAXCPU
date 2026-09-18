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
            
            req_perm_str = required_permission.value if hasattr(required_permission, 'value') else str(required_permission)
            if not AuthorizationService.user_has_permission(user_id, req_perm_str):
                return jsonify({"error": f"Acceso denegado. Requiere el permiso: {req_perm_str}"}), 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({"error": "No autorizado. Inicie sesión."}), 401
        return f(*args, **kwargs)
    return decorated_function