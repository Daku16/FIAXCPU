import os


class Config:
    """Configuración base del sistema FIAX CPU Web"""
    # Sin valor en el entorno, create_app genera y conserva una clave por instalación.
    SECRET_KEY = os.environ.get('SECRET_KEY')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fiax_cpu_web.db')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'

    # Versión de la Aplicación
    APP_VERSION = '1.2.0'

    # Cuentas de demostración conocidas: solo para desarrollo y sustentación.
    SEED_DEMO_USERS = False
    # El botón "Cerrar aplicación" solo existe en la versión de escritorio.
    ALLOW_SHUTDOWN = False

    # Antigüedad mínima para que un temporal se pueda borrar (evita tocar archivos en uso).
    TEMP_MIN_AGE_HOURS = float(os.environ.get('FIAX_TEMP_MIN_AGE_HOURS', '1'))

    PASSWORD_MIN_LENGTH = 8

    # Umbrales Heurísticos de Hardware para FIAX Diagnostic Engine
    THRESHOLD_CPU_WARNING = 70.0   # Porcentaje
    THRESHOLD_CPU_CRITICAL = 85.0  # Porcentaje
    THRESHOLD_RAM_WARNING = 75.0   # Porcentaje
    THRESHOLD_RAM_CRITICAL = 88.0  # Porcentaje
    THRESHOLD_DISK_FREE_GB_CRITICAL = 10.0 # GB libres mínimos recomendados
    THRESHOLD_DISK_FREE_GB_WARNING = 25.0  # GB


class DevelopmentConfig(Config):
    DEBUG = bool(os.environ.get('FLASK_DEBUG'))
    SEED_DEMO_USERS = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = 'solo-para-pruebas'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SEED_DEMO_USERS = True
    PASSWORD_MIN_LENGTH = 8


config_by_name = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
