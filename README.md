# Urbanização de Florianópolis

Dashboard e webmap para análise da expansão urbana de Florianópolis a partir de camadas vetoriais do Geoportal.

O produto compara três recortes temporais:

- 1977: mancha urbana histórica;
- 2002/2003: mancha urbana intermediária;
- 2024: áreas classificadas como `Urbanizado`.

## Arquivos Principais

- `index.html`: página inicial do produto, com links para os dashboards e para o webmap independente.
- `dashboard/dashboard_urbanizacao_webmap.html`: dashboard principal com cartões, abas, webmap e gráficos Plotly.
- `dashboard/dashboard_comparativo_socio_urbano.html`: dashboard complementar que cruza crescimento urbano por bairro com população, densidade e domicílios.
- `dashboard/dashboard_pressao_saneamento.html`: dashboard complementar sobre pressão urbana nos distritos de saneamento.
- `dashboard/dashboard_inspecoes_saneamento.html`: painel técnico complementar com inspeções sanitárias e prioridade integrada.
- `dashboard/webmap_manchas_urbanas.html`: webmap isolado para abrir em outra aba ou usar em apresentação.
- `dashboard/urbanizacao_webmap_data.js`: dados GeoJSON e estatísticas usados pelos HTMLs.
- `scripts/gerar_dashboard_urbanizacao_webmap.py`: script que gera os CSVs, o arquivo JS e os HTMLs.
- `scripts/gerar_dashboard_comparativo_socio_urbano.py`: script que gera o dashboard socio-urbano e a tabela comparativa por bairro.
- `scripts/gerar_dashboard_pressao_saneamento.py`: script que cruza manchas urbanas, bairros e distritos de saneamento.
- `PUBLICACAO_GITHUB_PAGES.md`: roteiro para criar o repositório, enviar ao GitHub e ativar o GitHub Pages.
- `.nojekyll`: arquivo usado para publicar o site estático no GitHub Pages sem processamento Jekyll.

## Estrutura Da Pasta

```text
urbanizacao_florianopolis/
  dados_brutos/
    areas_urbanizadas_2024/
    gvw_bairros/
    mancha_urb1977/
    mancha_urb2002.zip
    censo2022_setores_dd.zip
    gvw_bairros.zip
    inspecoes_smmads_geoportal.zip
    sau_dist_san.zip
  dashboard/
    dashboard_urbanizacao_webmap.html
    dashboard_comparativo_socio_urbano.html
    dashboard_inspecoes_saneamento.html
    dashboard_pressao_saneamento.html
    webmap_manchas_urbanas.html
    urbanizacao_webmap_data.js
  resultados/
    areas_urbanizadas_totais_1977_2002_2024.csv
    comparativo_socio_urbano_bairros.csv
    inspecoes_saneamento_por_distrito.csv
    pressao_urbana_distritos_saneamento.csv
    classes_uso_2024.csv
    taxas_urbanizacao_1977_2002_2024.csv
    urbanizacao_por_bairro_1977_2002_2024.csv
    urbanizacao_por_regiao_1977_2002_2024.csv
  scripts/
    gerar_dashboard_comparativo_socio_urbano.py
    gerar_dashboard_pressao_saneamento.py
    gerar_dashboard_urbanizacao_webmap.py
  .gitignore
  .nojekyll
  PUBLICACAO_GITHUB_PAGES.md
  README.md
  requirements.txt
```

## Dados Utilizados

As camadas usadas no processamento principal são:

- `mancha_urb1977`: polígonos da mancha urbana de 1977.
- `mancha_urb2002.zip`: polígonos da mancha urbana intermediária.
- `areas_urbanizadas_2024`: classificação territorial de 2024.
- `gvw_bairros`: limites dos bairros e regiões administrativas.
- `sau_dist_san.zip`: distritos de saneamento, com cinco unidades territoriais: Centro, Leste, Sul, Continente e Norte.
- `inspecoes_smmads_geoportal.zip`: registros de inspeções sanitárias/ambientais com situação da edificação, categoria do imóvel, situação identificada e observações.

Todas as camadas principais estão em `SIRGAS 2000 / UTM zone 22S`, EPSG:31982. Como é um sistema projetado em metros, ele permite calcular áreas diretamente em m² e converter para km².

## Dashboard De Pressão Urbana Em Saneamento

O arquivo `dados_brutos/sau_dist_san.zip` contém cinco distritos de saneamento:

- Distrito Centro;
- Distrito Leste;
- Distrito Sul;
- Distrito Continente;
- Distrito Norte.

