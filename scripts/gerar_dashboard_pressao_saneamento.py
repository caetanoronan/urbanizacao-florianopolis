from pathlib import Path
import json
import unicodedata

import geopandas as gpd
import pandas as pd
from shapely.ops import unary_union
from shapely.validation import make_valid


ROOT = Path(__file__).resolve().parents[1]
URB_DIR = ROOT / "dados_brutos"
RESULT_DIR = ROOT / "resultados"
DASHBOARD_DIR = ROOT / "dashboard"
OUT_CSV = RESULT_DIR / "pressao_urbana_distritos_saneamento.csv"
OUT_INSPECOES_CSV = RESULT_DIR / "inspecoes_saneamento_por_distrito.csv"
OUT_HTML = DASHBOARD_DIR / "dashboard_pressao_saneamento.html"
OUT_INSPECOES_HTML = DASHBOARD_DIR / "dashboard_inspecoes_saneamento.html"


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


def normalize_text(value):
    if pd.isna(value):
        return ""
    text = str(value).lower()
    return "".join(
        char for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )


def main():
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    saneamento = load_layer(URB_DIR / "sau_dist_san.zip")
    bairros = load_layer(URB_DIR / "gvw_bairros" / "gvw_bairros.shp")
    inspecoes = load_layer(URB_DIR / "inspecoes_smmads_geoportal.zip")
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

    inspecoes_join = gpd.sjoin(
        inspecoes.to_crs(saneamento.crs),
        saneamento[["nm_dist_sa", "geometry"]],
        predicate="intersects",
        how="left",
    )
    texto_inspecao = (
        inspecoes_join["situacao_i"].map(normalize_text)
        + " "
        + inspecoes_join["situacao_e"].map(normalize_text)
        + " "
        + inspecoes_join["observacoe"].map(normalize_text)
    )
    inspecoes_join["flag_adequada"] = texto_inspecao.str.contains(
        "adequada|sem irregularidades", regex=True
    )
    inspecoes_join["flag_inadequada"] = texto_inspecao.str.contains(
        "inadequada|irregular|ausencia|inadequac|nao conectado|parcialmente|pluvial|tratamento local|fossa",
        regex=True,
    )
    inspecoes_join["flag_nao_conectado_rede"] = texto_inspecao.str.contains(
        "nao conectado a rede", regex=False
    )
    inspecoes_join["flag_conectado_parcial"] = texto_inspecao.str.contains(
        "parcialmente a rede", regex=False
    )
    inspecoes_join["flag_tratamento_local"] = texto_inspecao.str.contains(
        "tratamento local|sistema local|fossa", regex=True
    )
    inspecoes_join["flag_pluvial"] = texto_inspecao.str.contains("pluvial", regex=False)
    inspecoes_join["flag_caixa_gordura"] = texto_inspecao.str.contains(
        "caixa de gordura", regex=False
    )
    inspecoes_join["distrito_saneamento"] = (
        inspecoes_join["nm_dist_sa"].fillna("Fora dos distritos").str.replace("Continte", "Continente")
    )

    inspecoes_df = (
        inspecoes_join.groupby("distrito_saneamento", dropna=False)
        .agg(
            inspecoes_total=("id", "count"),
            inspecoes_adequadas=("flag_adequada", "sum"),
            inspecoes_inadequadas_indicios=("flag_inadequada", "sum"),
            nao_conectado_rede=("flag_nao_conectado_rede", "sum"),
            conectado_parcial_rede=("flag_conectado_parcial", "sum"),
            tratamento_local_fossa=("flag_tratamento_local", "sum"),
            ligacao_pluvial_irregular=("flag_pluvial", "sum"),
            caixa_gordura_problema=("flag_caixa_gordura", "sum"),
        )
        .reset_index()
    )
    for column in inspecoes_df.columns:
        if column != "distrito_saneamento":
            inspecoes_df[column] = inspecoes_df[column].astype(int)

    inspecoes_df["pct_inadequadas_indicios"] = (
        100 * inspecoes_df["inspecoes_inadequadas_indicios"] / inspecoes_df["inspecoes_total"]
    ).fillna(0)
    inspecoes_df["pct_nao_conectado_rede"] = (
        100 * inspecoes_df["nao_conectado_rede"] / inspecoes_df["inspecoes_total"]
    ).fillna(0)
    inspecoes_df["pct_tratamento_local_fossa"] = (
        100 * inspecoes_df["tratamento_local_fossa"] / inspecoes_df["inspecoes_total"]
    ).fillna(0)
    inspecoes_df["pct_conectado_parcial_rede"] = (
        100 * inspecoes_df["conectado_parcial_rede"] / inspecoes_df["inspecoes_total"]
    ).fillna(0)

    inspecoes_validas = inspecoes_df[inspecoes_df["distrito_saneamento"].ne("Fora dos distritos")].copy()
    df = df.merge(inspecoes_validas, on="distrito_saneamento", how="left")
    fill_columns = [column for column in inspecoes_validas.columns if column != "distrito_saneamento"]
    df[fill_columns] = df[fill_columns].fillna(0)

    df["indice_pressao_urbana_saneamento"] = (
        0.45 * normalize(df["crescimento_1977_2024_km2"])
        + 0.35 * normalize(df["pct_urb_2024"])
        + 0.20 * normalize(df["crescimento_por_1000_hab_km2"])
    )
    df["indice_prioridade_investimento"] = (
        0.35 * normalize(df["indice_pressao_urbana_saneamento"])
        + 0.25 * normalize(df["inspecoes_inadequadas_indicios"])
        + 0.20 * normalize(df["nao_conectado_rede"])
        + 0.20 * normalize(df["tratamento_local_fossa"])
    )
    df = df.sort_values("indice_pressao_urbana_saneamento", ascending=False)
    df.round(4).to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    inspecoes_validas.round(4).to_csv(OUT_INSPECOES_CSV, index=False, encoding="utf-8-sig")

    records = df.round(4).to_dict(orient="records")
    datas_validas = inspecoes["data"].dropna()
    data_inicio = datas_validas.min().strftime("%d/%m/%Y") if not datas_validas.empty else "-"
    data_fim = datas_validas.max().strftime("%d/%m/%Y") if not datas_validas.empty else "-"

    categorias = (
        inspecoes["imovel_cat"]
        .fillna("Sem classificação")
        .replace("", "Sem classificação")
        .value_counts()
        .head(4)
    )
    categorias_txt = "; ".join(
        f"{categoria} ({fmt_pt(valor, 0)})" for categoria, valor in categorias.items()
    )

    programas_base = (
        inspecoes["nome_progr"]
        .dropna()
        .astype(str)
        .str.strip()
        .str.replace(r"\s+", " ", regex=True)
    )
    programas_norm = programas_base.str.lower()
    programas = (
        programas_norm
        .replace(
            {
                "trato pela lagoa": "Trato pela Lagoa",
                "trato pela costa norte": "Trato pela Costa Norte",
                "trato pelo costa norte": "Trato pela Costa Norte",
                "fslr": "FSLNR",
                "fslnr": "FSLNR",
                "fslnr'": "FSLNR",
                "sanear": "SANEAR",
                "tpc": "TPC",
                "blitz sanear floripa": "Blitz Sanear Floripa",
            }
        )
        .value_counts()
        .head(5)
    )
    programas_txt = "; ".join(
        f"{programa} ({fmt_pt(valor, 0)})" for programa, valor in programas.items()
    )
    inspecoes_validas_geo = inspecoes_join[
        inspecoes_join["distrito_saneamento"].ne("Fora dos distritos")
    ].copy()
    inspecoes_validas_geo["ano"] = pd.to_datetime(
        inspecoes_validas_geo["data"], errors="coerce"
    ).dt.year
    inspecoes_por_ano = (
        inspecoes_validas_geo.dropna(subset=["ano"])
        .groupby("ano")
        .size()
        .reset_index(name="registros")
        .sort_values("ano")
    )
    categorias_chart = categorias.reset_index()
    categorias_chart.columns = ["categoria", "registros"]
    programas_chart = programas.reset_index()
    programas_chart.columns = ["programa", "registros"]

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
        "inspecoes_total": int(inspecoes_validas["inspecoes_total"].sum()),
        "nao_conectado_total": int(inspecoes_validas["nao_conectado_rede"].sum()),
        "tratamento_local_total": int(inspecoes_validas["tratamento_local_fossa"].sum()),
        "maior_prioridade": df.sort_values("indice_prioridade_investimento", ascending=False).iloc[0]["distrito_saneamento"],
        "maior_prioridade_indice": float(df["indice_prioridade_investimento"].max()),
        "inspecoes_data_inicio": data_inicio,
        "inspecoes_data_fim": data_fim,
        "categorias_imoveis": categorias_txt,
        "programas_inspecao": programas_txt,
    }
    scope = {
        "anos": [
            {"ano": int(row["ano"]), "registros": int(row["registros"])}
            for _, row in inspecoes_por_ano.iterrows()
        ],
        "categorias": [
            {"categoria": str(row["categoria"]), "registros": int(row["registros"])}
            for _, row in categorias_chart.iterrows()
        ],
        "programas": [
            {"programa": str(row["programa"]), "registros": int(row["registros"])}
            for _, row in programas_chart.iterrows()
        ],
    }
    payload = {"records": records, "stats": stats, "scope": scope}

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
  --chart-bg: rgba(255, 255, 255, .76);
  --chart-border: rgba(216, 206, 194, .72);
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
  --chart-bg: rgba(27, 36, 34, .72);
  --chart-border: rgba(61, 77, 71, .78);
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
  margin: 20px 24px 24px; padding: 18px; background: var(--chart-bg);
  border: 1px solid var(--chart-border); border-radius: 12px;
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
.info-card p, .info-card li, .formula p, .formula code, .footer-card p {{
  color: var(--muted); font-size: 16px; line-height: 1.46;
}}
.info-card p, .formula p, .footer-card p {{ margin: 0 0 10px; }}
.formula p:last-child, .footer-card p:last-child {{ margin-bottom: 0; }}
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
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Evolução urbana por distrito</h2><p class="panel-note">Nesta aba o leitor encontra a comparação direta da área urbanizada em 1977, 2002/2003 e 2024 dentro de cada distrito de saneamento. O gráfico mostra onde a mancha urbana cresceu em área absoluta.</p></div>
      <div class="plot-wrap"><div id="evolucaoChart" class="chart"></div></div></div>
    </div>

    <div id="tab-pressao" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Índice de pressão urbana sobre saneamento</h2><p class="panel-note">Nesta aba aparece a síntese do painel: um índice de 0 a 100 que combina crescimento urbano absoluto, percentual urbanizado em 2024 e crescimento por mil habitantes. Clique em uma barra para fixar a informação no gráfico antes de exportar em PNG; duplo clique limpa as marcações.</p></div>
      <div class="plot-wrap"><div id="pressaoChart" class="chart"></div></div></div>
    </div>

    <div id="tab-percentual" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Percentual urbanizado por distrito</h2><p class="panel-note">Nesta aba o leitor observa o grau de ocupação de cada distrito. O gráfico ajuda a diferenciar distritos com grande crescimento recente daqueles que já estavam altamente urbanizados.</p></div>
      <div class="plot-wrap"><div id="percentualChart" class="chart"></div></div></div>
    </div>

    <div id="tab-metodologia" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Metodologia e estatísticas</h2><p class="panel-note">Nesta aba estão as fórmulas usadas para transformar camadas espaciais em indicadores comparáveis. A leitura é feita por distrito de saneamento, sempre em km², usando interseção espacial entre polígonos e normalização dos indicadores antes da composição do índice.</p></div>
      <div class="plot-wrap"><div class="formula-grid">
        <div class="formula"><strong>1. Área urbanizada por distrito</strong><p>Para cada ano, a mancha urbana foi cruzada com o limite de cada distrito. O resultado mede somente a parte da mancha que cai dentro daquele distrito.</p><code>Aurb_dist(ano) = área(distrito ∩ mancha urbana do ano) / 1.000.000</code><p>A divisão por 1.000.000 converte m² para km².</p></div>
        <div class="formula"><strong>2. Crescimento absoluto</strong><p>Mostra quanto a área urbanizada aumentou entre o início e o fim da série histórica.</p><code>ΔA = Aurb_dist(2024) - Aurb_dist(1977)</code><p>Valores maiores indicam distritos que receberam mais expansão territorial em km².</p></div>
        <div class="formula"><strong>3. Percentual urbanizado</strong><p>Indica quanto do distrito já estava ocupado pela mancha urbana em cada ano. Ajuda a separar distritos em expansão daqueles já consolidados.</p><code>%urb = (Aurb_dist / área_total_distrito) × 100</code><p>Um distrito pequeno pode ter pouco crescimento em km², mas percentual urbanizado muito alto.</p></div>
        <div class="formula"><strong>4. População aproximada</strong><p>A população foi aproximada pela sobreposição entre bairros e distritos. Quando um bairro atravessa mais de um distrito, sua população é distribuída proporcionalmente pela área de interseção.</p><code>Pop_dist = Σ(pop_bairro × área(bairro ∩ distrito) / área_bairro)</code><p>É uma estimativa espacial, útil para comparação exploratória.</p></div>
        <div class="formula"><strong>5. Crescimento por mil habitantes</strong><p>Relaciona expansão urbana e população aproximada. O objetivo é comparar pressão territorial em distritos com tamanhos populacionais diferentes.</p><code>C1000 = (ΔA / Pop_dist) × 1.000</code><p>O resultado expressa km² de crescimento urbano para cada mil habitantes aproximados.</p></div>
        <div class="formula"><strong>6. Normalização</strong><p>Antes de combinar indicadores com unidades diferentes, cada variável é transformada para escala comum de 0 a 100.</p><code>norm(x) = ((x - xmin) / (xmax - xmin)) × 100</code><p>Assim, km², percentual e crescimento por habitante podem entrar no mesmo índice.</p></div>
        <div class="formula"><strong>7. Índice de pressão urbana</strong><p>O índice dá maior peso ao crescimento absoluto, depois ao percentual urbanizado e, por fim, ao crescimento relativo à população.</p><code>IPUS = 0,45×norm(ΔA) + 0,35×norm(%urb2024) + 0,20×norm(C1000)</code><p>Quanto mais próximo de 100, maior a pressão territorial potencial sobre o distrito.</p></div>
        <div class="formula"><strong>8. Interpretação estatística</strong><p>O índice não mede capacidade da rede, vazão, ligações ativas ou cobertura oficial. Ele organiza evidências territoriais para orientar leitura de planejamento.</p><code>pressão maior = crescimento maior + ocupação maior + demanda populacional relativa maior</code><p>Por isso, deve ser lido como indicador exploratório, não como laudo operacional.</p></div>
        <div class="formula"><strong>9. Recorte temporal</strong><p>A comparação principal usa 1977 como marco histórico inicial e 2024 como situação mais recente. O ano 2002/2003 funciona como ponto intermediário para observar ritmo de evolução.</p><code>período total = 2024 - 1977 = 47 anos</code><p>Esse recorte permite enxergar a mudança acumulada da urbanização.</p></div>
      </div></div></div>
    </div>

    <div id="tab-glossario" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Glossário</h2><p class="panel-note">Nesta aba o leitor encontra os principais conceitos usados no painel, para interpretar os gráficos sem depender de conhecimento prévio em geoprocessamento ou saneamento.</p></div>
      <div class="plot-wrap"><div class="info-grid">
        <article class="info-card"><h3>Distrito de saneamento</h3><p>Unidade territorial associada ao planejamento e operação de serviços de saneamento.</p></article>
        <article class="info-card"><h3>Pressão urbana</h3><p>Síntese da intensidade de crescimento urbano e do grau de ocupação de uma área.</p></article>
        <article class="info-card"><h3>Área consolidada</h3><p>Distrito com percentual urbanizado alto, indicando menor espaço físico para expansão horizontal.</p></article>
        <article class="info-card"><h3>Expansão recente</h3><p>Aumento expressivo da mancha urbana entre os recortes históricos analisados.</p></article>
        <article class="info-card"><h3>Normalização</h3><p>Transformação dos indicadores para escala comum de 0 a 100 antes de combiná-los.</p></article>
        <article class="info-card"><h3>Estimativa por interseção</h3><p>Distribuição aproximada de população e domicílios por proporção de área dos bairros dentro de cada distrito.</p></article>
        <article class="info-card"><h3>Mancha urbana</h3><p>Conjunto de polígonos que representa áreas ocupadas por usos urbanos em determinado ano.</p></article>
        <article class="info-card"><h3>Crescimento absoluto</h3><p>Diferença em km² entre a área urbanizada de 2024 e a área urbanizada de 1977 no mesmo distrito.</p></article>
        <article class="info-card"><h3>Percentual urbanizado</h3><p>Proporção da área total do distrito ocupada pela mancha urbana em cada recorte temporal.</p></article>
        <article class="info-card"><h3>Crescimento por mil habitantes</h3><p>Indicador que relaciona expansão territorial e população aproximada, permitindo comparar distritos de tamanhos diferentes.</p></article>
        <article class="info-card"><h3>Pressão potencial</h3><p>Leitura exploratória que aponta onde o crescimento urbano pode exigir maior atenção de infraestrutura, sem medir capacidade operacional da rede.</p></article>
        <article class="info-card"><h3>EPSG:31982</h3><p>Sistema SIRGAS 2000 / UTM zona 22S, usado porque trabalha em metros e permite calcular áreas com consistência.</p></article>
      </div></div></div>
    </div>

    <div id="tab-tabela" class="tab-panel">
      <div class="panel"><div class="panel-head"><h2 class="panel-title">Tabela síntese por distrito</h2><p class="panel-note">Nesta aba estão os números finais do painel em formato tabular, útil para conferência, citação em relatório e comparação rápida entre distritos.</p></div>
      <div class="plot-wrap table-wrap"><table id="summaryTable"></table></div></div>
    </div>
  </section>

  <footer class="footer">
    <h2>Referências e processamento</h2>
    <div class="footer-grid">
      <div class="footer-card"><strong>Autoria</strong><p>Caetano Ronan - UFSC.</p></div>
      <div class="footer-card"><strong>Fontes</strong><p>`sau_dist_san.zip`, manchas urbanas de 1977, 2002/2003 e 2024, e camada `gvw_bairros`.</p></div>
      <div class="footer-card"><strong>Processamento</strong><p>SIRGAS 2000 / UTM zona 22S, EPSG:31982. Interseções espaciais, áreas em km², normalização e índice composto.</p></div>
      <div class="footer-card"><strong>Complemento técnico</strong><p>As inspeções sanitárias foram separadas em painel próprio para preservar a leitura deste produto.</p></div>
    </div>
  </footer>
