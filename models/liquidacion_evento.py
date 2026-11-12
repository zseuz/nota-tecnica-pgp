"""
MODELO (MVC) - Liquidacion por EVENTO.

Modalidad de pago retrospectiva: se paga por cada atencion realmente prestada
a su tarifa pactada. No hay proyeccion de poblacion, ni ajuste por IPC, ni
corredor de riesgo (el evento no transfiere riesgo al prestador).

    valor_evento = sum( num_atenciones * costo_unitario )

Solo requiere RIPS + tarifario. No conoce Flask.
"""
from pathlib import Path
import pandas as pd

from models.pgp_model import _validar, ErrorDatosPGP


class LiquidacionEvento:
    """Liquida los servicios prestados bajo la modalidad de pago por evento."""

    def __init__(self, periodo="2027"):
        self.periodo = str(periodo)

    def calcular(self, ruta_rips, ruta_tarifario) -> dict:
        rips = _validar(pd.read_excel(ruta_rips), "rips")
        tar = _validar(pd.read_excel(ruta_tarifario), "tarifario")

        df = rips.merge(tar[["cups", "costo_unitario"]], on="cups", how="left")
        if df["costo_unitario"].isna().any():
            faltan = df.loc[df["costo_unitario"].isna(), "cups"].unique()
            raise ErrorDatosPGP(f"CUPS sin tarifa en el tarifario: {', '.join(map(str, faltan))}")

        df["valor_evento"] = df["num_atenciones"] * df["costo_unitario"]

        resumen = (
            df.groupby(["cups", "descripcion"], as_index=False)
              .agg(num_atenciones=("num_atenciones", "sum"),
                   costo_unitario=("costo_unitario", "first"),
                   valor_evento=("valor_evento", "sum"))
              .sort_values("valor_evento", ascending=False)
              .reset_index(drop=True)
        )
        total = float(resumen["valor_evento"].sum())
        atenciones = int(resumen["num_atenciones"].sum())
        costo_promedio = total / atenciones if atenciones else 0

        return {
            "resumen": resumen,
            "detalle": df,
            "total": total,
            "atenciones": atenciones,
            "costo_promedio": round(costo_promedio),
            "periodo": self.periodo,
        }

    def exportar_excel(self, resultado: dict, ruta_salida) -> Path:
        ruta_salida = Path(ruta_salida)
        ruta_salida.parent.mkdir(parents=True, exist_ok=True)
        resumen = resultado["resumen"].copy()
        total = pd.DataFrame([{
            "cups": "", "descripcion": "TOTAL LIQUIDACION POR EVENTO",
            "num_atenciones": resumen["num_atenciones"].sum(),
            "costo_unitario": "", "valor_evento": resultado["total"],
        }])
        resumen_total = pd.concat([resumen, total], ignore_index=True)

        with pd.ExcelWriter(ruta_salida, engine="openpyxl") as xls:
            resumen_total.to_excel(xls, sheet_name="Liquidacion_evento", index=False)
            resultado["detalle"].to_excel(xls, sheet_name="Detalle", index=False)
            pd.DataFrame([
                {"parametro": "Periodo", "valor": resultado["periodo"]},
                {"parametro": "Modalidad", "valor": "Pago por evento"},
                {"parametro": "Total atenciones", "valor": resultado["atenciones"]},
                {"parametro": "Valor total (COP)", "valor": round(resultado["total"])},
                {"parametro": "Costo promedio por atencion (COP)", "valor": resultado["costo_promedio"]},
            ]).to_excel(xls, sheet_name="Parametros", index=False)
        return ruta_salida
