import os
import sys
import unittest

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import create_app, setup_initial_data
from domain.models import db, User, Role, Permission, SesionDiagnostico, IncidenciaDetectada, Equipo
from domain.enums import RoleEnum, PermissionEnum, SeveridadEnum
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.maintenance_service import MaintenanceService
from services.audit_service import AuditService
from services.auth_service import AuthService

class FIAXSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('dev')
        cls.app.config['TESTING'] = True
        cls.app.config['WTF_CSRF_ENABLED'] = False
        with cls.app.app_context():
            db.create_all()
            setup_initial_data()

    def setUp(self):
        self.client = self.app.test_client()

    def login_admin(self):
        return self.client.post('/login', data={'correo': 'admin@fiax.com', 'password': 'admin123'})

    def login_tecnico(self):
        return self.client.post('/login', data={'correo': 'tecnico@fiax.com', 'password': 'tecnico123'})

    # 1. Autenticación y Sesiones
    def test_01_login_success(self):
        res = self.login_admin()
        self.assertEqual(res.status_code, 302)
        self.assertIn('/dashboard', res.headers.get('Location', ''))

    def test_02_login_invalid_password(self):
        res = self.client.post('/login', data={'correo': 'admin@fiax.com', 'password': 'wrongpassword'})
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Credenciales", res.data)

    def test_03_registration_and_logout(self):
        import uuid
        uid = uuid.uuid4().hex[:6]
        unique_email = f"test_reg_{uid}@fiax.com"
        unique_name = f"Usuario Test {uid}"

        # Registro fallido: contraseñas distintas
        res = self.client.post('/registro', data={
            'nombre': unique_name,
            'correo': unique_email,
            'password': 'pass1',
            'confirm_password': 'pass2'
        })
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"coinciden", res.data)

        # Registro exitoso
        res = self.client.post('/registro', data={
            'nombre': unique_name,
            'correo': unique_email,
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(res.status_code, 302)

        # Registro fallido: Correo duplicado
        res_dup_mail = self.client.post('/registro', data={
            'nombre': f"Otro Nombre {uuid.uuid4().hex[:4]}",
            'correo': unique_email,
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(res_dup_mail.status_code, 200)
        self.assertIn(b"correo", res_dup_mail.data)

        # Registro fallido: Nombre duplicado
        res_dup_name = self.client.post('/registro', data={
            'nombre': unique_name,
            'correo': f"otro_mail_{uuid.uuid4().hex[:6]}@fiax.com",
            'password': 'password123',
            'confirm_password': 'password123'
        })
        self.assertEqual(res_dup_name.status_code, 200)
        self.assertIn(b"nombre", res_dup_name.data)

        # Logout
        res = self.client.get('/logout')
        self.assertEqual(res.status_code, 302)

    # 2. Telemetría de Hardware
    def test_04_hardware_telemetry(self):
        profile = TelemetryService.get_hardware_profile()
        self.assertIn('nombre_equipo', profile)
        self.assertIn('os_version', profile)
        self.assertIn('ram_total_gb', profile)
        self.assertGreater(profile['ram_total_gb'], 0)

        metrics = TelemetryService.get_live_metrics()
        self.assertIn('cpu', metrics)
        self.assertIn('ram', metrics)
        self.assertIn('disk', metrics)
        self.assertIn('procesos_activos', metrics)
        self.assertGreaterEqual(metrics['cpu']['usage_percent'], 0)

    # 3. Motor Heurístico y Health Score
    def test_05_health_score_calculation(self):
        # Escenario 1: Sistema en reposo óptimo
        score_optimo = DiagnosticService.calculate_health_score(
            cpu_pct=20.0, ram_pct=40.0, disk_free_gb=100.0, temp_mb=50.0, incidents=[]
        )
        self.assertEqual(score_optimo, 100)

        # Escenario 2: Sistema estresado al límite
        incidents_criticos = [
            {'severidad': SeveridadEnum.CRITICO.value},
            {'severidad': SeveridadEnum.ALTO.value}
        ]
        score_critico = DiagnosticService.calculate_health_score(
            cpu_pct=95.0, ram_pct=92.0, disk_free_gb=8.0, temp_mb=1500.0, incidents=incidents_criticos
        )
        self.assertLessEqual(score_critico, 40)
        self.assertGreaterEqual(score_critico, 15)

    def test_06_complete_diagnosis_execution(self):
        with self.app.app_context():
            resultado = DiagnosticService.execute_complete_diagnosis()
            self.assertTrue(resultado['success'])
            self.assertIn('sesion_id', resultado)
            self.assertIn('score_salud', resultado)
            self.assertGreaterEqual(len(resultado['incidencias']), 1)

    # 4. Servicios de Mantenimiento y Remediación
    def test_07_maintenance_routines(self):
        res_temp = MaintenanceService.clean_temporary_files()
        self.assertTrue(res_temp['success'])

        res_dns = MaintenanceService.flush_dns_cache()
        self.assertTrue(res_dns['success'])

        res_mem = MaintenanceService.optimize_memory()
        self.assertTrue(res_mem['success'])

        # Probar endpoint API con mantenimiento selectivo
        self.login_admin()
        res_api_dns = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'dns'})
        self.assertEqual(res_api_dns.status_code, 200)
        self.assertEqual(res_api_dns.get_json()['tipo'], 'dns')

        res_api_temp = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'temporales'})
        self.assertEqual(res_api_temp.status_code, 200)
        self.assertEqual(res_api_temp.get_json()['tipo'], 'temporales')

        res_api_mem = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'memoria'})
        self.assertEqual(res_api_mem.status_code, 200)
        self.assertEqual(res_api_mem.get_json()['tipo'], 'memoria')

    def test_08_resolve_incident(self):
        with self.app.app_context():
            # Buscar una incidencia pendiente
            incidencia = IncidenciaDetectada.query.filter_by(estado='PENDIENTE').first()
            if incidencia:
                res = MaintenanceService.resolve_incident(incidencia.id)
                self.assertTrue(res['success'])
                self.assertEqual(res['incidencia']['estado'], 'RESUELTA')

    # 5. Auditoría
    def test_09_audit_logging(self):
        # Registro fuera de contexto de solicitud
        with self.app.app_context():
            log = AuditService.registrar(
                accion="TEST_CLI",
                modulo="SISTEMA",
                detalles="Prueba de auditoría sin request_context"
            )
            self.assertIsNotNone(log)

        # Registro dentro de sesión
        self.login_admin()
        res = self.client.get('/api/v1/fiax/auditoria')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertGreater(len(data['logs']), 0)

    # 6. RBAC y CRUD de Usuarios
    def test_10_rbac_access_control(self):
        # Petición anónima a /api/v1/users debe ser rechazada (401)
        self.client.get('/logout')
        res = self.client.get('/api/v1/users')
        self.assertEqual(res.status_code, 401)

        # Acceso con credenciales de admin
        self.login_admin()
        res = self.client.get('/api/v1/users')
        self.assertEqual(res.status_code, 200)

    def test_11_user_crud_and_protections(self):
        import uuid
        self.login_admin()
        uid = uuid.uuid4().hex[:6]
        unique_email = f"rbac_{uid}@fiax.com"
        unique_name = f"Validador RBAC {uid}"

        # Crear usuario
        res = self.client.post('/api/v1/users', json={
            'nombre': unique_name,
            'correo': unique_email,
            'password': 'temporal_pass_123',
            'role_id': 3
        })
        self.assertEqual(res.status_code, 201)
        user_id = res.get_json()['usuario']['id']

        # Intentar crear con el mismo correo (debe rechazar con 400)
        res_dup_mail = self.client.post('/api/v1/users', json={
            'nombre': f"Otro Nombre {uuid.uuid4().hex[:4]}",
            'correo': unique_email,
            'password': 'password123',
            'role_id': 3
        })
        self.assertEqual(res_dup_mail.status_code, 400)

        # Intentar crear con el mismo nombre (debe rechazar con 400)
        res_dup_name = self.client.post('/api/v1/users', json={
            'nombre': unique_name,
            'correo': f"otro_mail_{uuid.uuid4().hex[:6]}@fiax.com",
            'password': 'password123',
            'role_id': 3
        })
        self.assertEqual(res_dup_name.status_code, 400)

        # Modificar usuario
        mod_name = f"Validador Modificado {uid}"
        res = self.client.put(f'/api/v1/users/{user_id}', json={
            'nombre': mod_name,
            'correo': unique_email,
            'role_id': 2
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()['usuario']['nombre_completo'], mod_name)

        # Intentar modificar correo a uno existente (debe rechazar con 400)
        res = self.client.put(f'/api/v1/users/{user_id}', json={
            'correo': 'admin@fiax.com'
        })
        self.assertEqual(res.status_code, 400)

        # Intentar modificar nombre a uno existente (debe rechazar con 400)
        res_name_col = self.client.put(f'/api/v1/users/{user_id}', json={
            'nombre': 'Erick Garcia'
        })
        self.assertEqual(res_name_col.status_code, 400)

        # Eliminar usuario creado
        res = self.client.delete(f'/api/v1/users/{user_id}')
        self.assertEqual(res.status_code, 200)

    # 7. Vistas Web y Versión
    def test_12_template_rendering(self):
        # Login page renderiza versión
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"1.1.0", res.data)

        # Dashboard sin login redirige
        self.client.get('/logout')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)

        # Dashboard con login renderiza exitosamente y muestra versión
        self.login_admin()
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Score de Salud FIAX", res.data)
        self.assertIn(b"1.1.0", res.data)

        # Gestion de usuarios renderiza exitosamente y muestra versión
        res = self.client.get('/usuarios')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Control de Acceso y", res.data)
        self.assertIn(b"1.1.0", res.data)

if __name__ == '__main__':
    unittest.main()
