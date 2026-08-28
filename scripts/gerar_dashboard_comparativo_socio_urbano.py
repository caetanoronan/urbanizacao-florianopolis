from pathlib import Path
import json

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "resultados"
DASHBOARD_DIR = ROOT / "dashboard"
BAIRROS_PATH = ROOT / "dados_brutos" / "gvw_bairros" / "gvw_bairros.shp"
URB_BAIRROS_CSV = RESULT_DIR / "urbanizacao_por_bairro_1977_2002_2024.csv"
OUT_CSV = RESULT_DIR / "comparativo_socio_urbano_bairros.csv"
OUT_HTML = DASHBOARD_DIR / "dashboard_comparativo_socio_urbano.html"


def fmt_pt(value, digits=2):
    if pd.isna(value):
        return "-"
    return f"{value:,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def corr(df, x, y):
    clean = df[[x, y]].dropna()
    if len(clean) < 3:
        return None
    return float(clean[x].corr(clean[y]))


def main():
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)

    urbanizacao = pd.read_csv(URB_BAIRROS_CSV)
    bairros = gpd.read_file(BAIRROS_PATH, encoding="latin1")
    socio = bairros[
        ["nome", "dom_estima", "densidade0", "media_mora", "distrito_a", "legislacao"]
    ].rename(columns={"nome": "bairro"})

    df = urbanizacao.merge(socio, on="bairro", how="left")
    df["crescimento_por_1000_hab_km2"] = (
        df["crescimento_1977_2024_km2"] / df["pop_estimada"].replace(0, pd.NA) * 1000
    )
    df["area_urb_2024_por_1000_hab_km2"] = (
        df["urb2024_km2"] / df["pop_estimada"].replace(0, pd.NA) * 1000
    )
    df["hab_por_km2_urb_2024"] = df["pop_estimada"] / df["urb2024_km2"].replace(0, pd.NA)
    df["dom_por_km2_urb_2024"] = df["dom_estima"] / df["urb2024_km2"].replace(0, pd.NA)
    df["crescimento_relativo_1977_2024_pct"] = (
        df["crescimento_1977_2024_km2"] / df["urb1977_km2"].replace(0, pd.NA) * 100
    )

    med_growth = df["crescimento_1977_2024_km2"].median()
    med_density = df["densidade_pop_bairro"].median()

    def perfil(row):
        high_growth = row["crescimento_1977_2024_km2"] >= med_growth
        high_density = row["densidade_pop_bairro"] >= med_density
        if high_growth and high_density:
            return "Alta expansão e alta densidade"
        if high_growth and not high_density:
            return "Alta expansão e baixa densidade"
        if not high_growth and high_density:
            return "Baixa expansão e alta densidade"
        return "Baixa expansão e baixa densidade"

    df["perfil_socio_urbano"] = df.apply(perfil, axis=1)

    df.round(4).sort_values("crescimento_1977_2024_km2", ascending=False).to_csv(
        OUT_CSV, index=False, encoding="utf-8-sig"
    )

    records = df.round(4).to_dict(orient="records")
    top_growth = df.sort_values("crescimento_1977_2024_km2", ascending=False).head(10)
    top_density = df.sort_values("densidade_pop_bairro", ascending=False).head(10)
    top_pop = df.sort_values("pop_estimada", ascending=False).head(10)
    top_per_capita = df.sort_values("crescimento_por_1000_hab_km2", ascending=False).head(10)

    stats = {
        "bairros": int(len(df)),
        "pop_total": float(df["pop_estimada"].sum()),
        "dom_total": float(df["dom_estima"].sum()),
        "densidade_media_ponderada": float(
            df["pop_estimada"].sum() / df["area_bairro_km2"].sum()
        ),
        "crescimento_total": float(df["crescimento_1977_2024_km2"].sum()),
        "corr_pop_crescimento": corr(df, "pop_estimada", "crescimento_1977_2024_km2"),
        "corr_densidade_crescimento": corr(
            df, "densidade_pop_bairro", "crescimento_1977_2024_km2"
        ),
        "corr_densidade_pct_urb": corr(df, "densidade_pop_bairro", "pct_urb_2024"),
        "top_growth_bairro": str(top_growth.iloc[0]["bairro"]),
        "top_growth_valor": float(top_growth.iloc[0]["crescimento_1977_2024_km2"]),
        "top_density_bairro": str(top_density.iloc[0]["bairro"]),
        "top_density_valor": float(top_density.iloc[0]["densidade_pop_bairro"]),
    }

    payload = {
        "records": records,
        "stats": stats,
        "topGrowth": top_growth.round(4).to_dict(orient="records"),
        "topDensity": top_density.round(4).to_dict(orient="records"),
        "topPop": top_pop.round(4).to_dict(orient="records"),
        "topPerCapita": top_per_capita.round(4).to_dict(orient="records"),
    }

    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Comparativo socio-urbano - Florianópolis</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{
  --bg: #f6f2ec;
  --panel: #ffffff;
  --ink: #10231f;
  --muted: #56665f;
  --grid: #ded8cf;
  --border: #d8cec2;
  --control: #fbf8f2;
  --shadow: rgba(72, 58, 44, .10);
  --teal: #2f8077;
  --blue: #6f88b7;
  --gold: #d8ae35;
  --red: #d07a78;
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
  --control: #22302c;
  --shadow: rgba(0, 0, 0, .34);
  --teal: #84d8cc;
  --blue: #a7bceb;
  --gold: #efcf6a;
  --red: #efa09d;
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
  display: flex;
  justify-content: space-between;
  gap: 24px;
  align-items: end;
  margin-bottom: 22px;
  background: var(--hero-bg);
  border: 1px solid var(--border);
  border-radius: 22px;
  padding: 32px;
  box-shadow: 0 10px 28px var(--shadow);
}}
h1 {{ margin: 0; font-size: clamp(34px, 3.6vw, 56px); line-height: 1.05; letter-spacing: 0; }}
.lead {{ margin: 12px 0 0; color: var(--muted); font-size: 22px; line-height: 1.45; max-width: 1040px; }}
.header-actions {{ display: flex; align-items: end; gap: 16px; flex-shrink: 0; }}
button, .button {{ font: inherit; }}
.theme-toggle, .button {{
  border: 1px solid var(--border);
  background: var(--panel);
  color: var(--ink);
  border-radius: 999px;
  cursor: pointer;
  font-weight: 700;
  padding: 15px 22px;
  white-space: nowrap;
  font-size: 18px;
  text-decoration: none;
  display: inline-block;
}}
.metrics {{
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 16px;
  margin-bottom: 18px;
}}
.metric {{
  padding: 22px;
  min-height: 156px;
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 10px 28px var(--shadow);
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
.tab-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 7px; padding: 8px 0 12px; }}
.tab-button {{
  border: 1px solid var(--border);
  background: var(--panel);
  padding: 10px 14px;
  border-radius: 999px;
  cursor: pointer;
  font-weight: 700;
  color: var(--ink);
  line-height: 1.2;
  text-align: center;
  font-size: 15px;
  box-shadow: 0 6px 16px var(--shadow);
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
.panel {{
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  box-shadow: 0 10px 28px var(--shadow);
  overflow: hidden;
}}
.panel-head {{
  margin: 20px 24px 0;
  padding: 18px;
  background: rgba(242, 235, 140, .36);
  border: 1px solid rgba(166, 153, 73, .18);
  border-radius: 12px;
}}
.panel-title {{ margin: 0; font-size: 34px; line-height: 1.12; letter-spacing: 0; }}
.panel-note {{ margin: 10px 0 0; color: var(--muted); line-height: 1.45; font-size: 18px; }}
.plot-wrap {{
  margin: 20px 24px 24px;
  padding: 18px;
  background: rgba(242, 235, 140, .36);
  border: 1px solid rgba(166, 153, 73, .18);
  border-radius: 12px;
}}
.chart {{ width: 100%; min-height: 640px; }}
.chart.short {{ min-height: 520px; }}
.info-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.info-card {{
  min-height: 160px;
  padding: 20px;
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 8px 22px var(--shadow);
  background: var(--metric-a);
}}
.info-card:nth-child(5n + 2) {{ background: var(--metric-b); }}
.info-card:nth-child(5n + 3) {{ background: var(--metric-c); }}
.info-card:nth-child(5n + 4) {{ background: var(--metric-d); }}
.info-card:nth-child(5n + 5) {{ background: var(--metric-e); }}
.info-card h3 {{ margin: 0 0 10px; font-size: 22px; line-height: 1.16; }}
.info-card p, .info-card li {{ color: var(--muted); font-size: 16px; line-height: 1.46; }}
.info-card p {{ margin: 0 0 12px; }}
.info-card ul {{ margin: 0; padding-left: 20px; }}
.formula-grid {{
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
}}
.formula {{
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--metric-a);
  box-shadow: 0 8px 22px var(--shadow);
}}
.formula:nth-child(5n + 2) {{ background: var(--metric-b); }}
.formula:nth-child(5n + 3) {{ background: var(--metric-c); }}
.formula:nth-child(5n + 4) {{ background: var(--metric-d); }}
.formula:nth-child(5n + 5) {{ background: var(--metric-e); }}
.formula strong {{
  display: block;
  margin-bottom: 8px;
  color: var(--ink);
  font-size: 17px;
}}
.formula code {{
  display: block;
  white-space: normal;
  overflow-wrap: anywhere;
  color: var(--muted);
  font-family: Consolas, Monaco, monospace;
  font-size: 14px;
  line-height: 1.45;
}}
.tab-explain {{
  display: grid;
  grid-template-columns: minmax(0, 1.15fr) minmax(260px, .85fr);
  gap: 14px;
  margin-bottom: 16px;
}}
.explain-card {{
  padding: 16px 18px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--metric-b);
  box-shadow: 0 8px 22px var(--shadow);
}}
.explain-card:nth-child(2) {{ background: var(--metric-d); }}
.explain-card strong {{
  display: block;
  color: var(--ink);
  font-size: 18px;
  margin-bottom: 8px;
}}
.explain-card p {{
  margin: 0;
  color: var(--muted);
  font-size: 16px;
  line-height: 1.45;
}}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
th, td {{ padding: 11px 12px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ color: var(--ink); background: var(--control); position: sticky; top: 0; }}
td {{ color: var(--muted); }}
tbody tr:nth-child(5n + 1) {{ background: rgba(216, 243, 239, .42); }}
tbody tr:nth-child(5n + 2) {{ background: rgba(217, 233, 251, .42); }}
tbody tr:nth-child(5n + 3) {{ background: rgba(215, 240, 250, .42); }}
tbody tr:nth-child(5n + 4) {{ background: rgba(223, 243, 227, .42); }}
tbody tr:nth-child(5n + 5) {{ background: rgba(231, 222, 247, .42); }}
body[data-theme="dark"] tbody tr:nth-child(5n + 1) {{ background: rgba(29, 61, 58, .38); }}
body[data-theme="dark"] tbody tr:nth-child(5n + 2) {{ background: rgba(32, 52, 77, .38); }}
body[data-theme="dark"] tbody tr:nth-child(5n + 3) {{ background: rgba(28, 59, 72, .38); }}
body[data-theme="dark"] tbody tr:nth-child(5n + 4) {{ background: rgba(33, 60, 42, .38); }}
body[data-theme="dark"] tbody tr:nth-child(5n + 5) {{ background: rgba(48, 42, 73, .38); }}
.profile-badge {{
  display: inline-block;
  padding: 7px 10px;
  border-radius: 999px;
  color: #10231f;
  font-weight: 700;
  line-height: 1.2;
  white-space: nowrap;
}}
.profile-alta-expansao-e-alta-densidade {{ background: #94aee6; }}
.profile-alta-expansao-e-baixa-densidade {{ background: #88c9df; }}
.profile-baixa-expansao-e-alta-densidade {{ background: #b6d98b; }}
.profile-baixa-expansao-e-baixa-densidade {{ background: #e8cf75; }}
.footer {{
  margin: 22px 0 0;
  padding: 24px;
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 12px;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.5;
  box-shadow: 0 10px 28px var(--shadow);
}}
.footer h2 {{
  margin: 0 0 16px;
  color: var(--ink);
  font-size: 28px;
  line-height: 1.12;
}}
.footer-grid {{
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}}
.footer-card {{
  padding: 16px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--metric-a);
  box-shadow: 0 8px 22px var(--shadow);
}}
.footer-card:nth-child(2) {{ background: var(--metric-b); }}
.footer-card:nth-child(3) {{ background: var(--metric-c); }}
.footer-card:nth-child(4) {{ background: var(--metric-d); }}
.footer strong {{ display: block; color: var(--ink); margin-bottom: 7px; }}
.footer p {{ margin: 0; }}
@media (max-width: 980px) {{
  main {{ padding: 14px; }}
  header {{ flex-direction: column; align-items: stretch; }}
  .header-actions {{ flex-direction: column; align-items: stretch; }}
  .metrics, .info-grid, .tab-list, .tab-explain, .formula-grid, .footer-grid {{ grid-template-columns: 1fr; }}
  .chart {{ min-height: 520px; }}
}}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Comparativo socio-urbano</h1>
      <p class="lead">Florianópolis - cruzamento entre crescimento urbano, população estimada, densidade e domicílios por bairro.</p>
    </div>
    <div class="header-actions">
      <a class="button" href="../index.html">Voltar ao índice</a>
      <button class="theme-toggle" id="theme-toggle" type="button" aria-label="Alternar modo escuro">Modo escuro</button>
    </div>
  </header>

  <section class="metrics">
    <div class="metric"><span>Bairros analisados</span><strong>{stats["bairros"]}</strong><small>Unidades com dados urbanos e populacionais.</small></div>
    <div class="metric"><span>População estimada</span><strong>{fmt_pt(stats["pop_total"], 0)}</strong><small>Soma dos bairros na camada `gvw_bairros`.</small></div>
    <div class="metric"><span>Domicílios estimados</span><strong>{fmt_pt(stats["dom_total"], 0)}</strong><small>Base para comparações de ocupação residencial.</small></div>
    <div class="metric"><span>Crescimento urbano</span><strong>{fmt_pt(stats["crescimento_total"])} km²</strong><small>Diferença entre 1977 e 2024.</small></div>
    <div class="metric"><span>Maior crescimento</span><strong>{stats["top_growth_bairro"]}</strong><small>{fmt_pt(stats["top_growth_valor"])} km² entre 1977 e 2024.</small></div>
  </section>

  <section class="tabs" aria-label="Comparações socio-urbanas">
    <div class="tab-list" role="tablist">
      <button class="tab-button active" type="button" role="tab" aria-selected="true" aria-controls="tab-historia" data-tab="tab-historia">História dos dados</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-metodologia" data-tab="tab-metodologia">Metodologia/Estatísticas</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-glossario" data-tab="tab-glossario">Glossário</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-pop" data-tab="tab-pop">Crescimento x população</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-densidade" data-tab="tab-densidade">Crescimento x densidade</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-quadrantes" data-tab="tab-quadrantes">Perfis de bairros</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-rankings" data-tab="tab-rankings">Rankings comparativos</button>
      <button class="tab-button" type="button" role="tab" aria-selected="false" aria-controls="tab-tabela" data-tab="tab-tabela">Tabela síntese</button>
    </div>

    <div id="tab-historia" class="tab-panel active" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">O que este dashboard compara</h2>
          <p class="panel-note">Este segundo painel não substitui o dashboard principal: ele aprofunda a leitura social da urbanização por bairro.</p>
        </div>
        <div class="plot-wrap">
          <div class="info-grid">
            <article class="info-card">
              <h3>Pergunta central</h3>
              <p>Os bairros que mais cresceram em área urbanizada também concentram mais população, domicílios e densidade?</p>
            </article>
            <article class="info-card">
              <h3>Como ler</h3>
              <p>Crescimento em km² mostra expansão territorial. População, densidade e domicílios ajudam a diferenciar expansão extensa de ocupação concentrada.</p>
            </article>
            <article class="info-card">
              <h3>Cuidado interpretativo</h3>
              <p>A população é uma fotografia recente, enquanto o crescimento urbano acumula 1977-2024. Portanto, a leitura é comparativa, não causal.</p>
            </article>
            <article class="info-card">
              <h3>Correlação população x crescimento</h3>
              <p>Coeficiente de Pearson: <strong>{fmt_pt(stats["corr_pop_crescimento"], 3)}</strong>. Valores próximos de 1 indicam associação positiva mais forte.</p>
            </article>
            <article class="info-card">
              <h3>Correlação densidade x crescimento</h3>
              <p>Coeficiente de Pearson: <strong>{fmt_pt(stats["corr_densidade_crescimento"], 3)}</strong>. Ajuda a observar se expansão territorial acompanha adensamento.</p>
            </article>
            <article class="info-card">
              <h3>Correlação densidade x % urbano</h3>
              <p>Coeficiente de Pearson: <strong>{fmt_pt(stats["corr_densidade_pct_urb"], 3)}</strong>. Relaciona ocupação populacional e proporção urbanizada em 2024.</p>
            </article>
          </div>
        </div>
      </div>
    </div>

    <div id="tab-metodologia" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Metodologia e estatísticas</h2>
          <p class="panel-note">Resumo dos dados usados, indicadores calculados e fórmulas aplicadas no dashboard comparativo socio-urbano.</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba documenta como a tabela comparativa foi construída a partir do cruzamento entre urbanização por bairro e atributos populacionais da camada `gvw_bairros`.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>Os indicadores são exploratórios. Eles aproximam a urbanização acumulada entre 1977 e 2024 de uma fotografia populacional recente dos bairros.</p>
            </div>
          </div>
          <div class="formula-grid">
            <div class="formula">
              <strong>Crescimento urbano absoluto</strong>
              <code>ΔA = Aurb_2024 - Aurb_1977</code>
            </div>
            <div class="formula">
              <strong>Crescimento por mil habitantes</strong>
              <code>C1000 = (ΔA / população_estimada) × 1.000</code>
            </div>
            <div class="formula">
              <strong>Área urbanizada por mil habitantes</strong>
              <code>A1000 = (Aurb_2024 / população_estimada) × 1.000</code>
            </div>
            <div class="formula">
              <strong>Habitantes por km² urbanizado</strong>
              <code>HabUrb = população_estimada / Aurb_2024</code>
            </div>
            <div class="formula">
              <strong>Domicílios por km² urbanizado</strong>
              <code>DomUrb = domicílios_estimados / Aurb_2024</code>
            </div>
            <div class="formula">
              <strong>Crescimento relativo</strong>
              <code>Crel = (ΔA / Aurb_1977) × 100</code>
            </div>
            <div class="formula">
              <strong>Correlação de Pearson</strong>
              <code>r = cov(X,Y) / (σX × σY)</code>
            </div>
            <div class="formula">
              <strong>Perfis socio-urbanos</strong>
              <code>perfil = combinação entre ΔA acima/abaixo da mediana e densidade acima/abaixo da mediana</code>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div id="tab-glossario" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Glossário</h2>
          <p class="panel-note">Definições dos principais termos usados na leitura socio-urbana do dashboard.</p>
        </div>
        <div class="plot-wrap">
          <div class="info-grid">
            <article class="info-card"><h3>Crescimento urbano</h3><p>Aumento da área urbanizada entre dois anos. Neste painel, o recorte principal compara 1977 e 2024.</p></article>
            <article class="info-card"><h3>População estimada</h3><p>População atribuída aos bairros na camada `gvw_bairros`. É usada como aproximação recente para comparação com a mancha urbana.</p></article>
            <article class="info-card"><h3>Densidade populacional</h3><p>Relação entre população e área territorial do bairro, expressa em habitantes por km².</p></article>
            <article class="info-card"><h3>Domicílios estimados</h3><p>Número estimado de domicílios por bairro. Ajuda a observar a ocupação residencial associada à urbanização.</p></article>
            <article class="info-card"><h3>Área urbanizada por habitante</h3><p>Indicador que relaciona a área urbana de 2024 com a população estimada. Valores maiores sugerem ocupação mais espalhada.</p></article>
            <article class="info-card"><h3>Crescimento por mil habitantes</h3><p>Normaliza o crescimento urbano pelo tamanho populacional do bairro, permitindo comparar bairros muito diferentes.</p></article>
            <article class="info-card"><h3>Correlação</h3><p>Medida estatística de associação entre duas variáveis. Não prova causalidade, mas indica se elas tendem a variar juntas.</p></article>
            <article class="info-card"><h3>Mediana</h3><p>Valor central da distribuição. Foi usada para separar bairros acima e abaixo do crescimento e da densidade típicos.</p></article>
            <article class="info-card"><h3>Alta expansão</h3><p>Bairro com crescimento urbano igual ou superior à mediana municipal dos bairros analisados.</p></article>
            <article class="info-card"><h3>Alta densidade</h3><p>Bairro com densidade populacional igual ou superior à mediana municipal dos bairros analisados.</p></article>
            <article class="info-card"><h3>Espraiamento urbano</h3><p>Expansão territorial da área urbanizada que pode ocorrer sem aumento proporcional da densidade populacional.</p></article>
            <article class="info-card"><h3>Adensamento</h3><p>Concentração maior de habitantes ou domicílios em uma área menor, geralmente associada a ocupação urbana mais compacta.</p></article>
          </div>
        </div>
      </div>
    </div>

    <div id="tab-pop" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Crescimento urbano x população</h2>
          <p class="panel-note">Barras comparativas para os bairros com maior crescimento urbano. A leitura aproxima crescimento territorial em km² e população estimada em milhares de habitantes.</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba compara os bairros que mais ampliaram a mancha urbana com sua população estimada atual. Ela ajuda a identificar se a expansão territorial ocorreu em bairros também populosos.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>As barras verdes mostram crescimento em km²; as barras azuis mostram população em milhares de habitantes. Como as unidades são diferentes, a leitura deve ser comparativa, não de soma direta.</p>
            </div>
          </div>
          <div id="popChart" class="chart"></div>
        </div>
      </div>
    </div>

    <div id="tab-densidade" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Crescimento urbano x densidade</h2>
          <p class="panel-note">Barras comparativas para os bairros mais densos, mostrando densidade em mil hab/km² e crescimento urbano em km².</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba observa os bairros mais densos e compara essa concentração populacional com o crescimento urbano acumulado entre 1977 e 2024.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>Bairros densos nem sempre são os que mais expandiram em área. Quando a densidade é alta e o crescimento em km² é baixo, a leitura sugere ocupação mais concentrada.</p>
            </div>
          </div>
          <div id="densChart" class="chart"></div>
        </div>
      </div>
    </div>

    <div id="tab-quadrantes" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Perfis socio-urbanos dos bairros</h2>
          <p class="panel-note">Resumo dos quatro perfis criados pelas medianas de crescimento urbano e densidade populacional, sem sobreposição de pontos.</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba agrupa os bairros em quatro perfis, combinando crescimento urbano e densidade populacional. O objetivo é resumir padrões territoriais sem poluir a visualização.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>O gráfico mostra quanto cada perfil acumula de crescimento urbano e quantos bairros pertencem a ele. A classificação usa as medianas como linha de separação.</p>
            </div>
          </div>
          <div id="quadChart" class="chart"></div>
        </div>
      </div>
    </div>

    <div id="tab-rankings" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Rankings comparativos</h2>
          <p class="panel-note">Comparação entre maior crescimento absoluto, maior população, maior densidade e maior crescimento por mil habitantes.</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba reúne rankings complementares para enxergar a urbanização por diferentes lentes: área, população, densidade e crescimento relativo ao tamanho populacional.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>O ranking principal aparece primeiro. Os demais podem ser ativados pela legenda do Plotly, permitindo comparar quais bairros mudam de posição conforme o indicador escolhido.</p>
            </div>
          </div>
          <div id="rankChart" class="chart"></div>
        </div>
      </div>
    </div>

    <div id="tab-tabela" class="tab-panel" role="tabpanel">
      <div class="panel">
        <div class="panel-head">
          <h2 class="panel-title">Tabela síntese por bairro</h2>
          <p class="panel-note">Base final exportada também em CSV, organizada para revisão e uso em análises estatísticas complementares.</p>
        </div>
        <div class="plot-wrap">
          <div class="tab-explain">
            <div class="explain-card">
              <strong>O que está sendo apresentado</strong>
              <p>Esta aba mostra a base analítica bairro a bairro, reunindo crescimento urbano, percentual urbanizado, população, densidade, domicílios e perfil socio-urbano.</p>
            </div>
            <div class="explain-card">
              <strong>Como interpretar</strong>
              <p>As linhas usam tons pastel para facilitar a leitura sequencial. A coluna de perfil sintetiza se o bairro combina alta ou baixa expansão com alta ou baixa densidade.</p>
            </div>
          </div>
          <div class="table-wrap"><table id="summaryTable"></table></div>
        </div>
      </div>
    </div>
  </section>

  <footer class="footer">
    <h2>Referências e processamento</h2>
    <div class="footer-grid">
      <div class="footer-card">
        <strong>Autoria</strong>
        <p>Caetano Ronan - UFSC.</p>
      </div>
      <div class="footer-card">
        <strong>Fontes</strong>
        <p>`urbanizacao_por_bairro_1977_2002_2024.csv` e camada `gvw_bairros`, com população estimada, densidade, domicílios e regiões administrativas.</p>
      </div>
      <div class="footer-card">
        <strong>Processamento</strong>
        <p>SIRGAS 2000 / UTM zona 22S, EPSG:31982. Indicadores gerados por cruzamento tabular dos bairros, cálculo de razões, correlações e perfis por mediana.</p>
      </div>
      <div class="footer-card">
        <strong>Leitura crítica</strong>
        <p>A comparação é exploratória: população e densidade representam uma base recente, enquanto o crescimento urbano é acumulado entre 1977 e 2024.</p>
      </div>
    </div>
  </footer>
</main>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
const fmt = new Intl.NumberFormat('pt-BR', {{ maximumFractionDigits: 2 }});
const cssVar = name => getComputedStyle(document.body).getPropertyValue(name).trim();
const chartConfig = name => ({{
  responsive: true,
  displayModeBar: true,
  displaylogo: false,
  toImageButtonOptions: {{ format: 'png', filename: name, height: 900, width: 1400, scale: 2 }}
}});
const baseLayout = extra => ({{
  paper_bgcolor: 'rgba(0,0,0,0)',
  plot_bgcolor: 'rgba(0,0,0,0)',
  font: {{ family: 'Arial, sans-serif', color: cssVar('--ink') }},
  margin: {{ l: 76, r: 34, t: 48, b: 90 }},
  ...extra
}});
const pastel = ['#94aee6', '#88c9df', '#75b7a8', '#b6d98b', '#e8cf75', '#d7b6e6', '#eda7a0', '#9fd3c7', '#f2cf7e', '#b8c6ef'];
const pastelSoft = ['#d9e9fb', '#d7f0fa', '#d8f3ef', '#dff3e3', '#f1e6a8', '#e7def7', '#f3c9c5', '#cdece5', '#f2dca4', '#dfe5fb'];
const profileColors = {{
  'Alta expansão e alta densidade': '#94aee6',
  'Alta expansão e baixa densidade': '#88c9df',
  'Baixa expansão e alta densidade': '#b6d98b',
  'Baixa expansão e baixa densidade': '#e8cf75'
}};
const colorByIndex = rows => rows.map((d, i) => pastel[i % pastel.length]);
const softColorByIndex = rows => rows.map((d, i) => pastelSoft[i % pastelSoft.length]);

function renderCharts() {{
  const rows = data.records.filter(d => d.pop_estimada && d.densidade_pop_bairro);
  const topGrowthRows = [...rows].sort((a, b) => b.crescimento_1977_2024_km2 - a.crescimento_1977_2024_km2).slice(0, 16).reverse();
  const topDensityRows = [...rows].sort((a, b) => b.densidade_pop_bairro - a.densidade_pop_bairro).slice(0, 16).reverse();

  Plotly.newPlot('popChart', [{{
    type: 'bar',
    name: 'Crescimento urbano (km²)',
    x: topGrowthRows.map(d => d.crescimento_1977_2024_km2),
    y: topGrowthRows.map(d => d.bairro),
    orientation: 'h',
    marker: {{ color: colorByIndex(topGrowthRows) }},
    text: topGrowthRows.map(d => `${{fmt.format(d.crescimento_1977_2024_km2)}} km²`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{{y}}<br>Crescimento: %{{x:.2f}} km²<extra></extra>'
  }}, {{
    type: 'bar',
    name: 'População estimada (mil hab.)',
    x: topGrowthRows.map(d => d.pop_estimada / 1000),
    y: topGrowthRows.map(d => d.bairro),
    orientation: 'h',
    marker: {{ color: softColorByIndex(topGrowthRows) }},
    text: topGrowthRows.map(d => `${{fmt.format(d.pop_estimada / 1000)}} mil`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{{y}}<br>População: %{{x:.2f}} mil hab.<extra></extra>'
  }}], baseLayout({{
    barmode: 'group',
    margin: {{ l: 170, r: 120, t: 48, b: 92 }},
    xaxis: {{ title: 'Valor comparativo: km² e mil habitantes', gridcolor: cssVar('--grid') }},
    yaxis: {{ automargin: true }},
    legend: {{ orientation: 'h', y: 1.14 }}
  }}), chartConfig('crescimento_urbano_populacao_bairros'));

  Plotly.newPlot('densChart', [{{
    type: 'bar',
    name: 'Densidade (mil hab/km²)',
    x: topDensityRows.map(d => d.densidade_pop_bairro / 1000),
    y: topDensityRows.map(d => d.bairro),
    orientation: 'h',
    marker: {{ color: colorByIndex(topDensityRows) }},
    text: topDensityRows.map(d => `${{fmt.format(d.densidade_pop_bairro / 1000)}} mil`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{{y}}<br>Densidade: %{{x:.2f}} mil hab/km²<extra></extra>'
  }}, {{
    type: 'bar',
    name: 'Crescimento urbano (km²)',
    x: topDensityRows.map(d => d.crescimento_1977_2024_km2),
    y: topDensityRows.map(d => d.bairro),
    orientation: 'h',
    marker: {{ color: softColorByIndex(topDensityRows) }},
    text: topDensityRows.map(d => `${{fmt.format(d.crescimento_1977_2024_km2)}} km²`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '%{{y}}<br>Crescimento: %{{x:.2f}} km²<extra></extra>'
  }}], baseLayout({{
    barmode: 'group',
    margin: {{ l: 170, r: 120, t: 48, b: 92 }},
    xaxis: {{ title: 'Valor comparativo: mil hab/km² e km²', gridcolor: cssVar('--grid') }},
    yaxis: {{ automargin: true }},
    legend: {{ orientation: 'h', y: 1.14 }}
  }}), chartConfig('crescimento_urbano_densidade_bairros'));

  const profiles = [...new Set(rows.map(d => d.perfil_socio_urbano))];
  const profileRows = profiles.map(profile => {{
    const subset = rows.filter(d => d.perfil_socio_urbano === profile);
    return {{
      profile,
      count: subset.length,
      growth: subset.reduce((sum, d) => sum + d.crescimento_1977_2024_km2, 0),
      pop: subset.reduce((sum, d) => sum + d.pop_estimada, 0),
      bairros: subset.sort((a, b) => b.crescimento_1977_2024_km2 - a.crescimento_1977_2024_km2).slice(0, 5).map(d => d.bairro).join(', ')
    }};
  }}).sort((a, b) => b.growth - a.growth);
  Plotly.newPlot('quadChart', [{{
    type: 'bar',
    name: 'Crescimento total (km²)',
    x: profileRows.map(d => d.profile),
    y: profileRows.map(d => d.growth),
    marker: {{ color: profileRows.map(d => profileColors[d.profile] || '#75b7a8') }},
    text: profileRows.map(d => `${{fmt.format(d.growth)}} km²`),
    textposition: 'outside',
    cliponaxis: false,
    customdata: profileRows.map(d => [d.count, d.pop, d.bairros]),
    hovertemplate: '<b>%{{x}}</b><br>Crescimento: %{{y:.2f}} km²<br>Bairros: %{{customdata[0]}}<br>População: %{{customdata[1]:,.0f}}<br>Destaques: %{{customdata[2]}}<extra></extra>'
  }}, {{
    type: 'bar',
    name: 'Número de bairros',
    x: profileRows.map(d => d.profile),
    y: profileRows.map(d => d.count),
    yaxis: 'y2',
    marker: {{ color: profileRows.map(d => profileColors[d.profile] || '#75b7a8'), opacity: .42 }},
    text: profileRows.map(d => `${{d.count}} bairros`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '<b>%{{x}}</b><br>Bairros: %{{y}}<extra></extra>'
  }}], baseLayout({{
    barmode: 'group',
    margin: {{ l: 76, r: 82, t: 48, b: 120 }},
    xaxis: {{ tickangle: -12, gridcolor: cssVar('--grid') }},
    yaxis: {{ title: 'Crescimento urbano total (km²)', gridcolor: cssVar('--grid') }},
    yaxis2: {{ title: 'Número de bairros', overlaying: 'y', side: 'right', rangemode: 'tozero' }},
    legend: {{ orientation: 'h', y: 1.14 }}
  }}), chartConfig('perfis_socio_urbanos_bairros'));

  const rankGroups = [
    {{ name: 'Crescimento km²', rows: data.topGrowth, field: 'crescimento_1977_2024_km2', suffix: ' km²' }},
    {{ name: 'População', rows: data.topPop, field: 'pop_estimada', suffix: ' hab.' }},
    {{ name: 'Densidade', rows: data.topDensity, field: 'densidade_pop_bairro', suffix: ' hab/km²' }},
    {{ name: 'km² por mil hab.', rows: data.topPerCapita, field: 'crescimento_por_1000_hab_km2', suffix: '' }}
  ];
  Plotly.newPlot('rankChart', rankGroups.map((group, idx) => ({{
    type: 'bar',
    name: group.name,
    x: group.rows.map(d => d[group.field]),
    y: group.rows.map(d => d.bairro),
    orientation: 'h',
    marker: {{ color: group.rows.map((d, i) => pastel[(i + idx * 2) % pastel.length]) }},
    text: group.rows.map(d => `${{fmt.format(d[group.field])}}${{group.suffix}}`),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: `%{{y}}<br>${{group.name}}: %{{x:.2f}}<extra></extra>`,
    visible: idx === 0 ? true : 'legendonly'
  }})), baseLayout({{
    barmode: 'group',
    margin: {{ l: 170, r: 120, t: 48, b: 80 }},
    xaxis: {{ gridcolor: cssVar('--grid') }},
    yaxis: {{ automargin: true, autorange: 'reversed' }},
    legend: {{ orientation: 'h', y: 1.14 }}
  }}), chartConfig('rankings_socio_urbanos_bairros'));
}}

function renderTable() {{
  const rows = [...data.records].sort((a, b) => b.crescimento_1977_2024_km2 - a.crescimento_1977_2024_km2);
  const head = ['Bairro', 'Região', 'Cresc. km²', '% urb. 2024', 'População', 'Densidade', 'Domicílios', 'Perfil'];
  const profileClass = value => `profile-${{String(value).normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')}}`;
  const body = rows.map(d => `<tr>
    <td>${{d.bairro}}</td>
    <td>${{d.regiao_adm}}</td>
    <td>${{fmt.format(d.crescimento_1977_2024_km2)}}</td>
    <td>${{fmt.format(d.pct_urb_2024)}}%</td>
    <td>${{fmt.format(d.pop_estimada)}}</td>
    <td>${{fmt.format(d.densidade_pop_bairro)}}</td>
    <td>${{fmt.format(d.dom_estima || 0)}}</td>
    <td><span class="profile-badge ${{profileClass(d.perfil_socio_urbano)}}">${{d.perfil_socio_urbano}}</span></td>
  </tr>`).join('');
  document.getElementById('summaryTable').innerHTML = `<thead><tr>${{head.map(h => `<th>${{h}}</th>`).join('')}}</tr></thead><tbody>${{body}}</tbody>`;
}}

function applyTheme(theme) {{
  document.body.dataset.theme = theme;
  document.getElementById('theme-toggle').textContent = theme === 'dark' ? 'Modo claro' : 'Modo escuro';
  localStorage.setItem('urbanizacao-comparativo-theme-floripa', theme);
  window.setTimeout(renderCharts, 40);
}}

document.querySelectorAll('.tab-button').forEach(button => {{
  button.addEventListener('click', () => {{
    const target = button.dataset.tab;
    document.querySelectorAll('.tab-button').forEach(item => {{
      const active = item === button;
      item.classList.toggle('active', active);
      item.setAttribute('aria-selected', active ? 'true' : 'false');
    }});
    document.querySelectorAll('.tab-panel').forEach(panel => {{
      panel.classList.toggle('active', panel.id === target);
    }});
    window.setTimeout(() => ['popChart', 'densChart', 'quadChart', 'rankChart'].forEach(id => {{
      const el = document.getElementById(id);
      if (el) Plotly.Plots.resize(el);
    }}), 80);
  }});
}});

document.getElementById('theme-toggle').addEventListener('click', () => {{
  applyTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark');
}});

renderTable();
applyTheme(localStorage.getItem('urbanizacao-comparativo-theme-floripa') || 'light');
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    print(OUT_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
