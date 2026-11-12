"""
CONTROLADOR (MVC) - Orquesta la peticion HTTP.

Recibe los formularios, valida la entrada, llama al MODELO y entrega
la respuesta a la VISTA (plantillas). No contiene logica de calculo.
"""
import uuid
from pathlib import Path

from flask import (
    Blueprint, render_template, request, send_file, current_app, flash, redirect, url_for
)
from werkzeug.utils import secure_filename

from models.pgp_model import NotaTecnicaPGP, ErrorDatosPGP

pgp_bp = Blueprint("pgp", __name__)

EXTENSIONES_OK = {".xlsx", ".xls"}


def _guardar(archivo, carpeta: Path) -> Path:
    nombre = secure_filename(archivo.filename)
    if Path(nombre).suffix.lower() not in EXTENSIONES_OK:
        raise ErrorDatosPGP(f"'{nombre}' no es un Excel (.xlsx/.xls).")
    destino = carpeta / f"{uuid.uuid4().hex}_{nombre}"
    archivo.save(destino)
    return destino


@pgp_bp.route("/")
def index():
    """VISTA: formulario de carga."""
    return render_template("index.html")


@pgp_bp.route("/calcular", methods=["POST"])
def calcular():
    """Recibe 3 Excel + parametros, ejecuta el MODELO y muestra la nota."""
    uploads = Path(current_app.config["UPLOAD_DIR"])
    salida = Path(current_app.config["OUTPUT_DIR"])

    try:
        req_files = ("afiliados", "rips", "tarifario")
        for f in req_files:
            if f not in request.files or not request.files[f].filename:
                raise ErrorDatosPGP(f"Falta cargar el archivo de '{f}'.")

        ruta_af = _guardar(request.files["afiliados"], uploads)
        ruta_rips = _guardar(request.files["rips"], uploads)
        ruta_tar = _guardar(request.files["tarifario"], uploads)

        modelo = NotaTecnicaPGP(
            crecimiento_poblacion=float(request.form.get("crecimiento", 0.03)),
            ipc_salud=float(request.form.get("ipc", 0.05)),
            umbral_riesgo=float(request.form.get("umbral", 0.10)),
            periodo=request.form.get("periodo", "2027"),
        )
        resultado = modelo.calcular(ruta_af, ruta_rips, ruta_tar)
        archivo_salida = salida / "nota_tecnica.xlsx"
        modelo.exportar_excel(resultado, archivo_salida)

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


@pgp_bp.route("/descargar")
def descargar():
    """Entrega el Excel de la ultima nota tecnica generada."""
    archivo = Path(current_app.config["OUTPUT_DIR"]) / "nota_tecnica.xlsx"
    if not archivo.exists():
        flash("Aun no has generado ninguna nota tecnica.", "error")
        return redirect(url_for("pgp.index"))
    return send_file(archivo, as_attachment=True, download_name="nota_tecnica.xlsx")
