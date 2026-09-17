import os

class Config:
    """Configuración base del sistema FIAX CPU Web"""
    SECRET_KEY = os.environ.get('SECRET_KEY', 'fiax_cpu_secret_key_2026_systems_eng')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fiax_cpu_web.db')
    
    # Umbrales Heurísticos de Hardware para FIAX Diagnostic Engine
    THRESHOLD_CPU_WARNING = 70.0   # Porcentaje
    THRESHOLD_CPU_CRITICAL = 85.0  # Porcentaje
    THRESHOLD_RAM_WARNING = 75.0   # Porcentaje
    THRESHOLD_RAM_CRITICAL = 88.0  # Porcentaje
    THRESHOLD_DISK_FREE_GB_CRITICAL = 10.0 # GB libres mínimos recomendados
    THRESHOLD_DISK_FREE_GB_WARNING = 25.0  # GB

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

config_by_name = {
    'dev': DevelopmentConfig,
    'prod': ProductionConfig,
    'default': DevelopmentConfig
}
