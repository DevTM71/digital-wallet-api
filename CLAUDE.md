# digital-wallet-api

API de carteira digital construída com FastAPI, aplicando DDD (Domain-Driven Design) e Event Sourcing.

## Arquitetura em camadas

O código-fonte vive em `src/wallet/`, dividido em quatro camadas com dependências apontando sempre para dentro (em direção ao domínio):

- **`domain/`** — Coração do sistema: agregados, value objects, eventos de domínio e exceções. **Não pode ter dependências externas** (nenhum import de framework, ORM ou biblioteca de terceiros); apenas biblioteca padrão do Python.
- **`application/`** — Casos de uso que orquestram o domínio: recebem comandos, carregam agregados, invocam regras de negócio e delegam persistência a interfaces (ports). Não contém regra de negócio.
- **`infrastructure/`** — Implementações concretas de persistência (event store, repositórios) e demais adaptadores técnicos.
- **`api/`** — Camada HTTP (FastAPI): rotas, schemas de entrada/saída e tradução de exceções de domínio para respostas HTTP.

Testes ficam em `tests/unit/` (domínio e aplicação, sem I/O) e `tests/integration/` (persistência e API).

## Event Sourcing — regra fundamental

**O estado nunca é persistido diretamente.** A única fonte de verdade são os eventos de domínio, gravados em ordem no event store. O estado de um agregado é sempre reconstruído por *replay*: carrega-se o histórico de eventos e aplica-se cada um, na ordem, sobre uma instância vazia. Qualquer mudança de estado nasce de um novo evento — nunca de um UPDATE em uma linha de "saldo".

## Comandos

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt  # setup
.venv/bin/python -m pytest                                              # testes
.venv/bin/uvicorn --app-dir src wallet.api.main:app --reload            # API (docs em /docs)
```

## Configuração (variáveis de ambiente)

- `DATABASE_URL` — URL do banco de eventos; default `sqlite:///./wallet_events.db` (arquivo gitignorado).
- `CORS_ORIGINS` — origens permitidas para clientes web, separadas por vírgula; default `http://localhost:3000` (front-end Next.js local).

O Python do projeto é **3.14**, fixado em três lugares que devem andar juntos: `.venv` local, `Dockerfile` (`python:3.14-slim`) e CI (`python-version` em `.github/workflows/ci.yml`).

## Deploy (Render + Neon)

A API roda no Render (runtime Docker) com PostgreSQL gerenciado no Neon. Variáveis de ambiente:

- `DATABASE_URL` — connection string do Neon, com o esquema ajustado para `postgresql+psycopg2://...` (o SQLAlchemy 2 não aceita o prefixo `postgres://` que o Neon fornece; mantenha o `?sslmode=require`).
- `CORS_ORIGINS` — origem do front-end em produção.

O Render injeta `PORT` (o CMD do Dockerfile a respeita via `${PORT:-8000}`) e o health check path é `GET /health`.

## Convenções

- Docstrings, comentários, mensagens de erro e variáveis locais em **português**; identificadores públicos (classes, métodos, campos) em **inglês** (`Wallet.open`, `handle_deposit`).
- **Type hints sempre**, em todas as assinaturas de funções e métodos.
- **Testes obrigatórios para toda regra de negócio** — nenhuma regra de domínio entra sem teste unitário cobrindo o caso feliz e os casos de erro.
- Isolamento nos testes: `EventStore("sqlite:///:memory:")`; testes de API sobrescrevem as factories `get_command_handler`/`get_query_service` via `app.dependency_overrides`.
- Ao mudar a contagem de testes, atualize o badge `pytest-N%20testes` no README.md (em commit `docs` separado).

## Versionamento (Git)

- Commits **pequenos e coesos**: cada commit contém uma única mudança lógica. **Nunca agrupe mudanças não relacionadas no mesmo commit.**
- Seguir **Conventional Commits**: prefixos `feat`, `fix`, `test`, `docs`, `chore` (e `refactor` quando aplicável).
- Mensagens de commit em **inglês, no modo imperativo** (ex.: `feat: add withdraw validation`, não `added withdraw validation`).
