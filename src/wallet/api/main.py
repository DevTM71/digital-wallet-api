"""Camada HTTP da carteira digital (FastAPI).

A API é a camada mais externa da arquitetura: conhece o domínio apenas
através da application (comandos, handlers e queries) e sua única
responsabilidade própria é o protocolo — validar a borda com os schemas,
injetar dependências e traduzir exceções de domínio em códigos HTTP.
"""

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from wallet.application.commands import DepositFunds, OpenWallet, WithdrawFunds
from wallet.application.handlers import WalletCommandHandler
from wallet.application.queries import WalletQueryService
from wallet.domain.exceptions import (
    ConcurrencyError,
    InsufficientFundsError,
    InvalidAmountError,
    WalletNotFoundError,
)
from wallet.infrastructure.event_store import EventStore
from wallet.infrastructure.repository import WalletRepository
from wallet.api.schemas import (
    OpenWalletRequest,
    StatementResponse,
    TransactionRequest,
    WalletCreatedResponse,
    WalletResponse,
)

app = FastAPI(
    title="Digital Wallet API",
    description=(
        "API de carteira digital construída com DDD e Event Sourcing: "
        "todo estado é derivado de um fluxo append-only de eventos de domínio."
    ),
    version="1.0.0",
)

# Origens permitidas para clientes web (front-end), separadas por vírgula
_origens_cors = [
    origem.strip()
    for origem in os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")
    if origem.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_cors,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Singleton de módulo, criado sob demanda para evitar efeito colateral
# (criação do arquivo SQLite) no momento do import
_event_store: EventStore | None = None


def _obter_event_store() -> EventStore:
    global _event_store
    if _event_store is None:
        _event_store = EventStore()
    return _event_store


def get_command_handler() -> WalletCommandHandler:
    """Factory do handler de comandos, para injeção via ``Depends``."""
    return WalletCommandHandler(WalletRepository(_obter_event_store()))


def get_query_service() -> WalletQueryService:
    """Factory do serviço de queries, para injeção via ``Depends``."""
    return WalletQueryService(_obter_event_store())


CommandHandlerDep = Annotated[WalletCommandHandler, Depends(get_command_handler)]
QueryServiceDep = Annotated[WalletQueryService, Depends(get_query_service)]


# --- Tradução centralizada: exceção de domínio -> código HTTP ---------------


@app.exception_handler(WalletNotFoundError)
async def tratar_carteira_nao_encontrada(
    request: Request, exc: WalletNotFoundError
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(exc)})


@app.exception_handler(InvalidAmountError)
async def tratar_quantia_invalida(request: Request, exc: InvalidAmountError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Valor inválido."},
    )


@app.exception_handler(InsufficientFundsError)
async def tratar_saldo_insuficiente(
    request: Request, exc: InsufficientFundsError
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


@app.exception_handler(ConcurrencyError)
async def tratar_conflito_de_concorrencia(
    request: Request, exc: ConcurrencyError
) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(exc)})


# --- Rotas -------------------------------------------------------------------


@app.get("/health", summary="Health check da aplicação")
def health() -> dict[str, str]:
    """Usado pelo health check da plataforma de deploy; não toca o banco."""
    return {"status": "ok"}


@app.post(
    "/wallets",
    status_code=status.HTTP_201_CREATED,
    response_model=WalletCreatedResponse,
    summary="Abre uma nova carteira",
)
def abrir_carteira(corpo: OpenWalletRequest, handler: CommandHandlerDep) -> WalletCreatedResponse:
    wallet_id = handler.handle_open(OpenWallet(owner_name=corpo.owner_name))
    return WalletCreatedResponse(id=wallet_id)


@app.post(
    "/wallets/{wallet_id}/deposits",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Deposita fundos na carteira",
)
def depositar(wallet_id: str, corpo: TransactionRequest, handler: CommandHandlerDep) -> Response:
    handler.handle_deposit(
        DepositFunds(wallet_id=wallet_id, amount=corpo.amount, description=corpo.description)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/wallets/{wallet_id}/withdrawals",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Saca fundos da carteira",
)
def sacar(wallet_id: str, corpo: TransactionRequest, handler: CommandHandlerDep) -> Response:
    handler.handle_withdraw(
        WithdrawFunds(wallet_id=wallet_id, amount=corpo.amount, description=corpo.description)
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get(
    "/wallets/{wallet_id}",
    response_model=WalletResponse,
    summary="Consulta o estado atual da carteira",
)
def consultar_carteira(wallet_id: str, queries: QueryServiceDep) -> WalletResponse:
    return WalletResponse(**queries.get_wallet(wallet_id))


@app.get(
    "/wallets/{wallet_id}/statement",
    response_model=StatementResponse,
    summary="Consulta o extrato completo da carteira",
)
def consultar_extrato(wallet_id: str, queries: QueryServiceDep) -> StatementResponse:
    entradas = queries.get_statement(wallet_id)
    return StatementResponse.model_validate({"wallet_id": wallet_id, "entries": entradas})
