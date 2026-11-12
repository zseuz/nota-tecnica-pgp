"""
MODELO (MVC) - Logica de negocio de la nota tecnica del PGP.

Esta capa NO sabe nada de Flask ni de HTTP. Recibe rutas de archivos y
parametros, y devuelve los resultados del calculo. Es reutilizable desde
la web, un script o pruebas unitarias.

Alineado con el marco normativo colombiano del Pago Global Prospectivo:
  - Decreto 441 de 2022: obligatoriedad de la nota tecnica como anexo del
    acuerdo de voluntades y de los mecanismos de ajuste de riesgo.
  - Resolucion 2335 de 2023: ajustes de riesgo frente a las desviaciones
    de la nota tecnica e indicadores de seguimiento.
Contenido minimo reflejado: poblacion, servicios/tecnologias con codigos,
frecuencias, tarifas, modalidad de pago, mecanismo de ajuste de riesgo
(corredor de riesgo) e indicadores de monitoreo.
"""
from pathlib import Path
import pandas as pd


class ErrorDatosPGP(Exception):
    """Error de validacion de los Excel de entrada."""


COLUMNAS = {
    "afiliados": {"grupo_etario", "sexo", "num_afiliados"},
    "rips": {"cups", "descripcion", "grupo_etario", "sexo", "num_atenciones"},
    "tarifario": {"cups", "costo_unitario"},
}


def _validar(df: pd.DataFrame, nombre: str) -> pd.DataFrame:
    faltan = COLUMNAS[nombre] - set(df.columns)
    if faltan:
        raise ErrorDatosPGP(
            f"El archivo de '{nombre}' no tiene las columnas: {', '.join(sorted(faltan))}"
        )
    return df


def indicadores_monitoreo() -> pd.DataFrame:
    """
    Indicadores minimos de seguimiento que la nota tecnica debe incluir
    (Decreto 441/2022, Resolucion 2335/2023). Son plantillas: la meta se
    pacta en cada acuerdo de voluntades.
    """
    return pd.DataFrame([
        {"dimension": "Oportunidad",   "indicador": "Oportunidad en consulta de medicina general",
         "formula": "Promedio de dias entre solicitud y asignacion de la cita", "meta_referencia": "<= 3 dias"},
        {"dimension": "Accesibilidad", "indicador": "Tasa de uso de servicios",
         "formula": "Atenciones / poblacion afiliada", "meta_referencia": "Monitoreo (vs nota tecnica)"},
        {"dimension": "Calidad",       "indicador": "Reingreso a urgencias < 72 horas",
         "formula": "Reingresos < 72h / egresos de urgencias", "meta_referencia": "<= 3%"},
        {"dimension": "Seguridad",     "indicador": "Tasa de eventos adversos",
         "formula": "Eventos adversos / total de atenciones", "meta_referencia": "Minimizar"},
        {"dimension": "Experiencia",   "indicador": "Satisfaccion del usuario",
         "formula": "Usuarios satisfechos / encuestados", "meta_referencia": ">= 90%"},
        {"dimension": "Gestion - uso de recursos", "indicador": "Desviacion de la nota tecnica",
         "formula": "(Valor ejecutado - valor proyectado) / valor proyectado", "meta_referencia": "Dentro del corredor de riesgo"},
        {"dimension": "Gestion - facturacion", "indicador": "Oportunidad de radicacion",
         "formula": "Facturas radicadas a tiempo / total de facturas", "meta_referencia": ">= 95%"},
    ])