</main>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
const fmt = new Intl.NumberFormat('pt-BR', {{ maximumFractionDigits: 2 }});
const cssVar = name => getComputedStyle(document.body).getPropertyValue(name).trim();
const pastel = ['#c7b7e8', '#e7a9b2', '#f2b8a0', '#9eb5df', '#d4a4cf', '#b9bfdc'];
const barLine = {{ color: 'rgba(16,35,31,.28)', width: 1 }};
const chartConfig = name => ({{
  responsive: true,
  displayModeBar: true,
  displaylogo: false,
  toImageButtonOptions: {{ format: 'png', filename: name, height: 900, width: 1400, scale: 2 }}
}});
const layout = extra => ({{
  paper_bgcolor: '#ffffff',
  plot_bgcolor: '#ffffff',
  font: {{ family: 'Arial, sans-serif', color: '#10231f' }},
  margin: {{ l: 150, r: 80, t: 48, b: 86 }},
  xaxis: {{
    color: '#10231f',
    gridcolor: '#e6e0d8',
    zerolinecolor: '#cfc6bb',
    linecolor: '#b8aca0',
    tickfont: {{ color: '#10231f' }},
    titlefont: {{ color: '#10231f' }}
  }},
  yaxis: {{
    color: '#10231f',
    gridcolor: '#e6e0d8',
    zerolinecolor: '#cfc6bb',
    linecolor: '#b8aca0',
    tickfont: {{ color: '#10231f' }},
    titlefont: {{ color: '#10231f' }}
  }},
  legend: {{ font: {{ color: '#10231f' }} }},
  ...extra
}});
function orderedRows() {{
  return [...data.records].sort((a, b) => b.indice_pressao_urbana_saneamento - a.indice_pressao_urbana_saneamento);
}}
function pinClickLabel(chartId, formatter) {{
  const chart = document.getElementById(chartId);
  if (!chart || chart.dataset.pinClickReady) return;
  chart.dataset.pinClickReady = 'true';
  chart.on('plotly_click', event => {{
    const point = event.points && event.points[0];
    if (!point) return;
    const annotations = [...((chart.layout && chart.layout.annotations) || [])];
    annotations.push({{
      x: point.x,
      y: point.y,
      xref: 'x',
      yref: 'y',
      text: formatter(point),
      showarrow: true,
      arrowhead: 2,
      ax: 42,
      ay: -36,
      align: 'left',
      bgcolor: '#ffffff',
      bordercolor: '#b8aca0',
      borderwidth: 1,
      borderpad: 8,
      font: {{ color: '#10231f', size: 13 }}
    }});
    Plotly.relayout(chart, {{ annotations: annotations.slice(-6) }});
  }});
  chart.on('plotly_doubleclick', () => Plotly.relayout(chart, {{ annotations: [] }}));
}}
function renderCharts() {{
  const rows = orderedRows().reverse();
  const districts = rows.map(d => d.distrito_saneamento);
  Plotly.newPlot('evolucaoChart', [
    {{ type: 'bar', name: '1977', x: rows.map(d => d.urb1977_km2), y: districts, orientation: 'h', marker: {{ color: '#c7b7e8', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.urb1977_km2)}} km²`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2002/2003', x: rows.map(d => d.urb2002_2003_km2), y: districts, orientation: 'h', marker: {{ color: '#e7a9b2', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.urb2002_2003_km2)}} km²`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2024', x: rows.map(d => d.urb2024_km2), y: districts, orientation: 'h', marker: {{ color: '#9eb5df', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.urb2024_km2)}} km²`), textposition: 'outside', cliponaxis: false }}
  ], layout({{ barmode: 'group', xaxis: {{ title: 'Área urbanizada (km²)', gridcolor: cssVar('--grid') }}, yaxis: {{ automargin: true }}, legend: {{ orientation: 'h', y: 1.14 }} }}), chartConfig('evolucao_urbana_distritos_saneamento'));

  Plotly.newPlot('pressaoChart', [{{
    type: 'bar',
    x: rows.map(d => d.indice_pressao_urbana_saneamento),
    y: districts,
    orientation: 'h',
    marker: {{ color: rows.map((d, i) => pastel[i % pastel.length]), line: barLine }},
    opacity: .94,
    text: rows.map(d => `${{fmt.format(d.indice_pressao_urbana_saneamento)}}`),
    textposition: 'outside',
    cliponaxis: false,
    customdata: rows.map(d => [d.crescimento_1977_2024_km2, d.pct_urb_2024, d.crescimento_por_1000_hab_km2]),
    hovertemplate: '<b>%{{y}}</b><br>Índice: %{{x:.2f}}<br>Crescimento: %{{customdata[0]:.2f}} km²<br>% urbano 2024: %{{customdata[1]:.1f}}%<br>km²/mil hab.: %{{customdata[2]:.3f}}<extra></extra>'
  }}], layout({{ xaxis: {{ title: 'Índice de pressão urbana sobre saneamento (0-100)', gridcolor: cssVar('--grid'), range: [0, 112] }}, yaxis: {{ automargin: true }} }}), chartConfig('indice_pressao_urbana_saneamento'));
  pinClickLabel('pressaoChart', point => `<b>${{point.y}}</b><br>Índice: ${{fmt.format(point.x)}}<br>Cresc.: ${{fmt.format(point.customdata[0])}} km²<br>Urb. 2024: ${{fmt.format(point.customdata[1])}}%<br>km²/mil hab.: ${{fmt.format(point.customdata[2])}}`);

  Plotly.newPlot('percentualChart', [
    {{ type: 'bar', name: '1977', x: districts, y: rows.map(d => d.pct_urb_1977), marker: {{ color: '#c7b7e8', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.pct_urb_1977)}}%`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2002/2003', x: districts, y: rows.map(d => d.pct_urb_2002_2003), marker: {{ color: '#e7a9b2', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.pct_urb_2002_2003)}}%`), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: '2024', x: districts, y: rows.map(d => d.pct_urb_2024), marker: {{ color: '#9eb5df', line: barLine }}, opacity: .93, text: rows.map(d => `${{fmt.format(d.pct_urb_2024)}}%`), textposition: 'outside', cliponaxis: false }}
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
    inspecoes_html = f"""<!doctype html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Inspeções sanitárias e prioridade - Florianópolis</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
:root {{
  --bg: #f6f2ec; --panel: #ffffff; --ink: #10231f; --muted: #56665f;
  --grid: #ded8cf; --border: #d8cec2; --shadow: rgba(72,58,44,.10);
  --chart-bg: rgba(255,255,255,.76); --chart-border: rgba(216,206,194,.72);
  --teal: #2f8077; --hero-bg: linear-gradient(135deg, #d8f3ef 0%, #d9e9fb 55%, #e7def7 100%);
  --metric-a: linear-gradient(135deg, #d8f3ef 0%, #edf8f6 100%);
  --metric-b: linear-gradient(135deg, #d9e9fb 0%, #f0f6ff 100%);
  --metric-c: linear-gradient(135deg, #d7f0fa 0%, #eefaff 100%);
  --metric-d: linear-gradient(135deg, #dff3e3 0%, #f2fbf4 100%);
  --metric-e: linear-gradient(135deg, #e7def7 0%, #f8f3ff 100%);
}}
body[data-theme="dark"] {{
  --bg: #121817; --panel: #1b2422; --ink: #eef7f3; --muted: #b6c6bf;
  --grid: #34423d; --border: #3d4d47; --shadow: rgba(0,0,0,.34);
  --chart-bg: rgba(27,36,34,.72); --chart-border: rgba(61,77,71,.78);
  --teal: #84d8cc; --hero-bg: linear-gradient(135deg, #183a38 0%, #1b3552 58%, #2d2742 100%);
  --metric-a: linear-gradient(135deg, #1d3d3a 0%, #1b2c2a 100%);
  --metric-b: linear-gradient(135deg, #20344d 0%, #1b2530 100%);
  --metric-c: linear-gradient(135deg, #1c3b48 0%, #1a2a31 100%);
  --metric-d: linear-gradient(135deg, #213c2a 0%, #1b2a20 100%);
  --metric-e: linear-gradient(135deg, #302a49 0%, #252033 100%);
}}
* {{ box-sizing: border-box; }}
body {{ margin: 0; font-family: Arial, sans-serif; background: var(--bg); color: var(--ink); }}
main {{ max-width: 1440px; margin: 0 auto; padding: 34px; }}
header {{ display: flex; justify-content: space-between; gap: 24px; align-items: end; margin-bottom: 22px; background: var(--hero-bg); border: 1px solid var(--border); border-radius: 22px; padding: 32px; box-shadow: 0 10px 28px var(--shadow); }}
h1 {{ margin: 0; font-size: clamp(34px, 3.6vw, 56px); line-height: 1.05; letter-spacing: 0; }}
.lead {{ margin: 12px 0 0; color: var(--muted); font-size: 22px; line-height: 1.45; max-width: 980px; }}
.actions {{ display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }}
.button, button {{ border: 1px solid var(--border); background: var(--panel); color: var(--ink); border-radius: 999px; cursor: pointer; font: inherit; font-weight: 700; padding: 14px 20px; text-decoration: none; white-space: nowrap; }}
.button.primary {{ background: var(--teal); color: #fff; border-color: var(--teal); }}
body[data-theme="dark"] .button.primary {{ color: #10231f; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 18px; }}
.metric, .card {{ padding: 22px; border: 1px solid var(--border); border-radius: 10px; box-shadow: 0 10px 28px var(--shadow); }}
.metric:nth-child(5n+1), .card:nth-child(5n+1) {{ background: var(--metric-a); }}
.metric:nth-child(5n+2), .card:nth-child(5n+2) {{ background: var(--metric-b); }}
.metric:nth-child(5n+3), .card:nth-child(5n+3) {{ background: var(--metric-c); }}
.metric:nth-child(5n+4), .card:nth-child(5n+4) {{ background: var(--metric-d); }}
.metric:nth-child(5n+5), .card:nth-child(5n+5) {{ background: var(--metric-e); }}
.metric span {{ display: block; color: var(--muted); font-size: 15px; margin-bottom: 9px; }}
.metric strong {{ display: block; font-size: 30px; line-height: 1.08; }}
.tabs {{ display: grid; gap: 12px; }}
.tab-list {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; padding: 8px 0 12px; }}
.tab-button.active {{ background: var(--teal); color: #fff; border-color: var(--teal); }}
body[data-theme="dark"] .tab-button.active {{ color: #10231f; }}
.tab-panel {{ display: none; }}
.tab-panel.active {{ display: block; }}
.panel {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; box-shadow: 0 10px 28px var(--shadow); overflow: hidden; }}
.panel-head {{ margin: 20px 24px 0; padding: 18px; background: rgba(242,235,140,.32); border: 1px solid rgba(166,153,73,.18); border-radius: 12px; }}
.panel-title {{ margin: 0; font-size: 34px; line-height: 1.12; letter-spacing: 0; }}
.panel-note, .card p, .card li {{ color: var(--muted); font-size: 17px; line-height: 1.46; }}
.card code {{ display: block; margin: 10px 0; color: var(--muted); font-family: Consolas, Monaco, monospace; overflow-wrap: anywhere; }}
.plot-wrap {{ margin: 20px 24px 24px; padding: 18px; background: var(--chart-bg); border: 1px solid var(--chart-border); border-radius: 12px; }}
.chart {{ width: 100%; min-height: 620px; }}
.card-grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }}
.card h3 {{ margin: 0 0 10px; font-size: 22px; line-height: 1.16; }}
.card ul {{ margin: 0; padding-left: 20px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 15px; }}
th, td {{ padding: 11px 12px; border-bottom: 1px solid var(--border); text-align: left; }}
th {{ color: var(--ink); background: var(--panel); position: sticky; top: 0; }}
td {{ color: var(--muted); }}
footer {{ margin-top: 22px; padding: 22px; border: 1px solid var(--border); border-radius: 12px; background: var(--panel); color: var(--muted); line-height: 1.55; box-shadow: 0 10px 28px var(--shadow); }}
@media (max-width: 980px) {{ main {{ padding: 14px; }} header {{ flex-direction: column; align-items: stretch; }} .metrics, .tab-list, .card-grid {{ grid-template-columns: 1fr; }} .chart {{ min-height: 500px; }} }}
</style>
</head>
<body>
<main>
  <header>
    <div>
      <h1>Inspeções sanitárias e prioridade</h1>
      <p class="lead">Painel técnico complementar do capítulo de saneamento. Ele isola os registros de inspeção para não sobrecarregar o dashboard de pressão urbana.</p>
    </div>
    <div class="actions">
      <a class="button primary" href="dashboard_pressao_saneamento.html">Ver pressão urbana</a>
      <a class="button" href="../index.html">Voltar ao índice</a>
      <button id="theme-toggle" type="button">Modo escuro</button>
    </div>
  </header>
  <section class="metrics">
    <div class="metric"><span>Inspeções avaliadas</span><strong>{fmt_pt(stats["inspecoes_total"], 0)}</strong></div>
    <div class="metric"><span>Não conectado à rede</span><strong>{fmt_pt(stats["nao_conectado_total"], 0)}</strong></div>
    <div class="metric"><span>Tratamento local/fossa</span><strong>{fmt_pt(stats["tratamento_local_total"], 0)}</strong></div>
    <div class="metric"><span>Maior prioridade</span><strong>{stats["maior_prioridade"]}</strong></div>
  </section>
  <section class="tabs">
    <div class="tab-list" role="tablist">
      <button class="tab-button active" type="button" data-tab="tab-historia">Leitura</button>
      <button class="tab-button" type="button" data-tab="tab-escopo">Escopo da base</button>
      <button class="tab-button" type="button" data-tab="tab-inspecoes">Inspeções</button>
      <button class="tab-button" type="button" data-tab="tab-prioridade">Prioridade</button>
      <button class="tab-button" type="button" data-tab="tab-metodo">Metodologia</button>
      <button class="tab-button" type="button" data-tab="tab-glossario">Glossário</button>
      <button class="tab-button" type="button" data-tab="tab-tabela">Tabela</button>
    </div>
    <div id="tab-historia" class="tab-panel active"><div class="panel"><div class="panel-head"><h2 class="panel-title">Por que este painel foi separado?</h2><p class="panel-note">As inspeções têm uma lógica própria: elas mostram registros de fiscalização e indícios sanitários. Separar este painel preserva a leitura do produto principal e deixa a análise técnica mais clara.</p></div><div class="plot-wrap"><div class="card-grid">
      <article class="card"><h3>O que aparece aqui</h3><p>Registros agregados por distrito de saneamento: inadequação, não conexão à rede, conexão parcial, tratamento local/fossa, ligação pluvial irregular e problemas de caixa de gordura.</p></article>
      <article class="card"><h3>Como interpretar</h3><p>Os valores indicam ocorrências registradas nas inspeções. Eles ajudam a enxergar concentração de problemas, mas não substituem cadastro oficial de cobertura da rede.</p></article>
      <article class="card"><h3>Como fecha a história</h3><p>Este painel liga a expansão urbana à pergunta final de planejamento: onde o território cresceu e onde há mais sinais de pressão sanitária?</p></article>
    </div></div></div></div>
    <div id="tab-escopo" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Escopo da base de inspeções</h2><p class="panel-note">Nesta aba o leitor entende a base antes de interpretar os resultados: período coberto, tipos de imóveis inspecionados e principais programas/campanhas identificados nos registros.</p></div><div class="plot-wrap"><div class="card-grid">
      <article class="card"><h3>Período considerado</h3><p>Foram considerados {fmt_pt(stats["inspecoes_total"], 0)} registros de inspeção dentro dos distritos de saneamento, com datas válidas entre {stats["inspecoes_data_inicio"]} e {stats["inspecoes_data_fim"]}.</p></article>
      <article class="card"><h3>Perfil dos imóveis</h3><p>Principais categorias registradas: {stats["categorias_imoveis"]}.</p></article>
      <article class="card"><h3>Programas identificados</h3><p>Principais programas/campanhas com nome informado: {stats["programas_inspecao"]}.</p></article>
    </div></div><div class="plot-wrap"><div id="escopoAnosChart" class="chart"></div></div><div class="plot-wrap"><div id="escopoCategoriasChart" class="chart"></div></div><div class="plot-wrap"><div id="escopoProgramasChart" class="chart"></div></div></div></div>
    <div id="tab-inspecoes" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Registros sanitários por distrito</h2><p class="panel-note">Nesta aba o leitor encontra os principais tipos de ocorrência identificados nas inspeções. As barras agrupadas ajudam a comparar inadequações, não conexão à rede, conexão parcial e tratamento local/fossa entre os distritos.</p></div><div class="plot-wrap"><div id="inspecoesChart" class="chart"></div></div></div></div>
    <div id="tab-prioridade" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Prioridade integrada</h2><p class="panel-note">Nesta aba aparece o ranking sintético do painel técnico. O índice combina a pressão urbana já calculada com os registros de inspeção, destacando onde os sinais de demanda por investimento se acumulam. Clique em uma barra para fixar a informação antes de exportar em PNG; duplo clique limpa as marcações.</p></div><div class="plot-wrap"><div id="prioridadeChart" class="chart"></div></div></div></div>
    <div id="tab-metodo" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Metodologia</h2><p class="panel-note">Nesta aba estão as regras de classificação usadas nos textos das inspeções e a fórmula do índice de prioridade integrada. O objetivo é explicar como registros descritivos viraram indicadores comparáveis por distrito de saneamento.</p></div><div class="plot-wrap"><div class="card-grid">
      <article class="card"><h3>1. Cruzamento espacial</h3><p>Cada registro de inspeção foi cruzado com o polígono dos distritos de saneamento. Assim, cada ocorrência passa a contribuir para o distrito onde está localizada.</p><code>inspeção_distrito = inspeção ∩ distrito_saneamento</code><p>Registros fora dos distritos foram separados e não entram no ranking principal.</p></article>
      <article class="card"><h3>2. Texto analisado</h3><p>A classificação usa a combinação dos campos de situação e observação. Antes da busca, o texto é convertido para minúsculas e sem acentos, reduzindo falhas por grafia.</p><code>texto = situação_i + situação_e + observações</code><p>Essa etapa permite localizar termos como “não conectado”, “fossa” e “pluvial”.</p></article>
      <article class="card"><h3>3. Indícios de inadequação</h3><p>Foram contados registros com termos associados a problema, ausência, irregularidade, conexão parcial, não conexão, pluvial, fossa ou tratamento local.</p><code>inadequação = inadequada OR irregular OR ausência OR não conectado OR parcialmente OR pluvial OR fossa OR tratamento local</code><p>É uma contagem de indícios encontrados nas descrições.</p></article>
      <article class="card"><h3>4. Não conexão à rede</h3><p>Conta registros com menção direta a imóvel não conectado à rede de esgoto sanitário.</p><code>não_conectado = texto contém "não conectado a rede"</code><p>O resultado indica ocorrência registrada em inspeção, não cobertura oficial do sistema.</p></article>
      <article class="card"><h3>5. Conexão parcial</h3><p>Conta situações em que o texto indica conexão parcial à rede de esgoto sanitário.</p><code>conexão_parcial = texto contém "parcialmente a rede"</code><p>Esse indicador ajuda a identificar transições ou adequações incompletas.</p></article>
      <article class="card"><h3>6. Tratamento local/fossa</h3><p>Conta registros com menção a fossa, sistema local ou tratamento local.</p><code>tratamento_local = fossa OR sistema local OR tratamento local</code><p>Ele aproxima a dependência de soluções individuais ou não centralizadas.</p></article>
      <article class="card"><h3>7. Percentuais por distrito</h3><p>Além das contagens absolutas, o painel calcula a participação de cada tipo de ocorrência no total de inspeções do distrito.</p><code>%ocorrência = (ocorrência / inspeções_total) × 100</code><p>Isso evita comparar apenas números brutos entre distritos com quantidades diferentes de inspeções.</p></article>
      <article class="card"><h3>8. Normalização</h3><p>Os indicadores entram no índice em escala comum de 0 a 100, para que contagens e índices prévios possam ser combinados.</p><code>norm(x) = ((x - xmin) / (xmax - xmin)) × 100</code><p>O maior valor observado recebe 100 e o menor recebe 0.</p></article>
      <article class="card"><h3>9. Índice de prioridade</h3><p>O índice combina pressão urbana e registros sanitários. A pressão urbana recebe maior peso, seguida por inadequações, não conexão e tratamento local/fossa.</p><code>IPI = 0,35×norm(IPUS) + 0,25×norm(inadequações) + 0,20×norm(não conexão) + 0,20×norm(tratamento local/fossa)</code><p>Quanto maior o IPI, maior a prioridade exploratória para atenção pública.</p></article>
      <article class="card"><h3>10. Limite da análise</h3><p>O painel trabalha com inspeções e palavras-chave. Ele não substitui cadastro oficial de rede, ligações ativas, capacidade hidráulica, projetos executivos ou dados operacionais da concessionária.</p><code>resultado = leitura exploratória, não diagnóstico operacional</code><p>Essa cautela é essencial para comunicar bem o produto.</p></article>
      <article class="card"><h3>11. Uso recomendado</h3><p>Use o painel para localizar padrões, levantar hipóteses e orientar perguntas de planejamento: onde cresceram as demandas e onde as inspeções indicam maior atenção?</p><code>planejamento = urbanização + inspeções + prioridade territorial</code><p>A leitura deve apoiar discussão técnica, não substituir vistoria ou engenharia de rede.</p></article>
      <article class="card"><h3>12. Unidade de comparação</h3><p>Todas as estatísticas são agregadas por distrito de saneamento, mantendo coerência com o painel de pressão urbana.</p><code>unidade = Distrito Centro, Leste, Sul, Continente ou Norte</code><p>Isso amarra a história final à infraestrutura urbana.</p></article>
    </div></div></div></div>
    <div id="tab-glossario" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Glossário</h2><p class="panel-note">Nesta aba ficam os termos técnicos do painel de inspeções, para separar o que é registro fiscalizatório, indício sanitário e prioridade exploratória.</p></div><div class="plot-wrap"><div class="card-grid">
      <article class="card"><h3>Inspeção sanitária</h3><p>Registro de fiscalização ambiental/sanitária associado a uma edificação, imóvel ou situação observada em campo.</p></article>
      <article class="card"><h3>Situação da edificação</h3><p>Classificação geral do registro, como adequada, inadequada, irregular ou não inspecionada.</p></article>
      <article class="card"><h3>Indício textual</h3><p>Ocorrência identificada por palavras-chave nos campos descritivos da base, como “não conectado”, “fossa” ou “pluvial”.</p></article>
      <article class="card"><h3>Não conectado à rede</h3><p>Registro com menção a imóvel não conectado à rede de esgoto sanitário. É um indício, não um cadastro oficial de ligação.</p></article>
      <article class="card"><h3>Conexão parcial</h3><p>Situação em que o imóvel aparece como parcialmente conectado à rede de esgoto sanitário.</p></article>
      <article class="card"><h3>Tratamento local/fossa</h3><p>Registro com menção a fossa, sistema local ou tratamento local, indicando solução individual ou não centralizada.</p></article>
      <article class="card"><h3>Ligação pluvial irregular</h3><p>Indício de água pluvial conectada à rede de esgoto ou esgoto sanitário conectado à rede pluvial.</p></article>
      <article class="card"><h3>Caixa de gordura</h3><p>Elemento do sistema predial citado nas inspeções; ausência ou inadequação pode indicar problema no manejo de efluentes.</p></article>
      <article class="card"><h3>Prioridade integrada</h3><p>Índice de 0 a 100 que combina pressão urbana e registros sanitários para orientar comunicação e planejamento.</p></article>
      <article class="card"><h3>Leitura exploratória</h3><p>Interpretação usada para encontrar padrões e hipóteses. Ela não substitui laudo, projeto executivo ou base operacional da concessionária.</p></article>
      <article class="card"><h3>Distrito de saneamento</h3><p>Unidade territorial usada para agregar os registros e aproximar a leitura da organização espacial dos serviços de saneamento.</p></article>
      <article class="card"><h3>Normalização</h3><p>Conversão dos indicadores para escala comum antes de combiná-los no índice integrado.</p></article>
    </div></div></div></div>
    <div id="tab-tabela" class="tab-panel"><div class="panel"><div class="panel-head"><h2 class="panel-title">Tabela síntese</h2><p class="panel-note">Nesta aba o leitor encontra o resumo numérico por distrito de saneamento, reunindo as contagens principais e o índice de prioridade integrada.</p></div><div class="plot-wrap table-wrap"><table id="summaryTable"></table></div></div></div>
  </section>
  <footer><strong>Autoria:</strong> Caetano Ronan - UFSC. <strong>Fonte:</strong> `inspecoes_smmads_geoportal.zip`, `sau_dist_san.zip` e indicadores do painel de pressão urbana. Leitura exploratória para comunicação e planejamento, não diagnóstico operacional de rede.</footer>
</main>
<script>
const data = {json.dumps(payload, ensure_ascii=False)};
const fmt = new Intl.NumberFormat('pt-BR', {{ maximumFractionDigits: 2 }});
const cssVar = name => getComputedStyle(document.body).getPropertyValue(name).trim();
const colors = ['#c7b7e8', '#e7a9b2', '#f2b8a0', '#9eb5df', '#d4a4cf', '#b9bfdc'];
const barLine = {{ color: 'rgba(16,35,31,.28)', width: 1 }};
const config = name => ({{ responsive: true, displayModeBar: true, displaylogo: false, toImageButtonOptions: {{ format: 'png', filename: name, height: 900, width: 1400, scale: 2 }} }});
const layout = extra => ({{
  paper_bgcolor: '#ffffff',
  plot_bgcolor: '#ffffff',
  font: {{ family: 'Arial, sans-serif', color: '#10231f' }},
  margin: {{ l: 150, r: 80, t: 48, b: 86 }},
  xaxis: {{
    color: '#10231f',
    gridcolor: '#e6e0d8',
    zerolinecolor: '#cfc6bb',
    linecolor: '#b8aca0',
    tickfont: {{ color: '#10231f' }},
    titlefont: {{ color: '#10231f' }}
  }},
  yaxis: {{
    color: '#10231f',
    gridcolor: '#e6e0d8',
    zerolinecolor: '#cfc6bb',
    linecolor: '#b8aca0',
    tickfont: {{ color: '#10231f' }},
    titlefont: {{ color: '#10231f' }}
  }},
  legend: {{ font: {{ color: '#10231f' }} }},
  ...extra
}});
function rowsAsc(field) {{ return [...data.records].sort((a, b) => a[field] - b[field]); }}
function pinClickLabel(chartId, formatter) {{
  const chart = document.getElementById(chartId);
  if (!chart || chart.dataset.pinClickReady) return;
  chart.dataset.pinClickReady = 'true';
  chart.on('plotly_click', event => {{
    const point = event.points && event.points[0];
    if (!point) return;
    const annotations = [...((chart.layout && chart.layout.annotations) || [])];
    annotations.push({{
      x: point.x,
      y: point.y,
      xref: 'x',
      yref: 'y',
      text: formatter(point),
      showarrow: true,
      arrowhead: 2,
      ax: 42,
      ay: -36,
      align: 'left',
      bgcolor: '#ffffff',
      bordercolor: '#b8aca0',
      borderwidth: 1,
      borderpad: 8,
      font: {{ color: '#10231f', size: 13 }}
    }});
    Plotly.relayout(chart, {{ annotations: annotations.slice(-6) }});
  }});
  chart.on('plotly_doubleclick', () => Plotly.relayout(chart, {{ annotations: [] }}));
}}
function renderCharts() {{
  const scopeYears = data.scope.anos;
  Plotly.newPlot('escopoAnosChart', [{{
    type: 'bar',
    x: scopeYears.map(d => d.ano),
    y: scopeYears.map(d => d.registros),
    marker: {{ color: scopeYears.map((_, i) => colors[i % colors.length]), line: barLine }},
    opacity: .94,
    text: scopeYears.map(d => fmt.format(d.registros)),
    textposition: 'outside',
    cliponaxis: false,
    hovertemplate: '<b>%{{x}}</b><br>Inspeções: %{{y}}<extra></extra>'
  }}], layout({{
    margin: {{ l: 80, r: 50, t: 48, b: 80 }},
    xaxis: {{ title: 'Ano da inspeção', tickmode: 'linear', dtick: 1 }},
    yaxis: {{ title: 'Registros de inspeção' }},
    title: {{ text: 'Distribuição temporal das inspeções', font: {{ color: '#10231f', size: 20 }} }}
  }}), config('escopo_inspecoes_por_ano'));

  const scopeCategorias = [...data.scope.categorias].reverse();
  Plotly.newPlot('escopoCategoriasChart', [{{
    type: 'bar',
    x: scopeCategorias.map(d => d.registros),
    y: scopeCategorias.map(d => d.categoria),
    orientation: 'h',
    marker: {{ color: scopeCategorias.map((d, i) => colors[i % colors.length]), line: barLine }},
    opacity: .94,
    text: scopeCategorias.map(d => fmt.format(d.registros)),
    textposition: 'outside',
    cliponaxis: false
  }}], layout({{
    xaxis: {{ title: 'Registros' }},
    yaxis: {{ automargin: true }},
    title: {{ text: 'Perfil dos imóveis inspecionados', font: {{ color: '#10231f', size: 20 }} }}
  }}), config('escopo_perfil_imoveis'));

  const scopeProgramas = [...data.scope.programas].reverse();
  Plotly.newPlot('escopoProgramasChart', [{{
    type: 'bar',
    x: scopeProgramas.map(d => d.registros),
    y: scopeProgramas.map(d => d.programa),
    orientation: 'h',
    marker: {{ color: scopeProgramas.map((d, i) => colors[(i + 2) % colors.length]), line: barLine }},
    opacity: .94,
    text: scopeProgramas.map(d => fmt.format(d.registros)),
    textposition: 'outside',
    cliponaxis: false
  }}], layout({{
    xaxis: {{ title: 'Registros com programa informado' }},
    yaxis: {{ automargin: true }},
    title: {{ text: 'Programas e campanhas identificados', font: {{ color: '#10231f', size: 20 }} }}
  }}), config('escopo_programas_identificados'));

  const rows = rowsAsc('inspecoes_inadequadas_indicios');
  const y = rows.map(d => d.distrito_saneamento);
  Plotly.newPlot('inspecoesChart', [
    {{ type: 'bar', name: 'Indícios de inadequação', x: rows.map(d => d.inspecoes_inadequadas_indicios), y, orientation: 'h', marker: {{ color: colors[0], line: barLine }}, opacity: .92, text: rows.map(d => fmt.format(d.inspecoes_inadequadas_indicios)), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: 'Não conectado à rede', x: rows.map(d => d.nao_conectado_rede), y, orientation: 'h', marker: {{ color: colors[1], line: barLine }}, opacity: .92, text: rows.map(d => fmt.format(d.nao_conectado_rede)), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: 'Conexão parcial', x: rows.map(d => d.conectado_parcial_rede), y, orientation: 'h', marker: {{ color: colors[2], line: barLine }}, opacity: .92, text: rows.map(d => fmt.format(d.conectado_parcial_rede)), textposition: 'outside', cliponaxis: false }},
    {{ type: 'bar', name: 'Tratamento local/fossa', x: rows.map(d => d.tratamento_local_fossa), y, orientation: 'h', marker: {{ color: colors[3], line: barLine }}, opacity: .92, text: rows.map(d => fmt.format(d.tratamento_local_fossa)), textposition: 'outside', cliponaxis: false }}
  ], layout({{ barmode: 'group', xaxis: {{ title: 'Número de registros', gridcolor: cssVar('--grid') }}, yaxis: {{ automargin: true }}, legend: {{ orientation: 'h', y: 1.16 }} }}), config('inspecoes_sanitarias_distritos'));
  const pr = rowsAsc('indice_prioridade_investimento');
  Plotly.newPlot('prioridadeChart', [{{
    type: 'bar', x: pr.map(d => d.indice_prioridade_investimento), y: pr.map(d => d.distrito_saneamento), orientation: 'h',
    marker: {{ color: pr.map((d, i) => colors[i % colors.length]), line: barLine }}, opacity: .94, text: pr.map(d => fmt.format(d.indice_prioridade_investimento)), textposition: 'outside', cliponaxis: false,
    customdata: pr.map(d => [d.indice_pressao_urbana_saneamento, d.inspecoes_inadequadas_indicios, d.nao_conectado_rede, d.tratamento_local_fossa]),
    hovertemplate: '<b>%{{y}}</b><br>Prioridade: %{{x:.2f}}<br>Pressão urbana: %{{customdata[0]:.2f}}<br>Inadequações: %{{customdata[1]}}<br>Não conectado: %{{customdata[2]}}<br>Tratamento local/fossa: %{{customdata[3]}}<extra></extra>'
  }}], layout({{ xaxis: {{ title: 'Índice de prioridade integrada (0-100)', gridcolor: cssVar('--grid'), range: [0, 112] }}, yaxis: {{ automargin: true }} }}), config('prioridade_integrada_saneamento'));
  pinClickLabel('prioridadeChart', point => `<b>${{point.y}}</b><br>Prioridade: ${{fmt.format(point.x)}}<br>Pressão urbana: ${{fmt.format(point.customdata[0])}}<br>Inadequações: ${{fmt.format(point.customdata[1])}}<br>Não conectado: ${{fmt.format(point.customdata[2])}}<br>Trat. local/fossa: ${{fmt.format(point.customdata[3])}}`);
}}
function renderTable() {{
  const head = ['Distrito', 'Inspeções', 'Inadequações', 'Não conectado', 'Conexão parcial', 'Tratamento local/fossa', 'Prioridade'];
  const body = [...data.records].sort((a,b)=>b.indice_prioridade_investimento-a.indice_prioridade_investimento).map(d => `<tr><td>${{d.distrito_saneamento}}</td><td>${{fmt.format(d.inspecoes_total)}}</td><td>${{fmt.format(d.inspecoes_inadequadas_indicios)}}</td><td>${{fmt.format(d.nao_conectado_rede)}}</td><td>${{fmt.format(d.conectado_parcial_rede)}}</td><td>${{fmt.format(d.tratamento_local_fossa)}}</td><td>${{fmt.format(d.indice_prioridade_investimento)}}</td></tr>`).join('');
  document.getElementById('summaryTable').innerHTML = `<thead><tr>${{head.map(h => `<th>${{h}}</th>`).join('')}}</tr></thead><tbody>${{body}}</tbody>`;
}}
function applyTheme(theme) {{ document.body.dataset.theme = theme; document.getElementById('theme-toggle').textContent = theme === 'dark' ? 'Modo claro' : 'Modo escuro'; localStorage.setItem('urbanizacao-inspecoes-theme-floripa', theme); window.setTimeout(renderCharts, 40); }}
document.querySelectorAll('.tab-button').forEach(button => button.addEventListener('click', () => {{ document.querySelectorAll('.tab-button').forEach(item => item.classList.toggle('active', item === button)); document.querySelectorAll('.tab-panel').forEach(panel => panel.classList.toggle('active', panel.id === button.dataset.tab)); window.setTimeout(() => ['escopoAnosChart','escopoCategoriasChart','escopoProgramasChart','inspecoesChart','prioridadeChart'].forEach(id => {{ const el=document.getElementById(id); if (el) Plotly.Plots.resize(el); }}), 80); }}));
document.getElementById('theme-toggle').addEventListener('click', () => applyTheme(document.body.dataset.theme === 'dark' ? 'light' : 'dark'));
renderTable();
applyTheme(localStorage.getItem('urbanizacao-inspecoes-theme-floripa') || 'light');
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html, encoding="utf-8")
    OUT_INSPECOES_HTML.write_text(inspecoes_html, encoding="utf-8")
    print(OUT_HTML)
    print(OUT_INSPECOES_HTML)
    print(OUT_CSV)


if __name__ == "__main__":
    main()