Essa camada permite contar uma terceira história territorial: a expansão urbana vista pela ótica da infraestrutura urbana e do saneamento. Em vez de observar apenas bairros e regiões administrativas, o dashboard pergunta quais distritos de saneamento receberam maior crescimento da mancha urbana e quais já estavam próximos da saturação urbana.

Prévia estatística por distrito:

| Distrito de saneamento | Área total | Urb. 1977 | Urb. 2002/2003 | Urb. 2024 | Cresc. 1977-2024 | % urb. 2024 |
|---|---:|---:|---:|---:|---:|---:|
| Distrito Norte | 157,62 km² | 10,58 km² | 28,67 km² | 44,47 km² | +33,89 km² | 28,21% |
| Distrito Sul | 140,24 km² | 9,16 km² | 19,86 km² | 32,66 km² | +23,51 km² | 23,29% |
| Distrito Leste | 106,62 km² | 9,53 km² | 13,91 km² | 17,20 km² | +7,67 km² | 16,13% |
| Distrito Centro | 11,63 km² | 8,64 km² | 10,02 km² | 10,02 km² | +1,38 km² | 86,17% |
| Distrito Continente | 11,78 km² | 11,38 km² | 11,18 km² | 11,59 km² | +0,21 km² | 98,40% |

Leitura inicial:

- Norte e Sul concentram a maior expansão absoluta entre 1977 e 2024.
- Centro e Continente aparecem como áreas historicamente consolidadas, com percentual urbanizado muito alto em 2024.
- Leste possui crescimento intermediário e pode ser analisado junto com bairros como Rio Vermelho e áreas de expansão mais recente.
- O dashboard `dashboard/dashboard_pressao_saneamento.html` transforma essa leitura em gráficos Plotly, metodologia, glossário e tabela síntese. As inspeções sanitárias ficam separadas em `dashboard/dashboard_inspecoes_saneamento.html`, para não saturar a leitura principal.

### Fechamento Da Narrativa

O produto foi organizado como uma sequência de quatro leituras:

1. Expansão da mancha urbana: mostra quanto Florianópolis cresceu entre 1977 e 2024.
2. Webmap: mostra onde esse crescimento ocorreu no território.
3. Comparativo socio-urbano: relaciona crescimento, população, densidade e domicílios.
4. Pressão urbana e saneamento: cruza crescimento urbano com distritos de saneamento; a leitura técnica separada cruza esse resultado com registros de inspeção.

Esse último painel fecha a história porque transforma a expansão urbana em pergunta de planejamento: onde o crescimento territorial, a ocupação consolidada e os indícios sanitários sugerem maior necessidade de atenção pública?

### Índice Exploratório De Pressão Urbana

O índice combina três variáveis normalizadas entre 0 e 100:

```text
N(x) = ((x - xmin) / (xmax - xmin)) × 100
```

```text
IPUS = 0,45 × N(ΔA_1977_2024)
     + 0,35 × N(%urb_2024)
     + 0,20 × N(ΔA_1977_2024 por 1.000 habitantes)
```

Onde:

- `ΔA_1977_2024` representa o crescimento absoluto da mancha urbana no distrito;
- `%urb_2024` representa o percentual do distrito ocupado por área urbanizada em 2024;
- `ΔA_1977_2024 por 1.000 habitantes` aproxima a pressão territorial relativa à população estimada.

### Índice Integrado De Prioridade

Com a camada `inspecoes_smmads_geoportal.zip`, o dashboard também calcula um índice integrado de prioridade:

```text
IPI = 0,35 × N(IPUS)
    + 0,25 × N(inspeções com indícios de inadequação)
    + 0,20 × N(registros de não conexão à rede)
    + 0,20 × N(registros de tratamento local/fossa)
```

Os registros foram classificados por busca textual nos campos `situacao_e`, `situacao_i` e `observacoe`.

```text
Indícios de inadequação = registros com termos como inadequada, irregular, ausência,
não conectado, parcialmente, pluvial, tratamento local ou fossa.
```

```text
Tratamento local/fossa = registros com menção a fossa, sistema local ou tratamento local.
```

Esse índice não substitui cadastro operacional de rede, ligações ou capacidade do sistema. Ele serve como leitura exploratória para indicar onde a pressão urbana e os registros sanitários se sobrepõem.

## Dashboard De Inspeções Sanitárias

O arquivo `dashboard/dashboard_inspecoes_saneamento.html` foi separado do painel de pressão urbana para evitar excesso de informação em uma única tela. Ele funciona como painel técnico complementar: enquanto o dashboard de pressão mostra a relação entre urbanização e distritos de saneamento, este painel detalha os registros de inspeção sanitária/ambiental.

