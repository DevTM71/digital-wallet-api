# 💳 Digital Wallet API

[![CI](https://github.com/DevTM71/digital-wallet-api/actions/workflows/ci.yml/badge.svg)](https://github.com/DevTM71/digital-wallet-api/actions)
![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![Pytest](https://img.shields.io/badge/pytest-33%20testes-0A9EDC?logo=pytest&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED?logo=docker&logoColor=white)

API de carteira digital construída com **FastAPI** aplicando **DDD** (Domain-Driven Design) e **Event Sourcing**. Aqui o estado nunca é armazenado diretamente: toda mudança é um **evento imutável** gravado em um fluxo append-only, e o saldo de cada carteira é **reconstruído por replay** dos seus eventos. A consequência prática é poderosa — o extrato não é uma tabela mantida à parte que pode divergir do saldo: **o extrato É o fluxo de eventos**, auditoria completa de graça.

> 🖥️ **Interface web:** este projeto tem um front-end em Next.js + TypeScript — [digital-wallet-web](https://github.com/DevTM71/digital-wallet-web).

## Arquitetura

Quatro camadas com dependências apontando sempre para o domínio:

```text
src/wallet/
├── domain/                # Regras de negócio puras — zero dependências externas
│   ├── aggregate.py       #   Agregado Wallet: comandos geram eventos; replay reconstrói o estado
│   ├── events.py          #   WalletOpened, FundsDeposited, FundsWithdrawn — a fonte de verdade
│   ├── value_objects.py   #   Money: Decimal imutável, 2 casas, sempre > 0
│   └── exceptions.py      #   Exceções de domínio, traduzidas para HTTP só na borda
├── application/           # Orquestração no estilo CQRS — sem regra de negócio
│   ├── commands.py        #   Intenções de escrita (OpenWallet, DepositFunds, WithdrawFunds)
│   ├── handlers.py        #   Fluxo carregar → executar comportamento → salvar eventos
│   └── queries.py         #   Lado de leitura: estado e extrato derivados do fluxo de eventos
├── infrastructure/        # Persistência
│   ├── event_store.py     #   Event store append-only com concorrência otimista
│   └── repository.py      #   save = append de eventos; get = replay do histórico
└── api/                   # Camada HTTP (FastAPI)
    ├── main.py            #   Rotas, injeção de dependências e tradução de erros
    └── schemas.py         #   Contrato da API (Pydantic)

tests/
├── unit/                  # Domínio e application puros, sem I/O
└── integration/           # Event store com banco real e API via HTTP
```

```mermaid
flowchart LR
    C[Cliente HTTP] --> API[API FastAPI]
    API -- comandos --> H[Command Handlers]
    H -- executa comportamento --> W[Agregado Wallet]
    W -- gera --> E[Eventos de domínio]
    E -- append --> S[(Event Store append-only)]
    S -. replay do histórico .-> W
    API -- consultas --> Q[Queries]
    S -- fluxo de eventos --> Q
```

### Conceitos demonstrados

- **DDD** — agregado `Wallet` como guardião das invariantes, Value Object `Money` imutável, exceções de domínio e repository; o domínio não importa nenhum framework.
- **Event Sourcing** — eventos como única fonte de verdade, estado reconstruído por replay e trilha de auditoria completa sem esforço adicional.
- **CQRS leve** — lado de escrita (comandos → handlers → agregado) separado do lado de leitura (queries projetando o fluxo de eventos).
- **Concorrência otimista** — a constraint única `(aggregate_id, version)` no event store garante que duas transações concorrentes não gravem a mesma versão do mesmo agregado: a segunda recebe `409 Conflict`.
- **Testes em dois níveis** — unitários puros para as regras de negócio e de integração exercitando API e banco reais de ponta a ponta.

## Como rodar

### Com Docker

```bash
docker compose up --build
```

### Localmente

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn --app-dir src wallet.api.main:app --reload
```

Em ambos os casos a API sobe em `http://localhost:8000`, com a documentação interativa (Swagger) em [`/docs`](http://localhost:8000/docs).

## Endpoints

| Método | Rota                          | Descrição                        | Erros                                              |
| ------ | ----------------------------- | -------------------------------- | -------------------------------------------------- |
| POST   | `/wallets`                    | Abre uma nova carteira           | `422` dados inválidos                              |
| POST   | `/wallets/{id}/deposits`      | Deposita fundos                  | `404` não encontrada · `422` valor inválido        |
| POST   | `/wallets/{id}/withdrawals`   | Saca fundos                      | `404` · `409` saldo insuficiente · `422`           |
| GET    | `/wallets/{id}`               | Consulta o estado atual          | `404` não encontrada                               |
| GET    | `/wallets/{id}/statement`     | Extrato completo (auditoria)     | `404` não encontrada                               |

As escritas também podem responder `409 Conflict` em caso de conflito de concorrência (duas transações tentando gravar a mesma versão do agregado).

## Exemplo de uso

```bash
# 1. Abrir a carteira
curl -X POST http://localhost:8000/wallets \
  -H 'Content-Type: application/json' \
  -d '{"owner_name": "Tiago Martins"}'
# → 201 {"id":"8ad83555-b5a5-4a53-975d-da607782c9d5"}

# 2. Depositar 500.00
curl -X POST http://localhost:8000/wallets/8ad83555-b5a5-4a53-975d-da607782c9d5/deposits \
  -H 'Content-Type: application/json' \
  -d '{"amount": "500.00", "description": "Salário de junho"}'
# → 204

# 3. Sacar 120.50
curl -X POST http://localhost:8000/wallets/8ad83555-b5a5-4a53-975d-da607782c9d5/withdrawals \
  -H 'Content-Type: application/json' \
  -d '{"amount": "120.50", "description": "Aluguel"}'
# → 204

# 4. Extrato — o fluxo de eventos projetado, com saldo acumulado linha a linha
curl http://localhost:8000/wallets/8ad83555-b5a5-4a53-975d-da607782c9d5/statement
```

```json
{
  "wallet_id": "8ad83555-b5a5-4a53-975d-da607782c9d5",
  "entries": [
    {
      "type": "abertura",
      "amount": "0.00",
      "balance_after": "0.00",
      "description": "Carteira aberta para Tiago Martins",
      "occurred_at": "2026-07-02T20:18:28.229337+00:00"
    },
    {
      "type": "deposito",
      "amount": "500.00",
      "balance_after": "500.00",
      "description": "Salário de junho",
      "occurred_at": "2026-07-02T20:18:28.258574+00:00"
    },
    {
      "type": "saque",
      "amount": "120.50",
      "balance_after": "379.50",
      "description": "Aluguel",
      "occurred_at": "2026-07-02T20:18:28.265254+00:00"
    }
  ]
}
```

## Testes

```bash
.venv/bin/python -m pytest
```

- **Unitários** (`tests/unit/`) — regras de negócio do agregado e value objects, handlers e queries; rodam sem nenhum I/O.
- **Integração** (`tests/integration/`) — event store contra SQLite real (round-trip, conflito de concorrência) e a API inteira via HTTP, do request ao banco.

A suíte completa roda no **GitHub Actions** a cada push e pull request — badge no topo.

## Persistência

Por padrão os eventos são gravados em **SQLite** (`wallet_events.db`). A URL do banco vem da variável de ambiente `DATABASE_URL`, então trocar para **PostgreSQL** em produção é uma linha de configuração:

```bash
DATABASE_URL="postgresql+psycopg2://usuario:senha@db-host:5432/wallet"
```

## Roadmap

- **Snapshots** — persistir o estado do agregado a cada N eventos para que carteiras com históricos longos não precisem reprocessar tudo no replay.
- **Projeções materializadas** — read models atualizados a partir dos eventos, liberando o lado de leitura de refazer projeções a cada consulta.
- **Idempotência de comandos** — chave de idempotência por requisição, permitindo retries seguros sem risco de depósito ou saque duplicado.

---

Desenvolvido por [Tiago Martins](https://github.com/DevTM71) — fluxo de trabalho acelerado por IA com Claude Code.
