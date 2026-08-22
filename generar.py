#!/usr/bin/env python3
"""
Generador del Reporte Budget Engagement · Compassion Perú.

Flujo: lee "Budgets anuales.xlsx" (Budgets general + Budget personales) y
"Seguimiento Budget.xlsx" (Seguimiento), valida calidad de dato, y exporta los
datos GRANULARES de las tres fuentes -> plantilla.html -> salida/index.html.

Todo el cálculo (KPIs, comparación FY vs FY, proyección de cierre, burn rate,
riesgos/oportunidades, insights) vive en JavaScript dentro de plantilla.html,
para que el mismo motor sirva tanto la vista publicada como la vista previa de
un Excel nuevo cargado en el navegador.

Uso:
    python generar.py                                  # usa los Excel más recientes en datos/
    python generar.py "datos/Budgets anuales.xlsx" "datos/Seguimiento Budget.xlsx"
"""
import sys, re, json, glob, datetime as dt
import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# ─────────────────────────── CONFIGURACIÓN ───────────────────────────
TOLERANCIA_GANTT = 0.15   # ±15% del budget del mes = "dentro de lo esperado" (verde)
MESES_FISCALES = ['Jul','Ago','Set','Oct','Nov','Dic','Ene','Feb','Mar','Abr','May','Jun']
MESES_GENERAL_COLS = ['Jul','Aug','Sep','Oct','Nov','Dec','Jan','Feb','Mar','Apr','May','Jun']
MES_ING_A_IDX = {m: i for i, m in enumerate(
    ['July','August','September','October','November','December',
     'January','February','March','April','May','June'])}

# ─────────────────────────── UTILIDADES ───────────────────────────
def cod3(texto):
    """Extrae el código de 3 dígitos de una Subcuenta/Spend Category ('6400-056 - ...' o 'SC056 - ...')."""
    if not isinstance(texto, str):
        return None
    cabeza = texto.split(' - ')[0]  # '6400-056' o 'SC056'
    m = re.search(r'(\d{3})$', cabeza)
    return m.group(1) if m else None

def cod4(texto):
    """Extrae el prefijo de 4 dígitos de una Cuenta/Ledger Account ('6400:Communications Expense...')."""
    if not isinstance(texto, str):
        return None
    m = re.match(r'^(\d{4})', texto)
    return m.group(1) if m else None

def label_subcuenta(texto):
    if not isinstance(texto, str):
        return texto
    partes = texto.split(' - ', 1)
    return partes[1] if len(partes) > 1 else texto

def label_cuenta(texto):
    if not isinstance(texto, str):
        return texto
    partes = texto.split(':', 1)
    return partes[1] if len(partes) > 1 else texto

def parse_monto(s):
    """'S/ 1,724.50 ' -> 1724.5 ; '-S/ 95.70 ' -> -95.7"""
    if s is None:
        return 0.0
    if isinstance(s, (int, float)):
        return float(s)
    limpio = re.sub(r'[^0-9.\-]', '', str(s))
    if limpio in ('', '-', '.'):
        return 0.0
    try:
        return float(limpio)
    except ValueError:
        return 0.0

def fy_de_fecha(mes_calendario, anio_calendario):
    """FY Jul-Jun: meses Jul-Dic pertenecen al FY siguiente."""
    return anio_calendario + 1 if mes_calendario >= 7 else anio_calendario

# ─────────────────────────── CARGA: BUDGETS ANUALES ───────────────────────────
def cargar_budget_general(path):
    df = pd.read_excel(path, sheet_name='Budgets general')
    req = ['FY', 'Entregable / Actividad', 'Descripción', 'Cuenta', 'Subcuenta', 'Total'] + MESES_GENERAL_COLS
    faltan = [c for c in req if c not in df.columns]
    if faltan:
        raise SystemExit(f"❌ Faltan columnas en 'Budgets general': {faltan}")
    filas = []
    for _, r in df.iterrows():
        meses = [parse_monto(r[c]) for c in MESES_GENERAL_COLS]
        filas.append(dict(
            fy=int(r['FY']), entregable=str(r['Entregable / Actividad']),
            descripcion=str(r['Descripción']) if pd.notna(r['Descripción']) else '',
            cuenta=r['Cuenta'], cuentaCod=cod4(r['Cuenta']), cuentaLabel=label_cuenta(r['Cuenta']),
            subcuenta=r['Subcuenta'], cod=cod3(r['Subcuenta']), subcuentaLabel=label_subcuenta(r['Subcuenta']),
            meses=meses, total=parse_monto(r['Total']) if pd.notna(r['Total']) else sum(meses)))
    return filas

