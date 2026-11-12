"""
ARRANQUE de la aplicacion (bootstrap MVC).

Crea la app Flask, carga la configuracion y registra el CONTROLADOR.
La VISTA vive en views/templates y views/static. El MODELO en models/.

Ejecutar:  python app.py   ->  http://127.0.0.1:5000
"""
from pathlib import Path
from flask import Flask

BASE_DIR = Path(__file__).parent


def crear_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(BASE_DIR / "views" / "templates"),
        static_folder=str(BASE_DIR / "views" / "static"),
    )
    app.config.update(
        SECRET_KEY="cambia-esta-clave-en-produccion",
        UPLOAD_DIR=str(BASE_DIR / "uploads"),
        OUTPUT_DIR=str(BASE_DIR / "salida"),
        MAX_CONTENT_LENGTH=10 * 1024 * 1024,  # 10 MB por carga
    )
    Path(app.config["UPLOAD_DIR"]).mkdir(exist_ok=True)
    Path(app.config["OUTPUT_DIR"]).mkdir(exist_ok=True)

    from controllers.pgp_controller import pgp_bp
    app.register_blueprint(pgp_bp)
    return app


app = crear_app()

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