class NotaTecnicaPGP:
    """Calcula la nota tecnica de un Pago Global Prospectivo."""

    def __init__(self, crecimiento_poblacion=0.03, ipc_salud=0.05,
                 umbral_riesgo=0.10, periodo="2027"):
        self.crecimiento = float(crecimiento_poblacion)
        self.ipc = float(ipc_salud)
        self.umbral = float(umbral_riesgo)   # ancho del corredor de riesgo (+/-)
        self.periodo = str(periodo)

    def calcular(self, ruta_afiliados, ruta_rips, ruta_tarifario) -> dict:
        afiliados = _validar(pd.read_excel(ruta_afiliados), "afiliados")
        rips = _validar(pd.read_excel(ruta_rips), "rips")
        tarifario = _validar(pd.read_excel(ruta_tarifario), "tarifario")

        # 1. RIPS + afiliados -> frecuencia de uso per capita
        df = rips.merge(afiliados, on=["grupo_etario", "sexo"], how="left")
        if df["num_afiliados"].isna().any():
            raise ErrorDatosPGP(
                "Hay grupos en RIPS sin afiliados que coincidan (revisa grupo_etario/sexo)."
            )
        df["frecuencia_percapita"] = df["num_atenciones"] / df["num_afiliados"]

        # 2. + tarifario -> costo unitario
        df = df.merge(tarifario[["cups", "costo_unitario"]], on="cups", how="left")
        if df["costo_unitario"].isna().any():
            faltan = df.loc[df["costo_unitario"].isna(), "cups"].unique()
            raise ErrorDatosPGP(f"CUPS sin tarifa en el tarifario: {', '.join(map(str, faltan))}")

        # 3. Proyeccion y costo esperado
        df["poblacion_objetivo"] = (df["num_afiliados"] * (1 + self.crecimiento)).round()
        df["atenciones_proyectadas"] = (df["frecuencia_percapita"] * df["poblacion_objetivo"]).round()
        df["costo_esperado"] = df["atenciones_proyectadas"] * df["costo_unitario"]

        # 4. Ajuste por IPC salud
        df["costo_ajustado"] = (df["costo_esperado"] * (1 + self.ipc)).round()

        # 5. Resumen por servicio (la nota tecnica)
        nota = (
            df.groupby(["cups", "descripcion"], as_index=False)
              .agg(atenciones_proyectadas=("atenciones_proyectadas", "sum"),
                   costo_ajustado=("costo_ajustado", "sum"))
              .sort_values("costo_ajustado", ascending=False)
              .reset_index(drop=True)
        )

        valor_pgp = float(nota["costo_ajustado"].sum())
        pob_objetivo = float(afiliados["num_afiliados"].sum() * (1 + self.crecimiento))
        per_capita_mes = valor_pgp / pob_objetivo / 12 if pob_objetivo else 0

        # 6. Mecanismo de ajuste de riesgo: corredor de riesgo (Dec. 441/2022)
        banda_inferior = round(valor_pgp * (1 - self.umbral))
        banda_superior = round(valor_pgp * (1 + self.umbral))

        return {
            "nota": nota,
            "detalle": df,
            "valor_pgp": valor_pgp,
            "poblacion_objetivo": round(pob_objetivo),
            "per_capita_mes": round(per_capita_mes),
            "corredor_riesgo": {
                "umbral": self.umbral,
                "banda_inferior": banda_inferior,
                "valor_esperado": round(valor_pgp),
                "banda_superior": banda_superior,
            },
            "indicadores": indicadores_monitoreo(),
            "parametros": {
                "periodo": self.periodo,
                "crecimiento_poblacion": self.crecimiento,
                "ipc_salud": self.ipc,
                "umbral_riesgo": self.umbral,
            },
        }

    def evaluar_ejecucion(self, resultado: dict, valor_ejecutado: float) -> dict:
        """
        Dado un valor realmente ejecutado, calcula la desviacion frente a la
        nota tecnica y si aplica ajuste de riesgo (Resolucion 2335/2023).
        """
        esperado = resultado["valor_pgp"]
        cr = resultado["corredor_riesgo"]
        desviacion = (valor_ejecutado - esperado) / esperado if esperado else 0
        if valor_ejecutado < cr["banda_inferior"]:
            estado, aplica = "Por debajo del corredor", True
        elif valor_ejecutado > cr["banda_superior"]:
            estado, aplica = "Por encima del corredor", True
        else:
            estado, aplica = "Dentro del corredor", False
        return {
            "valor_ejecutado": round(valor_ejecutado),
            "desviacion": desviacion,
            "estado": estado,
            "aplica_ajuste": aplica,
        }

    def exportar_excel(self, resultado: dict, ruta_salida) -> Path:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        nota = resultado["nota"].copy()
        total = pd.DataFrame([{
            "cups": "", "descripcion": "VALOR GLOBAL PGP",
            "atenciones_proyectadas": nota["atenciones_proyectadas"].sum(),
            "costo_ajustado": resultado["valor_pgp"],
        }])
        nota_total = pd.concat([nota, total], ignore_index=True)
        cr = resultado["corredor_riesgo"]
        p = resultado["parametros"]

        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as xls:
            nota_total.to_excel(xls, sheet_name="Nota_Tecnica", index=False)
            resultado["detalle"].to_excel(xls, sheet_name="Detalle_calculo", index=False)
            pd.DataFrame([
                {"concepto": "Umbral del corredor (+/-)", "valor": f"{cr['umbral']:.0%}"},
                {"concepto": "Banda inferior (COP)", "valor": cr["banda_inferior"]},
                {"concepto": "Valor esperado (COP)", "valor": cr["valor_esperado"]},
                {"concepto": "Banda superior (COP)", "valor": cr["banda_superior"]},
            ]).to_excel(xls, sheet_name="Corredor_riesgo", index=False)
            resultado["indicadores"].to_excel(xls, sheet_name="Indicadores", index=False)
            pd.DataFrame([
                {"parametro": "Periodo", "valor": p["periodo"]},
                {"parametro": "Crecimiento poblacion", "valor": f"{p['crecimiento_poblacion']:.0%}"},
                {"parametro": "IPC salud", "valor": f"{p['ipc_salud']:.0%}"},
                {"parametro": "Umbral de riesgo", "valor": f"{p['umbral_riesgo']:.0%}"},
                {"parametro": "Poblacion objetivo", "valor": resultado["poblacion_objetivo"]},
                {"parametro": "Valor global PGP (COP)", "valor": round(resultado["valor_pgp"])},
                {"parametro": "Per capita mensual (COP)", "valor": resultado["per_capita_mes"]},
            ]).to_excel(xls, sheet_name="Parametros", index=False)
        return ruta_salida
