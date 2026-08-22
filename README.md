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

`generar.py` **no calcula** KPIs, forecast, riesgos ni insights — solo valida las fuentes y
exporta los datos granulares de las tres hojas usadas. Todo el cálculo (KPIs, comparación
FY vs FY, burn rate, proyección de cierre, ahorro real vs. no ejecutado, riesgos/oportunidades,
insights gerenciales, tracker de ejecución) vive en JavaScript dentro de `plantilla.html`,
para que el mismo motor sirva tanto la vista publicada como la vista previa de un Excel nuevo
cargado en el navegador.

## Fuentes de datos

1. **`Budgets anuales.xlsx`** — estático, se actualiza pocas veces al año:
   - Hoja `Budgets general`: budget aprobado por Cuenta/Subcuenta/mes, para el FY anterior
     (cerrado) y el FY actual.
   - Hoja `Budget personales`: asignación del budget del FY actual a responsables, por
     subcuenta y mes fiscal.
2. **`Seguimiento Budget.xlsx`** — se actualiza cada mes con el gasto real:
   - Hoja `Seguimiento`: gasto real transaccional (línea por línea), con FY, cuenta,
     subcuenta ("Spend Category as Worktag"), mes, responsable y monto.

El cruce entre fuentes se hace por el código de 3 dígitos de la subcuenta (`6400-056` ↔
`SC056`) y el prefijo de 4 dígitos de la cuenta (`6400:...`) — ver comentarios en
`generar.py` si una subcuenta nueva no aparece mapeada.

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
