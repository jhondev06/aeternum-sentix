# Deploy no Render (VPS) — Guia Prático

Este guia explica como colocar o Sentix (API + dashboard) online usando Render (VPS Docker), facilitando o acesso de usuários como seu amigo economista.

## O que será publicado
- API FastAPI (porta 8000)
- Dashboard Streamlit (porta 8501) — opcional em outro serviço
- Dados e modelo persistem em disco (pasta `data/` e `outputs/`)

## Pré-requisitos
- Conta no Render
- Repositório com este projeto (contendo `sentix/` e `Dockerfile`)
- Python e Dockerfile já configurados (o projeto já tem Dockerfile)

## Observações importantes
- FinBERT baixa o modelo na primeira execução. O Dockerfile já chama `init_model.py` no build para gerar dados demo e treinar o modelo, o que ajuda a reduzir cold start.
- Use disco persistente para `data/` e `outputs/`.
- Autenticação básica na API (admin/sentix123) — altere em `config.yml`.

## Passo a passo

1) Conectar o repositório
- No Render, crie um novo serviço do tipo **Web**.
- Selecione a opção **Docker**.

2) Configurar build e start
- Build Command: `docker build -t sentix-api .`
- Start Command: `uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}`
- Health Check Path: `/health`

3) Variáveis de ambiente
- `PORT=8000`
- `PYTHONUNBUFFERED=1`
- (Opcional) `HF_HOME=/app/data/hfcache` para cache do HuggingFace dentro de disco persistente

4) Disco persistente
- Nome: `sentix-data`
- MountPath: `/app/data`
- Tamanho: 1GB (ajuste conforme o uso)

5) Deploy
- Render fará o build do Docker, executará `init_model.py` (gera demo + treina modelo) e subirá a API.
- Verifique `/health`.
- Teste endpoints:
  - `GET /realtime` (autenticado)
  - `GET /historical` (autenticado)

6) Dashboard (opcional)
- Recomenda-se publicar o Streamlit em outro serviço (porta 8501):
  - Build Command: `docker build -t sentix-dashboard .`
  - Start Command: `python -m streamlit run dashboard.py --server.port ${PORT:-8501} --server.address 0.0.0.0`

## Segurança
- Mantenha credenciais da API (`config.yml`) com valores próprios.
- Opcional: restrinja IPs permitidos via firewall do provedor.
- Limite de requisições (rate limiting) pode ser adicionado no proxy (ex.: Cloudflare) se necessário.

## Performance e custos
- FinBERT em CPU roda com latência aceitável para o MVP.
- Uma instância básica (ex.: 0.5–1 vCPU, 1–2GB RAM) costuma ser suficiente.
- Cold start: se o modelo não estiver cacheado, o download aumenta tempo de inicialização.
- Para reduzir cold start: manter cache em disco persistente (`HF_HOME`) ou pré-carregar no build (já previsto).

## Alternativas a Render
- Fly.io, Railway, DigitalOcean, Hetzner — todos funcionam com Docker.
- Em VPS tradicional, orquestre com Docker Compose (API + dashboard) e um proxy reverso (Nginx/Caddy) para HTTPS e domínio.

## Checklist de verificação pós-deploy
- `/health` responde `{"status": "healthy"}`
- Autenticação básica ativa
- Dados/outputs persistem em `/app/data` e `/app/outputs`
- Endpoints `/realtime` e `/historical` retornam dados

## Conclusão — vale a pena?
- Sim, vale a pena subir para uma VPS/Render se o objetivo é facilitar acesso para terceiros e evitar setup local.
- Benefícios: acesso via browser, zero instalação para usuários, possibilidade de abrir para mais pessoas.
- Observe custos e segurança. Para este MVP (análise de sentimento), Render é adequado e simples.