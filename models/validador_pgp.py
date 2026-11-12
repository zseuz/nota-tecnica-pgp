"""
MODELO (MVC) - Validador de los Excel antes de generar la nota tecnica.

Corre una secuencia de PUNTOS DE CONTROL sobre los tres archivos y reporta,
por cada uno, si esta correcto (ok), si tiene una advertencia (no bloquea) o
si tiene un error (bloquea la generacion). No conoce nada de Flask.
"""
import pandas as pd

from models.pgp_model import COLUMNAS

OK = "ok"
ERROR = "error"
ADVERTENCIA = "advertencia"

# frecuencia per capita anual por encima de la cual se sospecha un dato erroneo
FRECUENCIA_SOSPECHOSA = 50


def _punto(nombre, estado, detalle):
    return {"punto": nombre, "estado": estado, "detalle": detalle}


class ValidadorPGP:
    """Ejecuta los puntos de control sobre los Excel cargados."""

    def validar(self, ruta_afiliados, ruta_rips, ruta_tarifario) -> dict:
        checks = []

        # Punto 1: lectura de los archivos
        dfs = {}
        rutas = {"afiliados": ruta_afiliados, "rips": ruta_rips, "tarifario": ruta_tarifario}
        error_lectura = []
        for nombre, ruta in rutas.items():
            try:
                dfs[nombre] = pd.read_excel(ruta)
            except Exception as e:  # noqa: BLE001
                error_lectura.append(f"{nombre}: {e}")
        if error_lectura:
            checks.append(_punto("Lectura de archivos", ERROR,
                                  "No se pudieron abrir: " + " | ".join(error_lectura)))
            return {"ok": False, "checkpoints": checks}
        checks.append(_punto("Lectura de archivos", OK, "Los 3 Excel se abrieron correctamente."))

        # Punto 2: estructura de columnas (critico)
        faltantes = []
        for nombre, df in dfs.items():
            faltan = COLUMNAS[nombre] - set(df.columns)
            if faltan:
                faltantes.append(f"{nombre}: falta {', '.join(sorted(faltan))}")
        if faltantes:
            checks.append(_punto("Estructura de columnas", ERROR, " | ".join(faltantes)))
            return {"ok": False, "checkpoints": checks}  # sin columnas no se puede seguir
        checks.append(_punto("Estructura de columnas", OK,
                             "Todas las columnas requeridas estan presentes."))

        af, rips, tar = dfs["afiliados"], dfs["rips"], dfs["tarifario"]

        # Punto 3: valores validos (nulos / no numericos / negativos)
        problemas = []
        for df, col, etq in [(af, "num_afiliados", "afiliados"),
                             (rips, "num_atenciones", "RIPS"),
                             (tar, "costo_unitario", "tarifario")]:
            serie = pd.to_numeric(df[col], errors="coerce")
            if serie.isna().any():
                problemas.append(f"{etq}: hay valores vacios o no numericos en '{col}'")
            elif (serie < 0).any():
                problemas.append(f"{etq}: hay valores negativos en '{col}'")
        if problemas:
            checks.append(_punto("Valores numericos", ERROR, " | ".join(problemas)))
        else:
            checks.append(_punto("Valores numericos", OK,
                                 "Poblacion, atenciones y tarifas son numeros validos (>= 0)."))

        # Punto 4: duplicados en llaves
        dup = []
        if af.duplicated(subset=["grupo_etario", "sexo"]).any():
            dup.append("afiliados: hay filas repetidas de grupo_etario + sexo")
        if tar.duplicated(subset=["cups"]).any():
            dup.append("tarifario: hay CUPS repetidos")
        if dup:
            checks.append(_punto("Sin duplicados", ERROR, " | ".join(dup)))
        else:
            checks.append(_punto("Sin duplicados", OK,
                                 "No hay llaves duplicadas en afiliados ni en tarifario."))

        # Punto 5: cruce afiliados <-> RIPS
        llaves_af = set(map(tuple, af[["grupo_etario", "sexo"]].drop_duplicates().values))
        llaves_rips = set(map(tuple, rips[["grupo_etario", "sexo"]].drop_duplicates().values))
        sin_af = llaves_rips - llaves_af
        if sin_af:
            muestra = ", ".join(f"{g}/{s}" for g, s in list(sin_af)[:5])
            checks.append(_punto("Cruce afiliados-RIPS", ERROR,
                                 f"Grupos en RIPS sin afiliados: {muestra}"))
        else:
            checks.append(_punto("Cruce afiliados-RIPS", OK,
                                 "Todos los grupos de RIPS tienen afiliados."))

        # Punto 6: cruce RIPS <-> tarifario
        cups_rips = set(rips["cups"].astype(str))
        cups_tar = set(tar["cups"].astype(str))
        sin_tarifa = cups_rips - cups_tar
        if sin_tarifa:
            muestra = ", ".join(list(sin_tarifa)[:5])
            checks.append(_punto("Cruce RIPS-tarifario", ERROR,
                                 f"CUPS sin tarifa: {muestra}"))
        else:
            checks.append(_punto("Cruce RIPS-tarifario", OK,
                                 "Todos los CUPS de RIPS tienen tarifa."))

        # Punto 7: coherencia de frecuencias (solo advertencia, no bloquea)
        try:
            m = rips.merge(af, on=["grupo_etario", "sexo"], how="left")
            m["frec"] = pd.to_numeric(m["num_atenciones"], errors="coerce") / \
                pd.to_numeric(m["num_afiliados"], errors="coerce")
            altas = m[m["frec"] > FRECUENCIA_SOSPECHOSA]
            if len(altas):
                checks.append(_punto("Coherencia de frecuencias", ADVERTENCIA,
                                     f"{len(altas)} servicio(s) con frecuencia > {FRECUENCIA_SOSPECHOSA} "
                                     f"atenciones/persona al año. Revisa que no sea un error de digitacion."))
            else:
                checks.append(_punto("Coherencia de frecuencias", OK,
                                     "Las frecuencias de uso estan en rangos razonables."))
        except Exception:  # noqa: BLE001
            pass  # si falla el merge, los puntos de cruce ya reportaron el problema

        ok = all(c["estado"] != ERROR for c in checks)
        return {"ok": ok, "checkpoints": checks}
