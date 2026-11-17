"""Reporte de los mantenimientos ejecutados, filtrado por año, mes, tipo y origen."""
import csv
import io
from datetime import datetime, timezone

from sqlalchemy import func

from domain.models import EjecucionMantenimiento, format_local
from services.comparison_service import ComparisonService

MESES = ("Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio",
         "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre")

TIPOS = {
    "temporales": "Limpieza de temporales",
    "dns": "Vaciado de caché DNS",
    "memoria": "Optimización de memoria",
    "global": "Mantenimiento integral",
    "incidencia": "Resolución de incidencia",
}

ORIGENES = ("MANUAL", "PROGRAMADO")


def _local_to_utc(value):
    """Fecha local ingenua -> UTC ingenua, igual a como se guarda en la base de datos."""
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _to_local(value):
    return value.replace(tzinfo=timezone.utc).astimezone()


class ReportService:
    @staticmethod
    def parse_filters(args):
        """Valida los filtros recibidos; devuelve (filtros, error)."""
        def entero(nombre, minimo, maximo):
            bruto = (args.get(nombre) or "").strip()
            if not bruto:
                return None
            valor = int(bruto)
            if not minimo <= valor <= maximo:
                raise ValueError
            return valor

        try:
            anio = entero("anio", 2000, 2100)
            mes = entero("mes", 1, 12)
        except ValueError:
            return None, "Año o mes inválido."
        if mes and not anio:
            return None, "Para filtrar por mes también debe elegir el año."
        tipo = (args.get("tipo") or "").strip() or None
        if tipo and tipo not in TIPOS:
            return None, f"Tipo de procedimiento desconocido: {tipo}"
        origen = (args.get("origen") or "").strip().upper() or None
        if origen and origen not in ORIGENES:
            return None, f"Origen desconocido: {origen}"
        resultado = (args.get("resultado") or "").strip().lower() or None
        if resultado and resultado not in ("exito", "error"):
            return None, f"Resultado desconocido: {resultado}"
        return {"anio": anio, "mes": mes, "tipo": tipo, "origen": origen, "resultado": resultado}, None

    @staticmethod
    def query(filtros):
        q = EjecucionMantenimiento.query
        anio, mes = filtros.get("anio"), filtros.get("mes")
        if anio:
            if mes:
                inicio = datetime(anio, mes, 1)
                fin = datetime(anio + (mes == 12), mes % 12 + 1, 1)
            else:
                inicio, fin = datetime(anio, 1, 1), datetime(anio + 1, 1, 1)
            q = q.filter(EjecucionMantenimiento.fecha_hora >= _local_to_utc(inicio),
                         EjecucionMantenimiento.fecha_hora < _local_to_utc(fin))
        if filtros.get("tipo"):
            q = q.filter(EjecucionMantenimiento.tipo == filtros["tipo"])
        if filtros.get("origen"):
            q = q.filter(EjecucionMantenimiento.origen == filtros["origen"])
        if filtros.get("resultado"):
            q = q.filter(EjecucionMantenimiento.exito == (1 if filtros["resultado"] == "exito" else 0))
        return q.order_by(EjecucionMantenimiento.fecha_hora.desc(), EjecucionMantenimiento.id.desc())

    @staticmethod
    def available_years():
        minimo, maximo = EjecucionMantenimiento.query.with_entities(
            func.min(EjecucionMantenimiento.fecha_hora), func.max(EjecucionMantenimiento.fecha_hora)).one()
        actual = datetime.now().year
        if not minimo:
            return [actual]
        return list(range(max(_to_local(maximo).year, actual), _to_local(minimo).year - 1, -1))

    @staticmethod
    def _mb_liberados(ejecucion):
        antes = ejecucion.estado_inicial.get("temp_mb") or 0
        despues = ejecucion.estado_final.get("temp_mb") or 0
        return max(0.0, antes - despues)

    @classmethod
    def build(cls, filtros):
        ejecuciones = cls.query(filtros).all()
        por_mes, por_tipo = {}, {}
        score_ini = score_fin = mb_total = 0.0
        for e in ejecuciones:
            local = _to_local(e.fecha_hora)
            clave_mes = (local.year, local.month)
            mes = por_mes.setdefault(clave_mes, {"anio": local.year, "mes": local.month,
                                                 "etiqueta": f"{MESES[local.month - 1]} {local.year}",
                                                 "total": 0, "exitosos": 0, "programados": 0, "mb_liberados": 0.0})
            tipo = por_tipo.setdefault(e.tipo, {"tipo": e.tipo, "etiqueta": TIPOS.get(e.tipo, e.tipo),
                                                "total": 0, "exitosos": 0, "mb_liberados": 0.0})
            mb = cls._mb_liberados(e)
            for grupo in (mes, tipo):
                grupo["total"] += 1
                grupo["exitosos"] += 1 if e.exito else 0
                grupo["mb_liberados"] += mb
            mes["programados"] += 1 if e.origen == "PROGRAMADO" else 0
            mb_total += mb
            score_ini += e.estado_inicial.get("score_salud") or 0
            score_fin += e.estado_final.get("score_salud") or 0

        total = len(ejecuciones)
        exitosos = sum(1 for e in ejecuciones if e.exito)
        for grupo in list(por_mes.values()) + list(por_tipo.values()):
            grupo["mb_liberados"] = round(grupo["mb_liberados"], 2)
        return {
            "filtros": filtros,
            "resumen": {
                "total": total,
                "exitosos": exitosos,
                "con_errores": total - exitosos,
                "programados": sum(1 for e in ejecuciones if e.origen == "PROGRAMADO"),
                "manuales": sum(1 for e in ejecuciones if e.origen != "PROGRAMADO"),
                "mb_liberados": round(mb_total, 2),
                "score_inicial_promedio": round(score_ini / total, 1) if total else None,
                "score_final_promedio": round(score_fin / total, 1) if total else None,
            },
            "por_mes": [por_mes[k] for k in sorted(por_mes, reverse=True)],
            "por_tipo": sorted(por_tipo.values(), key=lambda g: g["total"], reverse=True),
            "ejecuciones": [ComparisonService.to_dict(e) for e in ejecuciones[:500]],
            "truncado": total > 500,
        }

    @classmethod
    def to_csv(cls, filtros):
        """CSV con ';' y BOM para que Excel en español lo abra con columnas y tildes correctas."""
        salida = io.StringIO()
        salida.write("﻿")
        writer = csv.writer(salida, delimiter=";")
        writer.writerow(["ID", "Fecha y hora", "Año", "Mes", "Procedimiento", "Tipo", "Origen", "Usuario",
                         "Resultado", "Score inicial", "Score final", "Temporales inicial (MB)",
                         "Temporales final (MB)", "MB liberados", "Disco libre inicial (GB)",
                         "Disco libre final (GB)", "Detalle"])

        def num(valor):
            return "" if valor is None else str(valor).replace(".", ",")

        for e in cls.query(filtros).all():
            local = _to_local(e.fecha_hora)
            ini, fin = e.estado_inicial, e.estado_final
            writer.writerow([
                e.id, format_local(e.fecha_hora), local.year, MESES[local.month - 1], e.titulo,
                TIPOS.get(e.tipo, e.tipo), "Programado" if e.origen == "PROGRAMADO" else "Manual",
                e.usuario.nombre_completo if e.usuario else ("Programador de tareas" if e.origen == "PROGRAMADO" else "Sistema"),
                "Exitoso" if e.exito else "Con errores",
                num(ini.get("score_salud")), num(fin.get("score_salud")),
                num(ini.get("temp_mb")), num(fin.get("temp_mb")), num(round(cls._mb_liberados(e), 2)),
                num(ini.get("disco_libre_gb")), num(fin.get("disco_libre_gb")),
                (e.mensaje or "").replace("\n", " "),
            ])
        return salida.getvalue()

    @staticmethod
    def csv_filename(filtros):
        partes = ["mantenimientos"]
        if filtros.get("anio"):
            partes.append(str(filtros["anio"]))
        if filtros.get("mes"):
            partes.append(f"{filtros['mes']:02d}")
        if filtros.get("tipo"):
            partes.append(filtros["tipo"])
        return "fiax-" + "-".join(partes) + ".csv"
