"""
CONTROLADOR (MVC) - Orquesta la peticion HTTP.

Flujo:
  1. /validar  (POST, AJAX) -> guarda los 3 Excel bajo un token, corre los
     puntos de control y devuelve el reporte en JSON.
  2. /calcular (POST)       -> con el token de unos archivos ya validados,
     ejecuta el MODELO y muestra la nota tecnica.
No contiene logica de calculo ni de validacion; delega en el MODELO.
"""
import re
import uuid
from pathlib import Path

from flask import (
    Blueprint, render_template, request, send_file, current_app,
    flash, redirect, url_for, jsonify
)
from werkzeug.utils import secure_filename

from models.pgp_model import NotaTecnicaPGP, ErrorDatosPGP
from models.validador_pgp import ValidadorPGP
from models.liquidacion_evento import LiquidacionEvento

pgp_bp = Blueprint("pgp", __name__)

EXTENSIONES_OK = {".xlsx", ".xls"}
ARCHIVOS = ("afiliados", "rips", "tarifario")
TOKEN_RE = re.compile(r"^[0-9a-f]{32}$")


def _es_excel(filename: str) -> bool:
    return Path(secure_filename(filename)).suffix.lower() in EXTENSIONES_OK


@pgp_bp.route("/")
def index():
    """VISTA: formulario de carga con validacion por puntos de control."""
    return render_template("index.html")


@pgp_bp.route("/validar", methods=["POST"])
def validar():
    """Guarda los 3 Excel bajo un token y devuelve el reporte de control (JSON)."""
    for f in ARCHIVOS:
        if f not in request.files or not request.files[f].filename:
            return jsonify({"ok": False, "error": f"Falta cargar el archivo de '{f}'."}), 400
        if not _es_excel(request.files[f].filename):
            return jsonify({"ok": False, "error": f"'{request.files[f].filename}' no es un Excel (.xlsx/.xls)."}), 400

    token = uuid.uuid4().hex
    carpeta = Path(current_app.config["UPLOAD_DIR"]) / token
    carpeta.mkdir(parents=True, exist_ok=True)
    for f in ARCHIVOS:
        request.files[f].save(carpeta / f"{f}.xlsx")

    reporte = ValidadorPGP().validar(
        carpeta / "afiliados.xlsx", carpeta / "rips.xlsx", carpeta / "tarifario.xlsx"
    )
    reporte["token"] = token
    return jsonify(reporte)


def _rutas_por_token(token: str):
    if not token or not TOKEN_RE.match(token):
        raise ErrorDatosPGP("Token de validacion invalido. Vuelve a cargar los archivos.")
    carpeta = Path(current_app.config["UPLOAD_DIR"]) / token
    rutas = [carpeta / f"{f}.xlsx" for f in ARCHIVOS]
    if not all(p.exists() for p in rutas):
        raise ErrorDatosPGP("Los archivos validados ya no estan disponibles. Vuelve a cargarlos.")
    return rutas


@pgp_bp.route("/calcular", methods=["POST"])
def calcular():
    """Con los archivos ya validados (token), ejecuta el MODELO y muestra la nota."""
    salida = Path(current_app.config["OUTPUT_DIR"])
    try:
        ruta_af, ruta_rips, ruta_tar = _rutas_por_token(request.form.get("token", ""))

        modelo = NotaTecnicaPGP(
            crecimiento_poblacion=float(request.form.get("crecimiento", 0.03)),
            ipc_salud=float(request.form.get("ipc", 0.05)),
            umbral_riesgo=float(request.form.get("umbral", 0.10)),
            periodo=request.form.get("periodo", "2027"),
        )
        resultado = modelo.calcular(ruta_af, ruta_rips, ruta_tar)
        modelo.exportar_excel(resultado, salida / "nota_tecnica.xlsx")

        return render_template(
            "resultado.html",
            nota=resultado["nota"].to_dict(orient="records"),
            valor_pgp=resultado["valor_pgp"],
            poblacion=resultado["poblacion_objetivo"],
            per_capita=resultado["per_capita_mes"],
            corredor=resultado["corredor_riesgo"],
            indicadores=resultado["indicadores"].to_dict(orient="records"),
            parametros=resultado["parametros"],
        )
    except ErrorDatosPGP as e:
        flash(str(e), "error")
        return redirect(url_for("pgp.index"))
    except Exception as e:  # noqa: BLE001
        flash(f"Error inesperado: {e}", "error")
        return redirect(url_for("pgp.index"))


@pgp_bp.route("/evento", methods=["POST"])
def evento():
    """Con los archivos ya validados (token), liquida por pago por EVENTO."""
    salida = Path(current_app.config["OUTPUT_DIR"])
    try:
        _, ruta_rips, ruta_tar = _rutas_por_token(request.form.get("token", ""))

        liq = LiquidacionEvento(periodo=request.form.get("periodo", "2027"))
        resultado = liq.calcular(ruta_rips, ruta_tar)
        liq.exportar_excel(resultado, salida / "liquidacion_evento.xlsx")

        return render_template(
            "evento.html",
            resumen=resultado["resumen"].to_dict(orient="records"),
            total=resultado["total"],
            atenciones=resultado["atenciones"],
            costo_promedio=resultado["costo_promedio"],
            periodo=resultado["periodo"],
        )
    except ErrorDatosPGP as e:
        flash(str(e), "error")
        return redirect(url_for("pgp.index"))
    except Exception as e:  # noqa: BLE001
        flash(f"Error inesperado: {e}", "error")
        return redirect(url_for("pgp.index"))


@pgp_bp.route("/descargar")
def descargar():
    """Entrega el Excel de la ultima nota tecnica generada."""
    archivo = Path(current_app.config["OUTPUT_DIR"]) / "nota_tecnica.xlsx"
    if not archivo.exists():
        flash("Aun no has generado ninguna nota tecnica.", "error")
        return redirect(url_for("pgp.index"))
    return send_file(archivo, as_attachment=True, download_name="nota_tecnica.xlsx")


@pgp_bp.route("/descargar-evento")
def descargar_evento():
    """Entrega el Excel de la ultima liquidacion por evento."""
    archivo = Path(current_app.config["OUTPUT_DIR"]) / "liquidacion_evento.xlsx"
    if not archivo.exists():
        flash("Aun no has generado ninguna liquidacion por evento.", "error")
        return redirect(url_for("pgp.index"))
    return send_file(archivo, as_attachment=True, download_name="liquidacion_evento.xlsx")
