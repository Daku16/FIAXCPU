import os
import platform
import socket
import time
from datetime import datetime
import psutil
from domain.models import db, Equipo, get_utc_now

class TelemetryService:
    @staticmethod
    def _processor_name():
        """Nombre comercial del procesador, que platform.processor() no da en todos los sistemas."""
        try:
            if os.name == 'nt':
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
                return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
            if os.path.exists('/proc/cpuinfo'):
                with open('/proc/cpuinfo', encoding='utf-8', errors='replace') as handle:
                    for line in handle:
                        if line.lower().startswith('model name'):
                            return line.split(':', 1)[1].strip()
        except OSError:
            pass
        return platform.processor() or platform.machine() or "Desconocido"

    @staticmethod
    def get_hardware_profile():
        """Obtiene la ficha técnica del hardware y sistema operativo anfitrión."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 80))
            ip_local = s.getsockname()[0]
            s.close()
        except OSError:
            ip_local = "127.0.0.1"

        return {
            "nombre_equipo": platform.node() or socket.gethostname() or "Equipo local",
            "os_version": f"{platform.system()} {platform.release()} (Build {platform.version()})",
            "arquitectura": platform.machine(),
            "procesador": TelemetryService._processor_name(),
            "ram_total_gb": round(psutil.virtual_memory().total / (1024 ** 3), 2),
            "ip_local": ip_local
        }

    @staticmethod
    def get_or_register_host_equipo():
        """Registra o actualiza el equipo anfitrión en la base de datos."""
        profile = TelemetryService.get_hardware_profile()
        equipo = Equipo.query.filter_by(nombre_equipo=profile["nombre_equipo"]).first()
        
        if not equipo:
            equipo = Equipo(
                nombre_equipo=profile["nombre_equipo"],
                os_version=profile["os_version"],
                arquitectura=profile["arquitectura"],
                ram_total_gb=profile["ram_total_gb"],
                procesador=profile["procesador"],
                ip_local=profile["ip_local"],
                ultima_conexion=get_utc_now()
            )
            db.session.add(equipo)
            db.session.commit()
        else:
            equipo.ultima_conexion = get_utc_now()
            equipo.ip_local = profile["ip_local"]
            equipo.os_version = profile["os_version"]
            equipo.procesador = profile["procesador"]
            equipo.ram_total_gb = profile["ram_total_gb"]
            db.session.commit()
            
        return equipo

    @staticmethod
    def get_live_metrics(cpu_interval=0.1):
        """Captura métricas reales; si fallan, propaga el error en lugar de inventar valores."""
        # CPU
        cpu_pct = psutil.cpu_percent(interval=cpu_interval)
        cpu_cores_logical = psutil.cpu_count(logical=True) or 4
        cpu_cores_physical = psutil.cpu_count(logical=False) or 2

        # Memoria
        mem = psutil.virtual_memory()
        ram_pct = mem.percent
        ram_used_gb = round((mem.total - mem.available) / (1024 ** 3), 2)
        ram_free_gb = round(mem.available / (1024 ** 3), 2)
        ram_total_gb = round(mem.total / (1024 ** 3), 2)

        # Disco Principal
        system_drive = os.getenv('SystemDrive', 'C:') if os.name == 'nt' else '/'
        disk_path = f"{system_drive}\\" if os.name == 'nt' else '/'
        disk = psutil.disk_usage(disk_path)
        disk_pct = disk.percent
        disk_free_gb = round(disk.free / (1024 ** 3), 2)
        disk_total_gb = round(disk.total / (1024 ** 3), 2)
        disk_used_gb = round(disk.used / (1024 ** 3), 2)

        # Procesos
        active_procs_count = len(psutil.pids())

        # Top 5 Procesos por uso de memoria
        top_procs = []
        try:
            for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info', 'status']):
                try:
                    info = p.info
                    name = info.get('name') or "Desconocido"
                    mem_pct = round(info.get('memory_percent') or 0.0, 1)
                    mem_mb = round((info.get('memory_info').rss / (1024 * 1024)), 1) if info.get('memory_info') else 0.0
                    top_procs.append({
                        "pid": info.get('pid'),
                        "name": name,
                        "cpu_percent": round(info.get('cpu_percent') or 0.0, 1),
                        "memory_percent": mem_pct,
                        "memory_mb": mem_mb,
                        "status": info.get('status') or "running"
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess, Exception):
                    continue
        except (psutil.Error, OSError):
            # La lista de procesos es complementaria: no invalida las demás métricas.
            pass

        # Ordenar por consumo de memoria descendente
        top_procs = sorted(top_procs, key=lambda x: x['memory_mb'], reverse=True)[:5]

        # Tiempo de actividad (uptime)
        uptime_seconds = int(time.time() - psutil.boot_time())
        horas_uptime = uptime_seconds // 3600
        minutos_uptime = (uptime_seconds % 3600) // 60

        return {
            "cpu": {
                "usage_percent": cpu_pct,
                "cores_logical": cpu_cores_logical,
                "cores_physical": cpu_cores_physical
            },
            "ram": {
                "usage_percent": ram_pct,
                "used_gb": ram_used_gb,
                "free_gb": ram_free_gb,
                "total_gb": ram_total_gb
            },
            "disk": {
                "usage_percent": disk_pct,
                "used_gb": disk_used_gb,
                "free_gb": disk_free_gb,
                "total_gb": disk_total_gb,
                "drive": system_drive
            },
            "procesos_activos": active_procs_count,
            "top_procesos": top_procs,
            "uptime": f"{horas_uptime}h {minutos_uptime}m",
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
