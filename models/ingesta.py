"""
MODELO (MVC) - Capa de ingesta: normaliza distintas FUENTES de frecuencias a
una tabla canonica que el resto del modelo entiende.

Tabla canonica:  cups, descripcion, grupo_etario, sexo, num_atenciones

Esto desacopla el origen de los datos del calculo: para soportar una nueva
fuente solo se agrega un adaptador, sin tocar la nota tecnica ni el evento.
No conoce Flask.
"""
import pandas as pd

from models.pgp_model import ErrorDatosPGP

CANONICO = ["cups", "descripcion", "grupo_etario", "sexo", "num_atenciones"]
LLAVES = ["cups", "descripcion", "grupo_etario", "sexo"]


class AdaptadorFuente:
    """Contrato: toda fuente se normaliza a la tabla canonica."""
    nombre = "generico"

    def normalizar(self, ruta) -> pd.DataFrame:
        raise NotImplementedError

    @staticmethod
    def _sexo_canonico(serie: pd.Series) -> pd.Series:
        # 'Femenino'/'F' -> 'F'; 'Masculino'/'Hombre'/'M' -> 'M'
        inicial = serie.astype(str).str.strip().str.upper().str[0]
        return inicial.replace({"H": "M"})


class AdaptadorRIPS(AdaptadorFuente):
    """RIPS: ya vienen con las columnas canonicas. Acepta agregado o crudo."""
    nombre = "RIPS"

    def normalizar(self, ruta) -> pd.DataFrame:
        df = pd.read_excel(ruta)
        faltan = set(LLAVES) - set(df.columns)
        if faltan:
            raise ErrorDatosPGP(f"RIPS: faltan columnas {', '.join(sorted(faltan))}")
        if "num_atenciones" in df.columns:
            # ya agregado -> consolidar por si viene en varias filas
            out = df.groupby(LLAVES, as_index=False)["num_atenciones"].sum()
        else:
            # RIPS crudo: una fila por atencion -> contar
            out = df.groupby(LLAVES).size().reset_index(name="num_atenciones")
        return out[CANONICO]


class AdaptadorFacturacion(AdaptadorFuente):
    """Consolidado de facturacion con otros nombres de columna -> canonico."""
    nombre = "Facturacion"
    MAPEO = {
        "codigo_servicio": "cups",
        "descripcion_servicio": "descripcion",
        "grupo_edad": "grupo_etario",
        "genero": "sexo",
        "cantidad": "num_atenciones",
    }

    def normalizar(self, ruta) -> pd.DataFrame:
        df = pd.read_excel(ruta)
        faltan = set(self.MAPEO) - set(df.columns)
        if faltan:
            raise ErrorDatosPGP(f"Facturacion: faltan columnas {', '.join(sorted(faltan))}")
        df = df.rename(columns=self.MAPEO)
        df["sexo"] = self._sexo_canonico(df["sexo"])
        out = df.groupby(LLAVES, as_index=False)["num_atenciones"].sum()
        return out[CANONICO]


ADAPTADORES = {
    "rips": AdaptadorRIPS,
    "facturacion": AdaptadorFacturacion,
}


def normalizar_fuente(ruta, fuente="rips") -> pd.DataFrame:
    """Devuelve la tabla canonica de frecuencias a partir de la fuente indicada."""
    clase = ADAPTADORES.get(fuente)
    if clase is None:
        raise ErrorDatosPGP(f"Fuente desconocida: '{fuente}'. Opciones: {', '.join(ADAPTADORES)}")
    return clase().normalizar(ruta)
