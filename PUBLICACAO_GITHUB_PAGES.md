# Publicação No GitHub Pages

Este repositório foi organizado para publicação como site estático no GitHub Pages.

## Entrada Do Site

O arquivo principal é:

```text
index.html
```

Ele direciona para quatro produtos:

- `dashboard/dashboard_urbanizacao_webmap.html`
- `dashboard/dashboard_comparativo_socio_urbano.html`
- `dashboard/dashboard_pressao_saneamento.html`
- `dashboard/webmap_manchas_urbanas.html`

## Arquivos Que Devem Subir

Subir:

- `index.html`
- `.nojekyll`
- `.gitignore`
- `README.md`
- `PUBLICACAO_GITHUB_PAGES.md`
- `requirements.txt`
- `dashboard/`
- `resultados/`
- `scripts/`
- `dados_brutos/`
- `webmap_manchas_urbanas_dashboard.png`
- `webmap_manchas_urbanas_florianopolis.png`

Não subir:

- `scripts/__pycache__/`
- arquivos `*.pyc`
- PNGs duplicados gerados por download, como `webmap_manchas_urbanas_dashboard (1).png`
- PNGs duplicados gerados por download, como `webmap_manchas_urbanas_florianopolis (2).png`

## Comandos Para Criar O Repositório Local

Na pasta `urbanizacao_florianopolis`:

```bash
git init
git add .
git commit -m "Publica produto de urbanizacao de Florianopolis"
```

## Comandos Para Enviar Ao GitHub

Crie um repositório vazio no GitHub, por exemplo:

```text
urbanizacao-florianopolis
```

Depois, na pasta local:

```bash
git branch -M main
git remote add origin https://github.com/caetanoronan/urbanizacao-florianopolis.git
git push -u origin main
```

## Ativar GitHub Pages

No GitHub:

1. Abra o repositório.
2. Acesse `Settings`.
3. Acesse `Pages`.
4. Em `Build and deployment`, selecione `Deploy from a branch`.
5. Em `Branch`, selecione `main`.
6. Em pasta, selecione `/root`.
7. Clique em `Save`.

Depois da publicação, a página deve ficar em:

```text
https://caetanoronan.github.io/urbanizacao-florianopolis/
```

## Regenerar Os Produtos

Para atualizar o dashboard principal e o webmap:

```bash
python scripts/gerar_dashboard_urbanizacao_webmap.py
```

Para atualizar o dashboard comparativo socio-urbano:

```bash
python scripts/gerar_dashboard_comparativo_socio_urbano.py
```

Para atualizar o dashboard de pressão urbana em saneamento:

```bash
python scripts/gerar_dashboard_pressao_saneamento.py
```
