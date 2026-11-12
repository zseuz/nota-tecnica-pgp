# Nota Técnica PGP — Aplicación web (MVC)

Aplicación web que calcula la **nota técnica de un Pago Global Prospectivo (PGP)**
a partir de tres archivos Excel (afiliados, RIPS/atenciones y tarifario), los cruza
y genera el valor global del PGP, el per cápita y un Excel descargable.

> Prototipo con fines de demostración. Los datos y parámetros son responsabilidad
> de quien los carga; el modelo de cálculo es simplificado y debe validarse antes
> de un uso real.

---

## Arquitectura MVC

El proyecto separa responsabilidades en las tres capas del patrón
**Modelo–Vista–Controlador**:

```
pgp_app/
├── app.py                        # Arranque: crea la app Flask y registra el controlador
├── models/
│   └── pgp_model.py              # MODELO  -> lógica de negocio y cálculo (sin Flask)
├── controllers/
│   └── pgp_controller.py         # CONTROLADOR -> rutas HTTP, valida y orquesta
├── views/
│   ├── templates/                # VISTA -> HTML (Jinja2)
│   │   ├── base.html
│   │   ├── index.html            #   formulario de carga
│   │   └── resultado.html        #   nota técnica
│   └── static/
│       └── estilo.css
├── uploads/                      # Excel cargados (temporal)
├── salida/                       # nota_tecnica.xlsx generado
└── README.md
```

| Capa          | Archivo                      | Responsabilidad                                           |
|---------------|------------------------------|-----------------------------------------------------------|
| **Modelo**    | `models/pgp_model.py`        | Carga Excel, valida columnas, calcula, exporta. No conoce HTTP. |
| **Vista**     | `views/templates/*.html`     | Presenta el formulario y los resultados.                  |
| **Controlador** | `controllers/pgp_controller.py` | Recibe peticiones, valida archivos, llama al modelo, elige la vista. |

Esta separación permite reutilizar el **Modelo** desde un script, una API o pruebas,
sin tocar la interfaz.

---

## Requisitos

- Python 3.10+
- Librerías: `flask`, `pandas`, `openpyxl`

```bash
pip install flask pandas openpyxl
```

## Cómo ejecutar

```bash
cd pgp_app
python app.py
```

Abrir en el navegador: **http://127.0.0.1:5000**

---

## Formato de los Excel de entrada

Cada archivo debe traer exactamente estas columnas:

**afiliados.xlsx**
| grupo_etario | sexo | num_afiliados |
|--------------|------|---------------|
| 18-44        | F    | 8500          |

**rips.xlsx** (atenciones históricas)
| cups   | descripcion               | grupo_etario | sexo | num_atenciones |
|--------|---------------------------|--------------|------|----------------|
| 890201 | Consulta medicina general | 18-44        | F    | 13600          |

**tarifario.xlsx**
| cups   | costo_unitario |
|--------|----------------|
| 890201 | 42000          |

Las llaves de cruce son: `grupo_etario` + `sexo` (afiliados ↔ RIPS) y `cups`
(RIPS ↔ tarifario).

---

## Lógica de cálculo

1. **Frecuencia de uso per cápita** = `num_atenciones / num_afiliados` (por grupo y servicio).
2. **Población objetivo** = `num_afiliados × (1 + crecimiento)`.
3. **Atenciones proyectadas** = `frecuencia × población_objetivo`.
4. **Costo esperado** = `atenciones_proyectadas × costo_unitario`.
5. **Costo ajustado** = `costo_esperado × (1 + IPC_salud)`.
6. **Valor global del PGP** = suma de todos los costos ajustados.
7. **Per cápita mensual** = `valor_PGP / población_objetivo / 12`.

Parámetros configurables desde el formulario: crecimiento de población, IPC salud y periodo.

---

## Validaciones

El modelo rechaza con un mensaje claro cuando:
- Falta alguno de los tres archivos o no es `.xlsx/.xls`.
- Un archivo no trae las columnas requeridas.
- Hay grupos en RIPS sin afiliados que coincidan.
- Hay un CUPS en RIPS sin tarifa en el tarifario.

---

## Cómo adaptarlo a datos reales

- Ajustar nombres de columnas en `COLUMNAS` (dentro de `models/pgp_model.py`) a los de tus Excel.
- Afinar parámetros (crecimiento, IPC) o añadir ajuste por riesgo / separar
  ambulatorio y hospitalario en el método `calcular`.
- Para producción: desactivar `debug=True`, mover `SECRET_KEY` a variable de entorno
  y limpiar la carpeta `uploads/` periódicamente.

---

## Datos de ejemplo

El proyecto hermano `pgp_demo` incluye `generar_datos.py`, que crea tres Excel ficticios
con el formato correcto para probar la aplicación sin datos reales.
