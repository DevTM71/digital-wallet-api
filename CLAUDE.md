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

## Convenções

- Código, docstrings e mensagens de erro em **português**.
- **Type hints sempre**, em todas as assinaturas de funções e métodos.
- **Testes obrigatórios para toda regra de negócio** — nenhuma regra de domínio entra sem teste unitário cobrindo o caso feliz e os casos de erro.

## Versionamento (Git)

- Commits **pequenos e coesos**: cada commit contém uma única mudança lógica. **Nunca agrupe mudanças não relacionadas no mesmo commit.**
- Seguir **Conventional Commits**: prefixos `feat`, `fix`, `test`, `docs`, `chore` (e `refactor` quando aplicável).
- Mensagens de commit em **inglês, no modo imperativo** (ex.: `feat: add withdraw validation`, não `added withdraw validation`).