def cargar_budget_personal(path):
    df = pd.read_excel(path, sheet_name='Budget personales')
    req = ['FY', 'Tipo de gasto', 'Descripción', 'Sub Cuenta', 'Mes - FY', 'Responsable', 'Monto']
    faltan = [c for c in req if c not in df.columns]
    if faltan:
        raise SystemExit(f"❌ Faltan columnas en 'Budget personales': {faltan}")
    filas = []
    for _, r in df.iterrows():
        mesfy = str(r['Mes - FY'])
        m = re.match(r'^(\d{1,2})_', mesfy)
        mes_idx = int(m.group(1)) - 1 if m else None
        filas.append(dict(
            fy=int(r['FY']), tipoGasto=r['Tipo de gasto'],
            descripcion=str(r['Descripción']) if pd.notna(r['Descripción']) else '',
            subcuenta=r['Sub Cuenta'], cod=cod3(r['Sub Cuenta']), subcuentaLabel=label_subcuenta(r['Sub Cuenta']),
            mesIdx=mes_idx, responsable=r['Responsable'] if pd.notna(r['Responsable']) else 'Sin asignar',
            monto=parse_monto(r['Monto'])))
    return filas

# ─────────────────────────── CARGA: SEGUIMIENTO (gasto real) ───────────────────────────
def cargar_actual(path):
    df = pd.read_excel(path, sheet_name='Seguimiento')
    req = ['FY', 'Ledger Account', 'Spend Category as Worktag', 'Line Memo', 'Total',
           'Year', 'Month', 'Fecha', 'Responsable']
    faltan = [c for c in req if c not in df.columns]
    if faltan:
        raise SystemExit(f"❌ Faltan columnas en 'Seguimiento': {faltan}")
    filas, discrepancias = [], 0
    for _, r in df.iterrows():
        monto = parse_monto(r['Total'])
        if 'PRO' in df.columns and pd.notna(r['PRO']) and abs(float(r['PRO']) - monto) > 0.01:
            discrepancias += 1
        mes_idx = MES_ING_A_IDX.get(str(r['Month']))
        filas.append(dict(
            fy=int(r['FY']), cuenta=r['Ledger Account'], cuentaCod=cod4(r['Ledger Account']),
            cuentaLabel=label_cuenta(r['Ledger Account']),
            subcuenta=r['Spend Category as Worktag'], cod=cod3(r['Spend Category as Worktag']),
            subcuentaLabel=label_subcuenta(r['Spend Category as Worktag']),
            mesIdx=mes_idx, mesNombre=r['Month'], fecha=str(r['Fecha']),
            responsable=r['Responsable'] if pd.notna(r['Responsable']) else 'Sin asignar',
            monto=monto, memo=str(r['Line Memo']) if pd.notna(r['Line Memo']) else ''))
    return filas, discrepancias

# ─────────────────────────── VALIDACIÓN DE CALIDAD ───────────────────────────
def validar(bg, actual, discrepancias_monto):
    alertas = []
    claves_budget = {(f['fy'], f['cuentaCod'], f['cod']) for f in bg}
    no_presupuestado = {}
    for a in actual:
        k = (a['fy'], a['cuentaCod'], a['cod'])
        if k not in claves_budget:
            kk = (a['fy'], a['cuentaLabel'], a['subcuentaLabel'])
            no_presupuestado[kk] = no_presupuestado.get(kk, 0) + a['monto']
    for (fy, cuenta, sub), monto in no_presupuestado.items():
        alertas.append(f"FY{fy}: gasto real de S/ {monto:,.2f} en '{cuenta} / {sub}' no tiene línea "
                        f"correspondiente en 'Budgets general' — revisar si falta mapear la subcuenta.")

    negativos = [a for a in actual if a['monto'] < 0]
    if negativos:
        alertas.append(f"{len(negativos)} filas de 'Seguimiento' tienen monto negativo (reversos/correcciones), "
                        f"por S/ {sum(a['monto'] for a in negativos):,.2f} en total — ya incluidas en el gasto neto.")

    if discrepancias_monto:
        alertas.append(f"{discrepancias_monto} filas de 'Seguimiento' tienen la columna numérica de monto "
                        f"distinta al texto de 'Total' — se usó el texto de 'Total' como fuente de verdad.")

    # meses sin ninguna fila de actual dentro del FY, comparado contra el mes fiscal de hoy
    hoy = dt.date.today()
    fy_hoy = fy_de_fecha(hoy.month, hoy.year)
    idx_hoy = (hoy.month - 7) if hoy.month >= 7 else (hoy.month + 5)
    meses_con_dato = {}
    for a in actual:
        meses_con_dato.setdefault(a['fy'], set()).add(a['mesIdx'])
    for fy in sorted({f['fy'] for f in bg}):
        limite = idx_hoy if fy == fy_hoy else 12
        cubiertos = meses_con_dato.get(fy, set())
        faltantes = [MESES_FISCALES[i] for i in range(limite) if i not in cubiertos]
        if faltantes:
            alertas.append(f"FY{fy}: sin ninguna fila de gasto real cargada para {', '.join(faltantes)} "
                            f"(dentro del rango ya transcurrido) — puede ser atraso de carga del Excel de "
                            f"seguimiento, no necesariamente ahorro real.")
    return alertas, dict(fyHoy=fy_hoy, idxHoy=idx_hoy, mesesConDato={str(k): sorted(v) for k, v in meses_con_dato.items()})

