"""
Genera 3 Excel de ejemplo (datos ficticios) que alimentan la nota tecnica de un PGP:
  - afiliados.xlsx   : poblacion a cargo por grupo etario y sexo
  - rips.xlsx        : atenciones historicas por servicio (frecuencia de uso)
  - tarifario.xlsx   : costo unitario por codigo CUPS
"""
import random
import pandas as pd
from pathlib import Path

random.seed(42)
DATA = Path(__file__).parent / "data"
DATA.mkdir(exist_ok=True)

GRUPOS = ["0-5", "6-17", "18-44", "45-59", "60+"]
SEXOS = ["F", "M"]

# Afiliados por grupo (poblacion base historica)
afiliados_base = {
    "0-5":   (1800, 1900),
    "6-17":  (4200, 4400),
    "18-44": (8500, 7800),
    "45-59": (3100, 2900),
    "60+":   (2100, 1700),
}

# Servicios: CUPS, descripcion, frecuencia anual esperada por afiliado (segun grupo)
# frecuencia = atenciones por persona al año
servicios = [
    ("890201", "Consulta medicina general",      {"0-5":2.5,"6-17":1.2,"18-44":1.6,"45-59":2.4,"60+":3.8}),
    ("890301", "Consulta medicina especializada",{"0-5":0.4,"6-17":0.3,"18-44":0.6,"45-59":1.1,"60+":2.2}),
    ("902210", "Hemograma IV",                    {"0-5":0.6,"6-17":0.4,"18-44":0.8,"45-59":1.3,"60+":2.0}),
    ("871060", "Radiografia de torax",            {"0-5":0.2,"6-17":0.2,"18-44":0.3,"45-59":0.5,"60+":0.9}),
    ("903841", "Glicemia basal",                  {"0-5":0.1,"6-17":0.2,"18-44":0.5,"45-59":1.2,"60+":1.8}),
    ("890701", "Consulta urgencias",              {"0-5":0.9,"6-17":0.5,"18-44":0.6,"45-59":0.7,"60+":1.1}),
]

# --- afiliados.xlsx ---
filas_af = []
for g in GRUPOS:
    f, m = afiliados_base[g]
    filas_af.append({"grupo_etario": g, "sexo": "F", "num_afiliados": f})
    filas_af.append({"grupo_etario": g, "sexo": "M", "num_afiliados": m})
df_af = pd.DataFrame(filas_af)
df_af.to_excel(DATA / "afiliados.xlsx", index=False)

# --- rips.xlsx (atenciones historicas = afiliados * frecuencia * ruido) ---
filas_rips = []
for cups, desc, frecs in servicios:
    for g in GRUPOS:
        for s in SEXOS:
            af = df_af[(df_af.grupo_etario == g) & (df_af.sexo == s)].num_afiliados.iloc[0]
            ruido = random.uniform(0.9, 1.1)
            atenciones = round(af * frecs[g] * ruido)
            filas_rips.append({
                "cups": cups, "descripcion": desc,
                "grupo_etario": g, "sexo": s,
                "num_atenciones": atenciones,
            })
df_rips = pd.DataFrame(filas_rips)
df_rips.to_excel(DATA / "rips.xlsx", index=False)

# --- tarifario.xlsx (costo unitario en COP) ---
tarifas = {
    "890201": 42000, "890301": 78000, "902210": 18500,
    "871060": 35000, "903841": 9800,  "890701": 95000,
}
df_tar = pd.DataFrame(
    [{"cups": c, "descripcion": d, "costo_unitario": tarifas[c]} for c, d, _ in servicios]
)
df_tar.to_excel(DATA / "tarifario.xlsx", index=False)

print("Generados en", DATA)
print(" - afiliados.xlsx :", len(df_af), "filas |", df_af.num_afiliados.sum(), "afiliados")
print(" - rips.xlsx      :", len(df_rips), "filas")
print(" - tarifario.xlsx :", len(df_tar), "servicios")
