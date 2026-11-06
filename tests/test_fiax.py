import os
import sys
import tempfile
import time
import unittest
from unittest import mock

# Asegurar que el directorio raíz del proyecto esté en sys.path
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Las pruebas nunca deben borrar los temporales reales del equipo.
_TEMP_SANDBOX = tempfile.mkdtemp(prefix="fiax-tests-")
tempfile.tempdir = _TEMP_SANDBOX

from app import create_app, setup_initial_data
from config import Config
from domain.models import db, User, Role, Permission, SesionDiagnostico, IncidenciaDetectada, Equipo, AccionCorrectiva
from domain.enums import RoleEnum, PermissionEnum, SeveridadEnum
from services.telemetry_service import TelemetryService
from services.diagnostic_service import DiagnosticService
from services.maintenance_service import MaintenanceService
from services.audit_service import AuditService
from services.auth_service import AuthService

class FIAXSystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app('testing', instance_path=tempfile.mkdtemp(prefix="fiax-instance-"))
        setup_initial_data(cls.app)

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
            self.assertIn('score_previo', resultado)

    def test_06b_new_diagnosis_replaces_old_pending_incidents(self):
        with self.app.app_context():
            vieja = self._pending_incident('CACHE_SOBREDIMENSIONADO', 'LIMPIEZA_TEMP')
            DiagnosticService.execute_complete_diagnosis()
            self.assertEqual(db.session.get(IncidenciaDetectada, vieja).estado, 'REEMPLAZADA')

    def test_06c_metric_failure_never_stores_invented_data(self):
        with self.app.app_context():
            antes = SesionDiagnostico.query.count()
            with mock.patch('psutil.virtual_memory', side_effect=OSError('sin acceso')):
                resultado = DiagnosticService.execute_complete_diagnosis()
            self.assertFalse(resultado['success'])
            self.assertEqual(SesionDiagnostico.query.count(), antes)

    def test_06d_dns_cache_parser(self):
        salida = "    a.com\n    ----------------------------------------\n    Nombre : a\n\n    b.com\n    ------\n"
        self.assertEqual(DiagnosticService.parse_windows_dns_cache(salida), 2)

    # 4. Servicios de Mantenimiento y Remediación
    def _pending_incident(self, tipo, tipo_accion):
        """Crea una incidencia pendiente en la última sesión de diagnóstico."""
        sesion = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
        inc = IncidenciaDetectada(diagnostico_id=sesion.id, tipo_incidencia=tipo, componente_afectado='Prueba',
                                  descripcion='Prueba', nivel_severidad='MEDIO', estado='PENDIENTE')
        db.session.add(inc)
        db.session.flush()
        db.session.add(AccionCorrectiva(incidencia_id=inc.id, solucion_recomendada='Prueba', tipo_accion=tipo_accion))
        db.session.commit()
        return inc.id

    def _temp_file(self, nombre, tamano=2048, antiguedad_horas=0.0, carpeta=None):
        directorio = os.path.join(_TEMP_SANDBOX, carpeta) if carpeta else _TEMP_SANDBOX
        os.makedirs(directorio, exist_ok=True)
        ruta = os.path.join(directorio, nombre)
        with open(ruta, 'wb') as handle:
            handle.write(b'x' * tamano)
        marca = time.time() - antiguedad_horas * 3600
        os.utime(ruta, (marca, marca))
        return ruta

    def test_07_temp_cleanup_only_removes_old_unprotected_files(self):
        viejo = self._temp_file('viejo.tmp', antiguedad_horas=5)
        anidado = self._temp_file('anidado.tmp', antiguedad_horas=5, carpeta='sub')
        reciente = self._temp_file('reciente.tmp')
        protegido = self._temp_file('dll.bin', antiguedad_horas=5, carpeta='_MEI12345')

        res = MaintenanceService.clean_temporary_files()

        self.assertTrue(res['success'])
        self.assertFalse(os.path.exists(viejo))
        self.assertFalse(os.path.exists(anidado))
        self.assertTrue(os.path.exists(reciente))
        self.assertTrue(os.path.exists(protegido))

    def test_07b_dns_reports_failure_when_unsupported(self):
        with mock.patch('shutil.which', return_value=None):
            self.assertFalse(MaintenanceService.flush_dns_cache()['success'])

    def test_07c_procedure_returns_before_and_after(self):
        self._temp_file('comparar.tmp', tamano=3 * 1024 * 1024, antiguedad_horas=5)
        self.login_admin()
        res = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'temporales'})
        self.assertEqual(res.status_code, 200)
        comparacion = res.get_json()['comparacion']
        temp = next(f for f in comparacion['filas'] if f['clave'] == 'temp_mb')
        self.assertLess(temp['final'], temp['inicial'])
        self.assertEqual(temp['tendencia'], 'mejora')

        historial = self.client.get('/api/v1/fiax/comparaciones').get_json()['comparaciones']
        self.assertEqual(historial[0]['id'], comparacion['id'])

    def test_07d_every_procedure_type_is_recorded(self):
        self.login_admin()
        for tipo in ('dns', 'memoria', 'global'):
            res = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': tipo})
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.get_json()['tipo'], tipo)
            self.assertIn('comparacion', res.get_json())
        self.assertEqual(self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'otro'}).status_code, 400)

    def test_07e_initial_state_endpoint(self):
        self.login_admin()
        filas = self.client.get('/api/v1/fiax/estado-actual').get_json()['estado']
        self.assertIn('score_salud', [f['clave'] for f in filas])

    def test_08_incident_closes_when_condition_cleared_and_keeps_initial_score(self):
        with self.app.app_context():
            DiagnosticService.execute_complete_diagnosis()
            inc_id = self._pending_incident('CACHE_DNS_SATURADA', 'FLUSH_DNS')
            sesion = SesionDiagnostico.query.order_by(SesionDiagnostico.id.desc()).first()
            score_inicial = sesion.score_salud
            with mock.patch.object(MaintenanceService, 'flush_dns_cache', return_value={'success': True, 'mensaje': 'ok'}), \
                    mock.patch.object(DiagnosticService, 'count_dns_cache_entries', return_value=1):
                res = MaintenanceService.resolve_incident(inc_id)
            self.assertTrue(res['resuelta'])
            self.assertEqual(res['incidencia']['estado'], 'RESUELTA')
            self.assertEqual(db.session.get(SesionDiagnostico, sesion.id).score_salud, score_inicial)
            self.assertEqual(sesion.score_actual, res['nuevo_score'])

    def test_08b_failed_action_does_not_close_incident(self):
        with self.app.app_context():
            inc_id = self._pending_incident('CACHE_DNS_SATURADA', 'FLUSH_DNS')
            with mock.patch.object(MaintenanceService, 'flush_dns_cache', return_value={'success': False, 'mensaje': 'falló'}):
                res = MaintenanceService.resolve_incident(inc_id)
            self.assertFalse(res['success'])
            self.assertEqual(db.session.get(IncidenciaDetectada, inc_id).estado, 'PENDIENTE')

    def test_08c_incident_stays_pending_when_condition_persists(self):
        with self.app.app_context():
            inc_id = self._pending_incident('ALTO_CONSUMO_CPU', 'AUDITAR_PROCESOS')
            with mock.patch('psutil.cpu_percent', return_value=99.0):
                res = MaintenanceService.resolve_incident(inc_id)
            self.assertTrue(res['success'])
            self.assertFalse(res['resuelta'])
            self.assertEqual(db.session.get(IncidenciaDetectada, inc_id).estado, 'PENDIENTE')

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
        self.assertIn(Config.APP_VERSION.encode(), res.data)

        # Dashboard sin login redirige
        self.client.get('/logout')
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 302)

        # Dashboard con login renderiza exitosamente y muestra versión
        self.login_admin()
        res = self.client.get('/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Score de Salud FIAX", res.data)
        self.assertIn(Config.APP_VERSION.encode(), res.data)

        # Gestion de usuarios renderiza exitosamente y muestra versión
        res = self.client.get('/usuarios')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Control de Acceso y", res.data)
        self.assertIn(Config.APP_VERSION.encode(), res.data)

    # 8. Seguridad
    def test_13_cross_site_writes_rejected(self):
        self.login_admin()
        res = self.client.post('/api/v1/fiax/mantenimiento/optimizar', json={'tipo': 'dns'},
                               headers={'Origin': 'https://sitio-malicioso.example'})
        self.assertEqual(res.status_code, 403)

    def test_14_role_endpoints_require_login(self):
        self.client.get('/logout')
        self.assertEqual(self.client.get('/api/v1/roles').status_code, 401)
        self.assertEqual(self.client.get('/api/v1/roles/1/permissions').status_code, 401)

    def test_15_only_admin_cannot_be_demoted(self):
        self.login_admin()
        with self.app.app_context():
            admin_id = User.query.filter_by(correo='admin@fiax.com').first().id
            rol_usuario = Role.query.filter_by(nombre='USUARIO').first().id
        res = self.client.put(f'/api/v1/users/{admin_id}', json={'role_id': rol_usuario})
        self.assertEqual(res.status_code, 400)

    def test_16_short_password_rejected(self):
        self.login_admin()
        res = self.client.post('/api/v1/users', json={'nombre': 'Corta', 'correo': 'corta@fiax.com', 'password': '123'})
        self.assertEqual(res.status_code, 400)

    def test_17_legacy_hash_is_upgraded_on_login(self):
        import hashlib
        with self.app.app_context():
            user = User(nombre_completo='Legacy', correo='legacy@fiax.com',
                        password_hash=hashlib.sha256(b'clave-antigua').hexdigest())
            db.session.add(user)
            db.session.commit()
            self.assertIsNotNone(AuthService.authenticate('legacy@fiax.com', 'clave-antigua'))
            self.assertIn(':', User.query.filter_by(correo='legacy@fiax.com').first().password_hash)


class FirstRunTestCase(unittest.TestCase):
    """La versión instalable no trae cuentas conocidas."""

    def test_first_account_becomes_administrator(self):
        app = create_app('testing', instance_path=tempfile.mkdtemp(prefix="fiax-first-"))
        app.config['SEED_DEMO_USERS'] = False
        setup_initial_data(app)
        client = app.test_client()
        with app.app_context():
            self.assertEqual(User.query.count(), 0)
        self.assertIn('la del Administrador'.encode(), client.get('/').data)

        datos = {'nombre': 'Primera', 'correo': 'p@x.co', 'password': 'clave-larga', 'confirm_password': 'clave-larga'}
        self.assertEqual(client.post('/registro', data=datos).status_code, 302)
        segundo = app.test_client()
        datos = {'nombre': 'Segunda', 'correo': 's@x.co', 'password': 'clave-larga', 'confirm_password': 'clave-larga'}
        segundo.post('/registro', data=datos)
        with app.app_context():
            self.assertEqual(User.query.filter_by(correo='p@x.co').first().roles[0].nombre, 'ADMINISTRADOR')
            self.assertEqual(User.query.filter_by(correo='s@x.co').first().roles[0].nombre, 'USUARIO')


if __name__ == '__main__':
    unittest.main()
