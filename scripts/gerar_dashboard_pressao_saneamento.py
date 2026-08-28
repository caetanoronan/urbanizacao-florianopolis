from pathlib import Path
import json

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
from shapely.validation import make_valid


ROOT = Path(__file__).resolve().parents[1]
URB_DIR = ROOT / "dados_brutos"
RESULT_DIR = ROOT / "resultados"
DASHBOARD_DIR = ROOT / "dashboard"
OUT_CSV = RESULT_DIR / "pressao_urbana_distritos_saneamento.csv"
OUT_HTML = DASHBOARD_DIR / "dashboard_pressao_saneamento.html"


def load_layer(path):
    layer = gpd.read_file(path, encoding="latin1")
    layer = layer[layer.geometry.notna() & ~layer.geometry.is_empty].copy()
    layer.geometry = layer.geometry.apply(lambda geom: make_valid(geom))
    return layer


def urban_union(layer):
    return unary_union(list(layer.geometry))


def normalize(series):
    minimum = series.min()
    maximum = series.max()
    if pd.isna(minimum) or pd.isna(maximum) or maximum == minimum:
        return pd.Series([0] * len(series), index=series.index)
    return 100 * (series - minimum) / (maximum - minimum)


def fmt_pt(value, digits=2):
    if pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    saneamento = load_layer(URB_DIR / "sau_dist_san.zip")
    bairros = load_layer(URB_DIR / "gvw_bairros" / "gvw_bairros.shp")
    urb_1977 = load_layer(URB_DIR / "mancha_urb1977" / "mancha_urb1977.shp")
    urb_2002 = load_layer(f"zip://{URB_DIR / 'mancha_urb2002.zip'}")
    urb_2024_all = load_layer(URB_DIR / "areas_urbanizadas_2024" / "areas_urbanizadas_2024.shp")
    urb_2024 = urb_2024_all[urb_2024_all["tipo"].eq("Urbanizado")].copy()

    geoms = {
        "1977": urban_union(urb_1977),
        "2002_2003": urban_union(urb_2002),
        "2024": urban_union(urb_2024),
    }

    rows = []
    for _, row in saneamento.iterrows():
        geom = row.geometry
        area_km2 = geom.area / 1_000_000
        u1977 = geom.intersection(geoms["1977"]).area / 1_000_000
        u2002 = geom.intersection(geoms["2002_2003"]).area / 1_000_000
        u2024 = geom.intersection(geoms["2024"]).area / 1_000_000

        pop_estimada = 0
        dom_estima = 0
        bairros_intersectados = []
        for _, bairro in bairros.iterrows():
            inter_area = geom.intersection(bairro.geometry).area
            if inter_area <= 0:
                continue
            share = inter_area / bairro.geometry.area if bairro.geometry.area else 0
            pop_estimada += (bairro.get("pop_estima") or 0) * share
            dom_estima += (bairro.get("dom_estima") or 0) * share
            if share >= 0.15:
                bairros_intersectados.append(str(bairro["nome"]))

        crescimento = u2024 - u1977
        pct_urb_2024 = 100 * u2024 / area_km2 if area_km2 else 0
        rows.append(
            {
                "distrito_saneamento": row["nm_dist_sa"].replace("Continte", "Continente"),
                "area_km2": area_km2,
                "urb1977_km2": u1977,
                "urb2002_2003_km2": u2002,
                "urb2024_km2": u2024,
                "crescimento_1977_2024_km2": crescimento,
                "pct_urb_1977": 100 * u1977 / area_km2 if area_km2 else 0,
                "pct_urb_2002_2003": 100 * u2002 / area_km2 if area_km2 else 0,
                "pct_urb_2024": pct_urb_2024,
                "pop_estimada_aprox": pop_estimada,
                "dom_estima_aprox": dom_estima,
                "densidade_aprox_hab_km2": pop_estimada / area_km2 if area_km2 else 0,
                "crescimento_por_1000_hab_km2": crescimento / pop_estimada * 1000 if pop_estimada else 0,
                "bairros_relevantes": ", ".join(bairros_intersectados[:12]),
            }
        )

    df = pd.DataFrame(rows)
    df["indice_pressao_urbana_saneamento"] = (
        0.45 * normalize(df["crescimento_1977_2024_km2"])
        + 0.35 * normalize(df["pct_urb_2024"])
        + 0.20 * normalize(df["crescimento_por_1000_hab_km2"])
    )
    df = df.sort_values("indice_pressao_urbana_saneamento", ascending=False)
    df.round(4).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")

    records = df.round(4).to_dict(orient="records")
    stats = {
        "distritos": len(df),
        "maior_pressao": df.iloc[0]["distrito_saneamento"],
        "maior_pressao_indice": float(df.iloc[0]["indice_pressao_urbana_saneamento"]),
        "maior_crescimento": df.sort_values("crescimento_1977_2024_km2", ascending=False).iloc[0]["distrito_saneamento"],
        "maior_crescimento_valor": float(df["crescimento_1977_2024_km2"].max()),
        "maior_pct": df.sort_values("pct_urb_2024", ascending=False).iloc[0]["distrito_saneamento"],
        "maior_pct_valor": float(df["pct_urb_2024"].max()),
        "crescimento_total": float(df["crescimento_1977_2024_km2"].sum()),
        "pop_total_aprox": float(df["pop_estimada_aprox"].sum()),
    }
    payload = {"records": records, "stats": stats}

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Pressão urbana e saneamento - Florianópolis</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{
  --bg: #f6f2ec;
  --panel: #ffffff;
  --ink: #10231f;
  --muted: #56665f;
  --grid: #ded8cf;
  --border: #d8cec2;
  --shadow: rgba(72, 58, 44, .10);
  --teal: #2f8077;
  --hero-bg: linear-gradient(135deg, #c8eee8 0%, #c7dcf5 55%, #e7d8f0 100%);
  --metric-a: linear-gradient(135deg, #d8f3ef 0%, #edf8f6 100%);
  --metric-b: linear-gradient(135deg, #d9e9fb 0%, #f0f6ff 100%);
  --metric-c: linear-gradient(135deg, #d7f0fa 0%, #eefaff 100%);
  --metric-d: linear-gradient(135deg, #dff3e3 0%, #f2fbf4 100%);
  --metric-e: linear-gradient(135deg, #e7def7 0%, #f8f3ff 100%);
}}
body[data-theme="dark"] {{
  --bg: #121817;
  --panel: #1b2422;
  --ink: #eef7f3;
  --muted: #b6c6bf;
  --grid: #34423d;
  --border: #3d4d47;
  --shadow: rgba(0, 0, 0, .34);
  --teal: #84d8cc;
  --hero-bg: linear-gradient(135deg, #183a38 0%, #1b3552 58%, #2d2742 100%);
  --metric-a: linear-gradient(135deg, #1d3d3a 0%, #1b2c2a 100%);
  --metric-b: linear-gradient(135deg, #20344d 0%, #1b2530 100%);
  --metric-c: linear-gradient(135deg, #1c3b48 0%, #1a2a31 100%);
  --metric-d: linear-gradient(135deg, #213c2a 0%, #1b2a20 100%);
  --metric-e: linear-gradient(135deg, #302a49 0%, #252033 100%);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--ink); }}
main {{ max-width: 1480px; margin: 0 auto; padding: 34px; }}
header {{
  display: flex; justify-content: space-between; gap: 24px; align-items: end;
  margin-bottom: 22px; background: var(--hero-bg); border: 1px solid var(--border);
  border-radius: 22px; padding: 32px; box-shadow: 0 10px 28px var(--shadow);
}}
h1 {{ margin: 0; font-size: clamp(34px, 3.6vw, 56px); line-height: 1.05; letter-spacing: 0; }}
.lead {{ margin: 12px 0 0; color: var(--muted); font-size: 22px; line-height: 1.45; max-width: 1040px; }}
.header-actions {{ display: flex; align-items: end; gap: 16px; flex-shrink: 0; }}
button, .button {{ font: inherit; }}
.theme-toggle, .button {{
  border: 1px solid var(--border); background: var(--panel); color: var(--ink);
  border-radius: 999px; cursor: pointer; font-weight: 700; padding: 15px 22px;
  white-space: nowrap; font-size: 18px; text-decoration: none; display: inline-block;
}}
.metrics {{ display: grid; grid-template-columns: repeat(5, 1fr); gap: 16px; margin-bottom: 18px; }}
.metric {{
  padding: 22px; min-height: 156px; border: 1px solid var(--border);
  border-radius: 12px; box-shadow: 0 10px 28px var(--shadow);
}}
.metric:nth-child(5n + 1) {{ background: var(--metric-a); }}
.metric:nth-child(5n + 2) {{ background: var(--metric-b); }}
.metric:nth-child(5n + 3) {{ background: var(--metric-c); }}
.metric:nth-child(5n + 4) {{ background: var(--metric-d); }}
.metric:nth-child(5n + 5) {{ background: var(--metric-e); }}
.metric span {{ display: block; color: var(--muted); font-size: 16px; margin-bottom: 10px; }}
.metric strong {{ display: block; font-size: 30px; line-height: 1.08; }}
.metric small {{ display: block; color: var(--muted); font-size: 15px; line-height: 1.35; margin-top: 12px; }}
.tabs {{ display: grid; gap: 12px; }}
.tab-list {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 7px; padding: 8px 0 12px; }}
.tab-button {{
  border: 1px solid var(--border); background: var(--panel); padding: 10px 14px;
  border-radius: 999px; cursor: pointer; font-weight: 700; color: var(--ink);
  line-height: 1.2; text-align: center; font-size: 15px; box-shadow: 0 6px 16px var(--shadow);
}}
.tab-button:nth-child(5n + 1) {{ background: var(--metric-a); }}
.tab-button:nth-child(5n + 2) {{ background: var(--metric-b); }}
.tab-button:nth-child(5n + 3) {{ background: var(--metric-c); }}
.tab-button:nth-child(5n + 4) {{ background: var(--metric-d); }}
.tab-button:nth-child(5n + 5) {{ background: var(--metric-e); }}
.tab-button.active {{ background: var(--teal); color: #fff; border-color: var(--teal); }}
body[data-theme="dark"] .tab-button.active {{ color: #10231f; }}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}
.panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 10px 28px var(--shadow); overflow: hidden; }}
.panel-head {{
  margin: 20px 24px 0; padding: 18px; background: rgba(242, 235, 140, .36);
  border: 1px solid rgba(166, 153, 73, .18); border-radius: 12px;
}}
.panel-title {{ margin: 0; font-size: 34px; line-height: 1.12; letter-spacing: 0; }}
.panel-note {{ margin: 10px 0 0; color: var(--muted); line-height: 1.45; font-size: 18px; }}
.plot-wrap {{
  margin: 20px 24px 24px; padding: 18px; background: rgba(242, 235, 140, .36);
  border: 1px solid rgba(166, 153, 73, .18); border-radius: 12px;
}}
.chart {{ width: 100%; min-height: 640px; }}
.info-grid, .formula-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.info-card, .formula, .footer-card {{
  padding: 20px; border: 1px solid var(--border); border-radius: 8px;
  box-shadow: 0 8px 22px var(--shadow); background: var(--metric-a);
}}
.info-card:nth-child(5n + 2), .formula:nth-child(5n + 2), .footer-card:nth-child(5n + 2) {{ background: var(--metric-b); }}
.info-card:nth-child(5n + 3), .formula:nth-child(5n + 3), .footer-card:nth-child(5n + 3) {{ background: var(--metric-c); }}
.info-card:nth-child(5n + 4), .formula:nth-child(5n + 4), .footer-card:nth-child(5n + 4) {{ background: var(--metric-d); }}
.info-card:nth-child(5n + 5), .formula:nth-child(5n + 5), .footer-card:nth-child(5n + 5) {{ background: var(--metric-e); }}
.info-card h3, .formula strong, .footer-card strong {{ display: block; margin: 0 0 10px; color: var(--ink); font-size: 21px; line-height: 1.16; }}
.info-card p, .info-card li, .formula code, .footer-card p {{
  color: var(--muted); font-size: 16px; line-height: 1.46;
}}
.info-card p, .footer-card p {{ margin: 0; }}
.info-card ul {{ margin: 0; padding-left: 20px; }}
.formula code {{ display: block; white-space: normal; overflow-wrap: anywhere; font-family: Consolas, Monaco, monospace; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
th, td {{ padding: 11px 12px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ color: var(--ink); background: var(--panel); position: sticky; top: 0; }}
td {{ color: var(--muted); }}
tbody tr:nth-child(5n + 1) {{ background: rgba(216, 243, 239, .42); }}
tbody tr:nth-child(5n + 2) {{ background: rgba(217, 233, 251, .42); }}
tbody tr:nth-child(5n + 3) {{ background: rgba(215, 240, 250, .42); }}
tbody tr:nth-child(5n + 4) {{ background: rgba(223, 243, 227, .42); }}
tbody tr:nth-child(5n + 5) {{ background: rgba(231, 222, 247, .42); }}
.footer {{ margin: 22px 0 0; padding: 24px; background: var(--panel); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 10px 28px var(--shadow); }}
.footer h2 {{ margin: 0 0 16px; color: var(--ink); font-size: 28px; line-height: 1.12; }}
.footer-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; }}
@media (max-width: 980px) {{
  main {{ padding: 14px; }}
  header {{ flex-direction: column; align-items: stretch; }}
  .header-actions {{ flex-direction: column; align-items: stretch; }}
  .metrics, .tab-list, .info-grid, .formula-grid, .footer-grid {{ grid-template-columns: 1fr; }}
  .chart {{ min-height: 520px; }}
}}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Pressão urbana e saneamento</h1>
      <p class="lead">Florianópolis - expansão da mancha urbana lida pelos distritos de saneamento Centro, Leste, Sul, Continente e Norte.</p>
    </div>
    <div class="header-actions">
      <a class="button" href="../index.html">Voltar ao índice</a>
      <button class="theme-toggle" id="theme-toggle" type="button">Modo escuro</button>
    </div>
  </header>

  <section class="metrics">
    <div class="metric"><span>Distritos avaliados</span><strong>{stats["distritos"]}</strong><small>Unidades operacionais de saneamento.</small></div>
    <div class="metric"><span>Maior pressão</span><strong>{stats["maior_pressao"]}</strong><small>Índice {fmt_pt(stats["maior_pressao_indice"])} em escala 0-100.</small></div>
    <div class="metric"><span>Maior crescimento</span><strong>{stats["maior_crescimento"]}</strong><small>{fmt_pt(stats["maior_crescimento_valor"])} km² entre 1977 e 2024.</small></div>
    <div class="metric"><span>Mais urbanizado</span><strong>{stats["maior_pct"]}</strong><small>{fmt_pt(stats["maior_pct_valor"])}% urbanizado em 2024.</small></div>
    <div class="metric"><span>População aproximada</span><strong>{fmt_pt(stats["pop_total_aprox"], 0)}</strong><small>Estimativa por interseção com bairros.</small></div>
  </section>

  <section class="tabs">
    <div class="tab-list" role="tablist">
      <button class="tab-button active" type="button" data-tab="tab-intro">História</button>
      <button class="tab-button" type="button" data-tab="tab-evolucao">Evolução urbana</button>
      <button class="tab-button" type="button" data-tab="tab-pressao">Índice de pressão</button>
      <button class="tab-button" type="button" data-tab="tab-percentual">Percentual urbanizado</button>
      <button class="tab-button" type="button" data-tab="tab-metodologia">Metodologia</button>
      <button class="tab-button" type="button" data-tab="tab-glossario">Glossário</button>
      <button class="tab-button" type="button" data-tab="tab-tabela">Tabela síntese</button>
    </div>

    <div id="tab-intro" class="tab-panel active">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">A terceira história do produto</h2><p class="panel-note">Depois da expansão por bairros e da comparação socio-urbana, esta leitura observa a pressão potencial sobre distritos de saneamento.</p></div>
      <div class="plot-wrap"><div class="info-grid">
        <article class="info-card"><h3>O que muda nesta leitura</h3><p>A unidade de análise deixa de ser o bairro e passa a ser o distrito de saneamento. Isso aproxima a expansão urbana da infraestrutura que precisa atender a cidade.</p></article>
        <article class="info-card"><h3>O que a comparação revela</h3><p>Norte e Sul concentram o maior crescimento absoluto. Centro e Continente aparecem como áreas consolidadas, com percentual urbanizado muito elevado.</p></article>
        <article class="info-card"><h3>Cuidado interpretativo</h3><p>O índice de pressão é exploratório. Ele não mede capacidade real da rede, mas aponta onde a expansão urbana pode dialogar com planejamento de infraestrutura.</p></article>
      </div></div></div>
    </div>

    <div id="tab-evolucao" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Evolução urbana por distrito</h2><p class="panel-note">Compara a área urbanizada em 1977, 2002/2003 e 2024 dentro de cada distrito de saneamento.</p></div>
      <div class="plot-wrap"><div id="evolucaoChart" class="chart"></div></div></div>
    </div>

    <div id="tab-pressao" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Índice de pressão urbana sobre saneamento</h2><p class="panel-note">Síntese em escala 0-100 combinando crescimento urbano absoluto, percentual urbanizado em 2024 e crescimento por mil habitantes.</p></div>
      <div class="plot-wrap"><div id="pressaoChart" class="chart"></div></div></div>
    </div>

    <div id="tab-percentual" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Percentual urbanizado por distrito</h2><p class="panel-note">Mostra quanto da área de cada distrito já estava ocupada pela mancha urbana em cada recorte temporal.</p></div>
      <div class="plot-wrap"><div id="percentualChart" class="chart"></div></div></div>
    </div>

    <div id="tab-metodologia" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Metodologia e estatísticas</h2><p class="panel-note">Fórmulas usadas para transformar os distritos de saneamento em indicadores comparáveis.</p></div>
      <div class="plot-wrap"><div class="formula-grid">
        <div class="formula"><strong>Área urbanizada por distrito</strong><code>Aurb_dist(ano) = área(interseção distrito ∩ mancha urbana ano) / 1.000.000</code></div>
        <div class="formula"><strong>Crescimento absoluto</strong><code>ΔA = Aurb_dist(2024) - Aurb_dist(1977)</code></div>
        <div class="formula"><strong>Percentual urbanizado</strong><code>%urb = (Aurb_dist / área_total_distrito) × 100</code></div>
        <div class="formula"><strong>População aproximada</strong><code>Pop_dist = Σ(pop_bairro × área_interseção_bairro_distrito / área_bairro)</code></div>
        <div class="formula"><strong>Crescimento por mil habitantes</strong><code>C1000 = (ΔA / Pop_dist) × 1.000</code></div>
        <div class="formula"><strong>Índice de pressão</strong><code>IPUS = 0,45×norm(ΔA) + 0,35×norm(%urb2024) + 0,20×norm(C1000)</code></div>
      </div></div></div>
    </div>

    <div id="tab-glossario" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Glossário</h2><p class="panel-note">Termos usados na leitura de pressão urbana sobre saneamento.</p></div>
      <div class="plot-wrap"><div class="info-grid">
        <article class="info-card"><h3>Distrito de saneamento</h3><p>Unidade territorial associada ao planejamento e operação de serviços de saneamento.</p></article>
        <article class="info-card"><h3>Pressão urbana</h3><p>Síntese da intensidade de crescimento urbano e do grau de ocupação de uma área.</p></article>
        <article class="info-card"><h3>Área consolidada</h3><p>Distrito com percentual urbanizado alto, indicando menor espaço físico para expansão horizontal.</p></article>
        <article class="info-card"><h3>Expansão recente</h3><p>Aumento expressivo da mancha urbana entre os recortes históricos analisados.</p></article>
        <article class="info-card"><h3>Normalização</h3><p>Transformação dos indicadores para escala comum de 0 a 100 antes de combiná-los.</p></article>
        <article class="info-card"><h3>Estimativa por interseção</h3><p>Distribuição aproximada de população e domicílios por proporção de área dos bairros dentro de cada distrito.</p></article>
      </div></div></div>
    </div>

    <div id="tab-tabela" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Tabela síntese por distrito</h2><p class="panel-note">Tabela final com crescimento, percentual urbanizado, população aproximada e índice de pressão.</p></div>
      <div class="plot-wrap table-wrap"><table id="summaryTable"></table></div></div>
    </div>
  </section>

  <footer class="footer">
    <h2>Referências e processamento</h2>
    <div class="footer-grid">
      <div class="footer-card"><strong>Autoria</strong><p>Caetano Ronan - UFSC.</p></div>
      <div class="footer-card"><strong>Fontes</strong><p>`sau_dist_san.zip`, manchas urbanas de 1977, 2002/2003 e 2024, e camada `gvw_bairros`.</p></div>
      <div class="footer-card"><strong>Processamento</strong><p>SIRGAS 2000 / UTM zona 22S, EPSG:31982. Interseções espaciais, áreas em km², normalização e índice composto.</p></div>
      <div class="footer-card"><strong>Leitura crítica</strong><p>O índice indica pressão potencial. Para diagnóstico operacional, seria necessário incorporar rede, cobertura e capacidade do sistema.</p></div>
    </div>
  </footer>
</main>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
const fmt = new Intl.NumberFormat('pt-BR', {{ maximumFractionDigits: 2 }});
const cssVar = name => getComputedStyle(document.body).getPropertyValue(name).trim();
const pastel = ['#94aee6', '#88c9df', '#75b7a8', '#b6d98b', '#e8cf75'];
const chartConfig = name => ({{
  responsive: true,
  displayModeBar: true,
  displaylogo: false,
  toImageButtonOptions: {{ format: 'png', filename: name, height: 900, width: 1400, scale: 2 }}
}});
const layout = extra => ({{
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ family: 'Arial, sans-serif', color: cssVar('--ink') }},
  margin: {{ l: 150, r: 80, t: 48, b: 86 }},
  ...extra
}});
function orderedRows() {{
  return [...data.records].sort((a, b) => b.indice_pressao_urbana_saneamento - a.indice_pressao_urbana_saneamento);
}}
function renderCharts() {{
  const rows = orderedRows().reverse();
  const districts = rows.map(d => d.distrito_saneamento);
  Plotly.newPlot('evolucaoChart', [
    {{ type: 'bar', name: '1977', x: rows.map(d => d.urb1977_km2), y: districts, orientation: 'h', marker: {{ color: '#e8cf75' }}, text: rows.map(d => `${{fmt.format(d.urb1977_km2)}} km²`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2002/2003', x: rows.map(d => d.urb2002_2003_km2), y: districts, orientation: 'h', marker: {{ color: '#88c9df' }}, text: rows.map(d => `${{fmt.format(d.urb2002_2003_km2)}} km²`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2024', x: rows.map(d => d.urb2024_km2), y: districts, orientation: 'h', marker: {{ color: '#75b7a8' }}, text: rows.map(d => `${{fmt.format(d.urb2024_km2)}} km²`), textposition: 'outside', cliponaxis: false }}
  ], layout({{ barmode: 'group', xaxis: {{ title: 'Área urbanizada (km²)', gridcolor: cssVar('--grid') }}, yaxis: {{ automargin: true }}, legend: {{ orientation: 'h', y: 1.14 }} }}), chartConfig('evolucao_urbana_distritos_saneamento'));

  Plotly.newPlot('pressaoChart', [{{
    type: 'bar',
    x: rows.map(d => d.indice_pressao_urbana_saneamento),
    y: districts,
    orientation: 'h',
    marker: {{ color: rows.map((d, i) => pastel[i % pastel.length]) }},
    text: rows.map(d => `${{fmt.format(d.indice_pressao_urbana_saneamento)}}`),
    textposition: 'outside',
    cliponaxis: false,
    customdata: rows.map(d => [d.crescimento_1977_2024_km2, d.pct_urb_2024, d.crescimento_por_1000_hab_km2]),
    hovertemplate: '<b>%{{y}}</b><br>Índice: %{{x:.2f}}<br>Crescimento: %{{customdata[0]:.2f}} km²<br>% urbano 2024: %{{customdata[1]:.1f}}%<br>km²/mil hab.: %{{customdata[2]:.3f}}<extra></extra>'
  }}], layout({{ xaxis: {{ title: 'Índice de pressão urbana sobre saneamento (0-100)', gridcolor: cssVar('--grid'), range: [0, 112] }}, yaxis: {{ automargin: true }} }}), chartConfig('indice_pressao_urbana_saneamento'));

  Plotly.newPlot('percentualChart', [
    {{ type: 'bar', name: '1977', x: districts, y: rows.map(d => d.pct_urb_1977), marker: {{ color: '#e8cf75' }}, text: rows.map(d => `${{fmt.format(d.pct_urb_1977)}}%`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2002/2003', x: districts, y: rows.map(d => d.pct_urb_2002_2003), marker: {{ color: '#88c9df' }}, text: rows.map(d => `${{fmt.format(d.pct_urb_2002_2003)}}%`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2024', x: districts, y: rows.map(d => d.pct_urb_2024), marker: {{ color: '#75b7a8' }}, text: rows.map(d => `${{fmt.format(d.pct_urb_2024)}}%`), textposition: 'outside', cliponaxis: false }}
  ], layout({{ margin: {{ l: 80, r: 50, t: 48, b: 110 }}, xaxis: {{ tickangle: -12, gridcolor: cssVar('--grid') }}, yaxis: {{ title: '% urbanizado', gridcolor: cssVar('--grid'), range: [0, 112] }}, legend: {{ orientation: 'h', y: 1.14 }} }}), chartConfig('percentual_urbanizado_distritos_saneamento'));
}}
function renderTable() {{
  const head = ['Distrito', 'Cresc. km²', '% urb. 2024', 'Pop. aprox.', 'Domicílios aprox.', 'Índice', 'Bairros relevantes'];
  const body = orderedRows().map(d => `<tr>
    <td>${{d.distrito_saneamento}}</td>
    <td>${{fmt.format(d.crescimento_1977_2024_km2)}}</td>
    <td>${{fmt.format(d.pct_urb_2024)}}%</td>
    <td>${{fmt.format(d.pop_estimada_aprox)}}</td>
    <td>${{fmt.format(d.dom_estima_aprox)}}</td>
    <td>${{fmt.format(d.indice_pressao_urbana_saneamento)}}</td>
    <td>${{d.bairros_relevantes || '-'}}</td>
  </tr>`).join('');
  document.getElementById('summaryTable').innerHTML = `<thead><tr>${{head.map(h => `<th>${{h}}</th>`).join('')}}</tr></thead><tbody>${{body}}</tbody>`;
}}
function applyTheme(theme) {{
  document.body.dataset.theme = theme;
  document.getElementById('theme-toggle').textContent = theme === 'dark' ? 'Modo claro' : 'Modo escuro';
  localStorage.setItem('urbanizacao-saneamento-theme-floripa', theme);
  window.setTimeout(renderCharts, 40);
}}
document.querySelectorAll('.tab-button').forEach(button => {{
  button.addEventListener('click', () => {{
    const target = button.dataset.tab;
    document.querySelectorAll('.tab-button').forEach(item => item.classList.toggle('active', item === button));
    document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === target));
    window.setTimeout(() => ['evolucaoChart', 'pressaoChart', 'percentualChart'].forEach(id => {{
      const el = document.getElementById(id);
      if (el) Plotly.Plots.resize(el);
    }}), 80);
  }});
}});
document.getElementById('theme-toggle').addEventListener('click', () => {{
  applyTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark');
}});
renderTable();
applyTheme(localStorage.getItem('urbanizacao-saneamento-theme-floripa') || 'light');
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(OUT_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