# ─────────────────────────── RENDER ───────────────────────────
def construir_meta(bg, bp, actual, contexto_fecha):
    fys = sorted({f['fy'] for f in bg})
    fy_actual = max(fys)
    fy_anterior = min(fys) if len(fys) > 1 else fy_actual - 1
    ultimo_mes = {}
    for a in actual:
        cur = ultimo_mes.get(a['fy'], -1)
        if a['mesIdx'] is not None and a['mesIdx'] > cur:
            ultimo_mes[a['fy']] = a['mesIdx']
    cuentas = sorted({(f['cuentaCod'], f['cuentaLabel']) for f in bg if f['cuentaCod']})
    subcuentas = sorted({(f['cod'], f['subcuentaLabel']) for f in bg if f['cod']})
    responsables = sorted({p['responsable'] for p in bp} | {a['responsable'] for a in actual})
    return dict(
        fyAnterior=fy_anterior, fyActual=fy_actual,
        mesesFiscales=MESES_FISCALES,
        moneda='S/', toleranciaGantt=TOLERANCIA_GANTT,
        actualizado=dt.date.today().strftime('%d %b %Y'),
        ultimoMesConDato={str(k): v for k, v in ultimo_mes.items()},
        cuentas=[{'cod': c, 'label': l} for c, l in cuentas],
        subcuentas=[{'cod': c, 'label': l} for c, l in subcuentas],
        responsables=responsables,
        contexto=contexto_fecha)

def render(D):
    tpl = open('plantilla.html', encoding='utf-8').read()
    html = tpl.replace('__DATA__', json.dumps(D, ensure_ascii=False))
    import os; os.makedirs('salida', exist_ok=True)
    open('salida/index.html', 'w', encoding='utf-8').write(html)
    json.dump(D, open('salida/datos.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('-')]
    if len(args) >= 2:
        p_anuales, p_seg = args[0], args[1]
    else:
        cands_a = sorted(glob.glob('datos/Budgets*anuales*.xlsx'), key=lambda p: __import__('os').path.getmtime(p))
        cands_s = sorted(glob.glob('datos/Seguimiento*.xlsx'), key=lambda p: __import__('os').path.getmtime(p))
        if not cands_a or not cands_s:
            raise SystemExit("❌ No se encontraron 'Budgets anuales*.xlsx' y/o 'Seguimiento*.xlsx' en datos/.")
        p_anuales, p_seg = cands_a[-1], cands_s[-1]

    print(f"📄 Budgets anuales: {p_anuales}")
    print(f"📄 Seguimiento:     {p_seg}")

    bg = cargar_budget_general(p_anuales)
    bp = cargar_budget_personal(p_anuales)
    actual, discrepancias = cargar_actual(p_seg)
    alertas, contexto_fecha = validar(bg, actual, discrepancias)
    meta = construir_meta(bg, bp, actual, contexto_fecha)

    D = dict(budgetGeneral=bg, budgetPersonal=bp, actual=actual, meta=meta, alertas=alertas)
    render(D)

    tot_budget = {}
    tot_actual = {}
    for f in bg: tot_budget[f['fy']] = tot_budget.get(f['fy'], 0) + f['total']
    for a in actual: tot_actual[a['fy']] = tot_actual.get(a['fy'], 0) + a['monto']
    print(f"✅ salida/index.html generado — {len(bg)} líneas de budget general, "
          f"{len(bp)} de budget personal, {len(actual)} de gasto real.")
    for fy in sorted(tot_budget):
        print(f"   FY{fy}: budget S/ {tot_budget[fy]:,.2f}  ·  actual S/ {tot_actual.get(fy, 0):,.2f}")
    if alertas:
        print("⚠  Alertas de calidad del dato:")
        for a in alertas: print("   -", a)

if __name__ == '__main__':
    main()
