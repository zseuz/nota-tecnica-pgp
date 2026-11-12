"""
MODELO (MVC) - Logica de negocio de la nota tecnica del PGP.

Esta capa NO sabe nada de Flask ni de HTTP. Solo recibe rutas de archivos
y parametros, y devuelve los resultados del calculo. Es reutilizable desde
la web, desde un script o desde pruebas unitarias.
"""
from pathlib import Path
import pandas as pd


class ErrorDatosPGP(Exception):
    """Error de validacion de los Excel de entrada."""


# Columnas que debe traer cada archivo
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


class NotaTecnicaPGP:
    """Calcula la nota tecnica de un Pago Global Prospectivo."""

    def __init__(self, crecimiento_poblacion=0.03, ipc_salud=0.05, periodo="2027"):
        self.crecimiento = float(crecimiento_poblacion)
        self.ipc = float(ipc_salud)
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

        return {
            "nota": nota,
            "detalle": df,
            "valor_pgp": valor_pgp,
            "poblacion_objetivo": round(pob_objetivo),
            "per_capita_mes": round(per_capita_mes),
            "parametros": {
                "periodo": self.periodo,
                "crecimiento_poblacion": self.crecimiento,
                "ipc_salud": self.ipc,
            },
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

        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as xls:
            nota_total.to_excel(xls, sheet_name="Nota_Tecnica", index=False)
            resultado["detalle"].to_excel(xls, sheet_name="Detalle_calculo", index=False)
            p = resultado["parametros"]
            pd.DataFrame([
                {"parametro": "Periodo", "valor": p["periodo"]},
                {"parametro": "Crecimiento poblacion", "valor": f"{p['crecimiento_poblacion']:.0%}"},
                {"parametro": "IPC salud", "valor": f"{p['ipc_salud']:.0%}"},
                {"parametro": "Poblacion objetivo", "valor": resultado["poblacion_objetivo"]},
                {"parametro": "Valor global PGP (COP)", "valor": round(resultado["valor_pgp"])},
                {"parametro": "Per capita mensual (COP)", "valor": resultado["per_capita_mes"]},
            ]).to_excel(xls, sheet_name="Parametros", index=False)
        return ruta_salida
