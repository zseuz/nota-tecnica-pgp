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
│   ├── pgp_model.py              # MODELO  -> nota técnica PGP (prospectivo)
│   ├── liquidacion_evento.py     # MODELO  -> liquidación por evento (retrospectivo)
│   ├── ingesta.py                # MODELO  -> adaptadores de fuente (RIPS, facturación)
│   └── validador_pgp.py          # MODELO  -> puntos de control sobre los Excel
├── controllers/
│   └── pgp_controller.py         # CONTROLADOR -> rutas HTTP, valida y orquesta
├── views/
│   ├── templates/                # VISTA -> HTML (Jinja2)
│   │   ├── base.html
│   │   ├── index.html            #   carga + puntos de control
│   │   └── resultado.html        #   nota técnica
│   └── static/
│       ├── estilo.css
│       └── validacion.js         #   muestra los chequeos y habilita generar
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

## Flujo de validación (puntos de control)

Antes de generar la nota técnica, la app corre una secuencia de chequeos y solo
habilita la generación si no hay errores:

1. Cargas los tres Excel y pulsas **Validar archivos**.
2. El cliente los envía a `POST /validar`, que los guarda bajo un token y corre
   los puntos de control:
   - Lectura de los archivos.
   - Estructura de columnas.
   - Valores numéricos (sin vacíos ni negativos).
   - Sin llaves duplicadas.
   - Cruce afiliados ↔ RIPS.
   - Cruce RIPS ↔ tarifario.
   - Coherencia de frecuencias (*advertencia*, no bloquea).
3. Los chequeos se muestran uno a uno. Cada punto es **ok**, **advertencia** o **error**.
4. Si todo pasa, aparece el botón **Generar nota técnica para entregar**, que
   envía el token a `POST /calcular` (no hay que volver a subir los archivos).
5. Si hay errores, se listan y la generación queda bloqueada hasta corregir.

## Capa de ingesta (fuente-agnóstico)

El cálculo está desacoplado del origen de los datos. Un **adaptador** normaliza
la fuente de frecuencias a una tabla canónica y el resto del modelo nunca cambia:

```
cups, descripcion, grupo_etario, sexo, num_atenciones
```

Adaptadores incluidos (`models/ingesta.py`):

| Fuente | Entrada esperada | Qué hace |
|--------|------------------|----------|
| `rips` | cups, descripcion, grupo_etario, sexo (+ num_atenciones opcional) | Consolida; si viene crudo (una fila por atención), cuenta |
| `facturacion` | codigo_servicio, descripcion_servicio, grupo_edad, genero, cantidad | Renombra al canónico y normaliza el sexo (Femenino/Masculino → F/M) |

En el formulario eliges la **fuente**; la ingesta corre como primer punto de
control. Para soportar un origen nuevo (p. ej. autorizaciones) basta con agregar
una clase adaptadora, sin tocar la nota técnica ni el evento.

## Modalidades de pago

Tras validar, puedes generar dos modalidades con los mismos archivos:

| Modalidad | Qué calcula | Insumos | Fórmula |
|-----------|-------------|---------|---------|
| **PGP** (prospectivo) | Valor global anticipado + corredor de riesgo | afiliados, RIPS, tarifario | frecuencia × tarifa × población proyectada, con IPC |
| **Evento** (retrospectivo) | Pago por cada atención prestada | RIPS, tarifario | `Σ atenciones × tarifa` |

El PGP transfiere riesgo al prestador (banda de riesgo); el evento no. Comparar
ambos valores sobre los mismos datos ayuda a sustentar la negociación.

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
8. **Corredor de riesgo** = banda `[valor × (1 − umbral), valor × (1 + umbral)]`.

Parámetros configurables desde el formulario: crecimiento de población, IPC salud,
umbral del corredor de riesgo y periodo.

## Alineación normativa (Colombia)

El modelo refleja el contenido mínimo que exige la normatividad del Pago Global
Prospectivo, para que la nota técnica sea válida como anexo del acuerdo de voluntades:

| Exigencia normativa | Dónde se implementa |
|---------------------|---------------------|
| Nota técnica obligatoria como anexo del acuerdo (Decreto 441/2022) | `Nota_Tecnica` + `Detalle_calculo` |
| Población, servicios con códigos CUPS, frecuencias y tarifas | insumos y cruce del modelo |
| Mecanismo de ajuste de riesgo / corredor de riesgo (Decreto 441/2022) | `corredor_riesgo` + `evaluar_ejecucion()` |
| Ajuste frente a desviaciones de la nota técnica (Resolución 2335/2023) | `evaluar_ejecucion()` (dentro/fuera del corredor) |
| Indicadores de monitoreo (calidad, oportunidad, accesibilidad, seguridad, gestión) | `indicadores_monitoreo()` → hoja `Indicadores` |

> Las metas de los indicadores y el ancho del corredor se pactan en cada acuerdo;
> aquí vienen como plantilla y parámetro configurables.

El método `evaluar_ejecucion(resultado, valor_ejecutado)` compara lo realmente
ejecutado contra la banda y señala si aplica ajuste de riesgo; es la base para
el seguimiento de la nota técnica durante la vigencia del contrato.

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
