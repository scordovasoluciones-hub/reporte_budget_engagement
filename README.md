# Reporte Budget Engagement · Compassion Perú

Dashboard estático (HTML + Chart.js) que se genera desde dos Excel de origen y se hospeda
igual que el reporte de Traducciones (GitHub Pages / Azure Static Web Apps) para incrustarse
en el Engagement Site de SharePoint.

## Estructura

    datos/             <- coloca aquí "Budgets anuales.xlsx" y "Seguimiento Budget.xlsx"
    generar.py         <- lee ambos Excel, valida calidad de dato, exporta datos GRANULARES
    plantilla.html      <- plantilla del dashboard (token __DATA__ + motor de cálculo en JS)
    salida/             <- generado: index.html (lo que se despliega) + datos.json
    staticwebapp.config.json  <- headers de Azure (sin usar mientras se hospede en GitHub Pages)
    requirements.txt

`generar.py` **no calcula** KPIs, forecast, riesgos ni insights — solo valida las fuentes,
agrega el budget granular a nivel Cuenta/Subcuenta/mes, y exporta los datos GRANULARES de
ambas hojas. Todo el cálculo (KPIs, comparación FY vs FY, burn rate, proyección de cierre,
ahorro real vs. no ejecutado, riesgos/oportunidades, insights gerenciales, tracker de
ejecución) vive en JavaScript dentro de `plantilla.html`, para que el mismo motor sirva
tanto la vista publicada como la vista previa de un Excel nuevo cargado en el navegador.

## Fuentes de datos

1. **`Budgets anuales.xlsx`** — estático, se actualiza pocas veces al año:
   - Hoja `Budget`: budget aprobado, granular por FY + Cuenta + Sub Cuenta + mes fiscal +
     responsable + monto. Cubre todos los FY presentes (no solo el actual). `generar.py`
     agrega esta hoja a nivel Cuenta/Subcuenta/mes internamente para los KPIs y gráficas
     generales; el detalle granular por responsable se usa para el filtro de Responsable,
     la matriz "Budget personal por responsable" y la "Vista por responsable".
   - (Las hojas `Others` y `datos` del mismo archivo son referencia/staging interna del
     usuario — no se leen.)
2. **`Seguimiento Budget.xlsx`** — se actualiza cada mes con el gasto real:
   - Hoja `Seguimiento`: gasto real transaccional (línea por línea), con FY, Mes - FY,
     Cuenta, Subcuenta, Fecha, Responsable y Gasto (monto numérico).

El cruce entre fuentes se hace por el código de 3 dígitos de la subcuenta (`SC056` en
ambas hojas) y el prefijo de 4 dígitos de la cuenta (`6400:...`, también igual en ambas) —
ver comentarios en `generar.py` si una subcuenta nueva no aparece mapeada. El mes fiscal se
lee del campo `Mes - FY` (formato `NN_Mes`, ej. `01_Jul`) presente en ambas hojas.

**Nombres de responsable**: el filtro de Responsable compara por **nombre exacto** contra el
campo Responsable de cada hoja (Budget y Seguimiento). Se intentó primero resolverlo vía
"qué cuentas tiene asignadas en Budget", pero se descartó: en FY2027 casi todas las
subcuentas (Travel, Meals, Education...) son un pool compartido por 8-11 personas a la vez,
así que ese enfoque sumaba el gasto de todo el equipo en cada persona filtrada. Con
coincidencia exacta de nombre, el filtro fue validado al centavo contra un filtro simple por
nombre en Excel. Para que sea preciso, los nombres deben escribirse igual en ambas hojas.

**Filtro de Área**: la hoja `Budget` trae una columna Área/Tipo de gasto (`ENG - Personal`,
`ENG - Área`, `PCA - Personal`) — el filtro permite marcar varias a la vez. Solo restringe el
**Budget**: `Seguimiento` no tiene esa columna, así que el gasto real no se puede atribuir a
un Área con precisión (el reporte lo deja explícito en "Filtros activos" cuando está activo,
en vez de aproximarlo y arriesgar otro doble conteo).

**Filtro de FY**: es general (vive en el panel de arriba, no dentro de una pestaña), pero solo
controla qué FY analiza la pestaña "Seguimiento" — "Análisis Ejecutivo" siempre muestra
ambos FY a la vez, porque comparar el FY actual contra el anterior es su propósito.

## Funciones del dashboard

- **Pestañas**: "Análisis Ejecutivo" (secciones A–J: resumen, KPIs, comparación FY vs FY,
  variaciones, ahorro real vs. no ejecutado, tendencia, proyección de cierre, riesgos,
  oportunidades, insights gerenciales, plan de acción) y "Seguimiento" (6 gráficas +
  tracker de ejecución tipo Gantt con alertas de color) — mismo link, se cambia con los
  botones de arriba a la derecha.
- **Panel de indicadores y filtros plegable**: el botón "Plegar/Desplegar" oculta los KPIs
  y filtros para dar más espacio a las gráficas.