### Escopo Da Base

Foram considerados apenas registros de inspeção localizados dentro dos distritos de saneamento. A base final possui:

| Indicador | Valor |
|---|---:|
| Registros de inspeção válidos | 65.024 |
| Data inicial | 21/03/2011 |
| Data final | 25/01/2025 |
| Distritos avaliados | 5 |

A aba `Escopo da base` mostra três leituras de contexto:

- distribuição temporal das inspeções por ano;
- perfil dos imóveis inspecionados;
- principais programas ou campanhas identificados.

### Perfil Dos Imóveis Inspecionados

Principais categorias registradas:

| Categoria | Registros |
|---|---:|
| Unifamiliar | 24.832 |
| Sem classificação | 20.449 |
| Multifamiliar | 12.405 |
| Comercial | 4.068 |

Essa leitura ajuda a entender a composição da base antes de interpretar os indicadores sanitários. Por exemplo, uma concentração maior de imóveis unifamiliares pode indicar uma lógica diferente de atendimento, fiscalização e ligação predial em relação a áreas multifamiliares ou comerciais.

### Programas E Campanhas Identificados

Principais programas/campanhas com nome informado:

| Programa/Campanha | Registros |
|---|---:|
| FSLNR | 16.018 |
| Trato pela Lagoa | 4.283 |
| SANEAR | 3.752 |
| TPC | 1.684 |
| Trato pela Costa Norte | 189 |

Esses campos ajudam a interpretar a origem institucional de parte dos registros. A análise considera os programas como contexto da inspeção, não como medida direta de cobertura de rede.

### Indicadores Do Painel De Inspeções

O painel calcula, por distrito de saneamento:

- total de inspeções;
- registros classificados como adequados;
- registros com indícios de inadequação;
- registros com menção a não conexão à rede;
- registros com menção a conexão parcial;
- registros com menção a tratamento local ou fossa;
- registros com menção a ligação pluvial irregular;
- registros com menção a problema de caixa de gordura;
- índice integrado de prioridade para investimento.

As classificações são obtidas por busca textual nos campos descritivos das inspeções. Por isso, o resultado deve ser lido como indício técnico exploratório, não como cadastro oficial de ligações, rede instalada ou capacidade operacional do sistema.

## Observação Sobre 2002/2003

O arquivo baixado se chama `mancha_urb2002.zip`, mas sua tabela interna possui o campo `refname` com valor `2003`. Por isso, o dashboard identifica essa camada como `2002/2003` até confirmação da fonte original.

## Filtro Aplicado Em 2024

A camada `areas_urbanizadas_2024` contém diferentes classes, incluindo:

- `Urbanizado`;
- `Não Urbanizado`;
- `Corpos d'água`.

Para comparar mancha urbana entre os anos, o processamento considera somente:

```text
tipo = Urbanizado
```

Esse filtro evita comparar a mancha urbana de 1977 e 2002/2003 com a área total da camada de 2024.

## Indicadores Calculados

### Área Urbanizada Total

Para cada ano, as geometrias urbanas são dissolvidas em uma única geometria e a área é calculada em km²:

```text
Aurb(ano) = área(união das geometrias urbanas do ano) / 1.000.000
```

### Área Urbanizada Por Bairro

Para cada bairro, calcula-se a interseção entre o limite do bairro e a mancha urbana de cada ano:

```text
Aurb_bairro(ano) = área(bairro ∩ mancha urbana ano) / 1.000.000
```

### Crescimento Absoluto

Diferença entre a área urbanizada final e inicial:

```text
ΔA = Aurb(ano final) - Aurb(ano inicial)
```

No dashboard, o crescimento principal usa:

```text
ΔA_1977_2024 = Aurb(2024) - Aurb(1977)
```

### Taxa Média Anual Linear

Média simples de crescimento por ano:

```text
Tlinear = ΔA / número de anos do período
```

Exemplo:

```text
Tlinear_1977_2024 = (Aurb_2024 - Aurb_1977) / 47
```

### Taxa Composta Anual

Taxa percentual anual equivalente ao crescimento acumulado no período:

```text
TCAC = ((Afinal / Ainicial)^(1 / anos) - 1) × 100
```

### Percentual Urbanizado

Proporção da área territorial ocupada pela mancha urbana:

```text
%urb = (Aurb_unidade / área_total_unidade) × 100
```

Onde `unidade` pode ser bairro ou região administrativa.

## Resultados Principais

Áreas urbanizadas totais:

| Ano | Área urbanizada |
|---|---:|
| 1977 | 49,42 km² |
| 2002/2003 | 83,80 km² |
| 2024 | 116,29 km² |

Taxas:

| Período | Crescimento | Média anual | Taxa composta anual |
|---|---:|---:|---:|
| 1977 a 2002/2003 | +34,38 km² | +1,38 km²/ano | 2,14% ao ano |
| 2002/2003 a 2024 | +32,48 km² | +1,48 km²/ano | 1,50% ao ano |
| 1977 a 2024 | +66,87 km² | +1,42 km²/ano | 1,84% ao ano |

Maiores crescimentos por bairro entre 1977 e 2024:

| Bairro | Crescimento |
|---|---:|
| Campeche | +8,88 km² |
| Rio Vermelho | +7,74 km² |
| Ingleses | +6,30 km² |
| Rio Tavares | +3,38 km² |
| Carianos | +3,21 km² |

## Dashboard Comparativo Socio-Urbano

O arquivo `dashboard/dashboard_comparativo_socio_urbano.html` é um segundo painel, separado do dashboard principal, criado para evitar poluição visual e permitir uma leitura estatística mais direta entre urbanização e indicadores populacionais.

Ele utiliza como base:

- `resultados/urbanizacao_por_bairro_1977_2002_2024.csv`;
- camada `dados_brutos/gvw_bairros`, com população estimada, densidade, domicílios, média de moradores, distrito e região administrativa.

### Objetivo Do Comparativo

O painel responde a uma pergunta exploratória:

```text
Os bairros que mais cresceram em área urbanizada também concentram maior população,
maior densidade e maior número de domicílios?
```

### Indicadores Socio-Urbanos

**Crescimento por mil habitantes**

```text
C1000 = (ΔA / população_estimada) × 1.000
```

**Área urbanizada de 2024 por mil habitantes**

```text
A1000 = (Aurb_2024 / população_estimada) × 1.000
```

**Habitantes por km² urbanizado em 2024**

```text
HabUrb = população_estimada / Aurb_2024
```

**Domicílios por km² urbanizado em 2024**

```text
DomUrb = domicílios_estimados / Aurb_2024
```

**Crescimento relativo 1977-2024**

```text
Crel = (ΔA_1977_2024 / Aurb_1977) × 100
```

**Correlação de Pearson**

```text
r = cov(X,Y) / (σX × σY)
```

No dashboard comparativo, a correlação é usada para comparar população estimada, densidade populacional, crescimento urbano e percentual urbanizado em 2024.

### Perfis Socio-Urbanos

Os bairros são classificados por uma regra de mediana:

```text
alta_expansão = ΔA_bairro >= mediana(ΔA)
alta_densidade = densidade_bairro >= mediana(densidade)
```

A combinação gera quatro perfis:

- alta expansão e alta densidade;
- alta expansão e baixa densidade;
- baixa expansão e alta densidade;
- baixa expansão e baixa densidade.

## Como Os Arquivos São Gerados

O script executa as seguintes etapas:

1. Lê as camadas vetoriais em `dados_brutos/`.
2. Remove geometrias nulas ou vazias.
3. Valida geometrias com `shapely.validation.make_valid`.
4. Filtra a camada de 2024 para manter apenas `tipo = Urbanizado`.
5. Dissolve as geometrias urbanas por ano usando `unary_union`.
6. Calcula a área total urbanizada para 1977, 2002/2003 e 2024.
7. Intersecta cada mancha urbana com os bairros.
8. Agrega resultados por região administrativa.
9. Exporta tabelas CSV para `resultados/`.
10. Simplifica geometrias para webmap.
11. Gera `urbanizacao_webmap_data.js`.
12. Gera o dashboard principal e o webmap isolado.

O script complementar `scripts/gerar_dashboard_comparativo_socio_urbano.py` executa estas etapas:

1. Lê a tabela `urbanizacao_por_bairro_1977_2002_2024.csv`.
2. Lê a camada `gvw_bairros`.
3. Une os indicadores urbanos aos campos populacionais por nome do bairro.
4. Calcula crescimento por mil habitantes.
5. Calcula área urbanizada por mil habitantes.
6. Calcula habitantes por km² urbanizado.
7. Calcula domicílios por km² urbanizado.
8. Calcula crescimento relativo em relação a 1977.
9. Calcula correlações de Pearson.
10. Classifica os bairros em perfis socio-urbanos por mediana.
11. Exporta `resultados/comparativo_socio_urbano_bairros.csv`.
12. Gera `dashboard/dashboard_comparativo_socio_urbano.html`.