- **Filtros**: Cuenta, Subcuenta, Responsable y rango de mes fiscal — se combinan y
  recalculan ambas pestañas al vuelo. La pestaña "Seguimiento" además tiene un selector
  propio de FY (actual/anterior) para poder revisar el año ya cerrado con el mismo detalle.
- **Cargar Excel (vista previa)**: dos botones — uno para "Budgets anuales.xlsx" y otro
  para "Seguimiento Budget.xlsx" — para revisar cómo se vería el dashboard con datos nuevos,
  sin publicar nada; solo se ve en tu navegador. El botón "Volver a datos publicados"
  descarta la vista previa.
- **Método de proyección de cierre**: run-rate simple (Actual YTD + promedio mensual de
  meses con dato real × meses fiscales restantes) — documentado como supuesto explícito en
  la sección F del reporte, no es un modelo estacional.
- **Ahorro real vs. no ejecutado**: el reporte separa explícitamente ahorro real (budget ya
  exigible sin gastar), presupuesto no ejecutado (meses futuros, no es ahorro) y ahorro
  potencial proyectado (Budget − Forecast).
- **Matriz "Budget personal por responsable"**: en la pestaña Seguimiento, budget vs. real
  por responsable y mes (barras + tooltip desglosado por cuenta).
- **Vista por responsable**: al final de la pestaña Seguimiento, con su propio filtro de
  responsable (independiente del resto del reporte) — detalle de 4 meses (anterior/actual/
  +2 siguientes) por cuenta y el acumulado del FY, pensado como insumo para correos de
  seguimiento personalizados.
- **Tema claro/oscuro**: botón en el header; la preferencia se guarda en el navegador.

## Contraseña de acceso

El dashboard muestra una pantalla de bloqueo (contraseña) antes de revelar el contenido.
**Importante — límite real de esta protección**: el sitio es un archivo HTML estático, así
que la validación ocurre en el propio navegador del visitante. Cualquier persona con acceso
al repositorio de GitHub (o a las herramientas de desarrollador del navegador) puede ver los
datos igual, contraseña o no. Es una barrera contra quien simplemente recibe el link y lo
abre — **no reemplaza tener el repositorio en privado** si la confidencialidad es un
requisito real (lo cual, en un repo privado, requiere GitHub Pro/Team para poder seguir
usando GitHub Pages).

**Cómo cambiar la contraseña**: en `plantilla.html`, busca la constante `PASSWORD_HASH`
(dentro del bloque `<script>`, sección "acceso con contraseña"). No se guarda la contraseña
en texto plano, sino su hash SHA-256. Para generar el hash de una contraseña nueva:

    python -c "import hashlib; print(hashlib.sha256('tu-contraseña-nueva'.encode()).hexdigest())"

Copia el resultado en `PASSWORD_HASH`, corre `python generar.py`, y haz commit + push. La
forma más simple: pídele a Claude que la cambie por ti y la publique.

## Refresco mensual — publicar para todos (3 pasos)

    1. Reemplaza "Seguimiento Budget.xlsx" en datos/ por la versión actualizada del mes
       (y "Budgets anuales.xlsx" si también cambió, ej. al iniciar un nuevo FY).
    2. python generar.py
    3. git add -A && git commit -m "Actualiza datos a <mes>" && git push

Antes de este paso puedes usar los botones "Cargar Excel" en el propio dashboard para
previsualizar el mes nuevo y confirmar que se ve bien.

El script imprime alertas de calidad del dato (gasto sin línea de budget, reversos,
meses sin carga dentro del rango ya transcurrido) y las muestra dentro del propio reporte.

## Supuestos configurables

Al inicio de `generar.py`:
- `TOLERANCIA_GANTT` — banda (±%) alrededor del budget mensual que se considera "dentro de
  lo esperado" en el tracker de ejecución (hoy 15%).

En `plantilla.html` (motor JS), función `categorias()`:
- Umbral de Burn Rate por categoría para clasificar 🟢/🟡/🔴 (hoy 85%–115%).

## Incrustar en SharePoint

Mismo procedimiento que el reporte de Traducciones: publicar en GitHub Pages (o Azure
Static Web Apps con `staticwebapp.config.json`, ya listo en este repo) y agregar el dominio
a la lista de seguridad de campos HTML del sitio de SharePoint.

## Notas de gobernanza

Es data financiera organizacional (budget y ejecución de gasto real de Compassion Perú).
El dashboard es un snapshot: refleja los Excel con los que se generó, no se conecta en vivo
a los archivos de origen. Para datos en vivo con refresco automático, la vía nativa es Power
BI sobre el mismo SharePoint. Si el repo se publica en GitHub Pages público, la URL queda
visible para cualquiera que la obtenga — evaluar repo privado + GitHub Pro, Cloudflare Pages
+ Cloudflare Access, o Azure Static Web Apps dentro del tenant de Compassion si esto no es
aceptable para datos de presupuesto.