O script complementar `scripts/gerar_dashboard_pressao_saneamento.py` executa estas etapas:

1. Lê a camada `sau_dist_san.zip`.
2. Lê as manchas urbanas de 1977, 2002/2003 e 2024.
3. Filtra 2024 para manter apenas `tipo = Urbanizado`.
4. Intersecta cada mancha urbana com os distritos de saneamento.
5. Calcula área urbanizada e percentual urbanizado por distrito.
6. Intersecta bairros e distritos para aproximar população, domicílios e densidade por proporção de área.
7. Calcula crescimento absoluto por distrito.
8. Calcula crescimento urbano por 1.000 habitantes.
9. Normaliza os indicadores e calcula o índice exploratório de pressão urbana em saneamento.
10. Lê `inspecoes_smmads_geoportal.zip`.
11. Classifica registros textuais com indícios de inadequação, não conexão à rede, conexão parcial, tratamento local/fossa, ligação pluvial irregular e problemas de caixa de gordura.
12. Agrega as inspeções por distrito de saneamento.
13. Calcula o índice integrado de prioridade.
14. Exporta `resultados/pressao_urbana_distritos_saneamento.csv`.
15. Exporta `resultados/inspecoes_saneamento_por_distrito.csv`.
16. Gera `dashboard/dashboard_pressao_saneamento.html`.
17. Gera `dashboard/dashboard_inspecoes_saneamento.html`.

## Como Regenerar O Dashboard

Instale as dependências:

```bash
pip install -r requirements.txt
```

Na raiz desta pasta, execute:

```bash
python scripts/gerar_dashboard_urbanizacao_webmap.py
```

Para regenerar o dashboard comparativo socio-urbano, execute:

```bash
python scripts/gerar_dashboard_comparativo_socio_urbano.py
```

Para regenerar o dashboard de pressão urbana em saneamento, execute:

```bash
python scripts/gerar_dashboard_pressao_saneamento.py
```

O script atualiza:

- `dashboard/dashboard_urbanizacao_webmap.html`
- `dashboard/webmap_manchas_urbanas.html`
- `dashboard/urbanizacao_webmap_data.js`
- `resultados/*.csv`

O script comparativo atualiza:

- `dashboard/dashboard_comparativo_socio_urbano.html`
- `resultados/comparativo_socio_urbano_bairros.csv`

O script de saneamento atualiza:

- `dashboard/dashboard_pressao_saneamento.html`
- `dashboard/dashboard_inspecoes_saneamento.html`
- `resultados/pressao_urbana_distritos_saneamento.csv`
- `resultados/inspecoes_saneamento_por_distrito.csv`

## Visualização

Abra o dashboard principal:

```text
dashboard/dashboard_urbanizacao_webmap.html
```

Abra apenas o webmap:

```text
dashboard/webmap_manchas_urbanas.html
```

Abra o dashboard comparativo socio-urbano:

```text
dashboard/dashboard_comparativo_socio_urbano.html
```

Abra o dashboard de pressão urbana em saneamento:

```text
dashboard/dashboard_pressao_saneamento.html
```

Abra o painel técnico de inspeções sanitárias:

```text
dashboard/dashboard_inspecoes_saneamento.html
```

Os gráficos são feitos com Plotly e permitem exportação em PNG pelo botão de câmera da barra de ferramentas.

## Dependências

As dependências mínimas estão em `requirements.txt`:

```text
geopandas
pandas
shapely
```

O dashboard usa bibliotecas via CDN:

- Plotly;
- Leaflet;
- OpenStreetMap como mapa base.

Portanto, os HTMLs precisam de internet para carregar bibliotecas e mapa base. Os dados calculados ficam locais em `urbanizacao_webmap_data.js`.

## Limitações E Cuidados

- A comparação depende da compatibilidade conceitual entre as camadas de 1977, 2002/2003 e 2024.
- A camada intermediária deve ser citada como `2002/2003` enquanto houver divergência entre nome do arquivo e atributo interno.
- A camada de 2024 foi filtrada por `tipo = Urbanizado`; usar a camada inteira inflaria a área, pois inclui áreas não urbanizadas e corpos d'água.
- Os valores por bairro dependem do limite atual dos bairros usado em `gvw_bairros`.

## Frase-Síntese

Entre 1977 e 2024, a mancha urbana de Florianópolis passou de aproximadamente 49,4 km² para 116,3 km², um aumento de 66,9 km². A expansão foi mais expressiva nas regiões Norte, Sul e Leste da Ilha, com destaque para Campeche, Rio Vermelho e Ingleses.
