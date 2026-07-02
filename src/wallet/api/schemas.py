"""Schemas Pydantic: o contrato HTTP da API.

Estes modelos definem exclusivamente o formato de entrada e saída da camada
HTTP — validação de borda, exemplos e documentação OpenAPI. Eles nunca
vazam para o domínio: as rotas os traduzem para comandos da application, e
as respostas são montadas a partir do que a application retorna.
"""

from pydantic import BaseModel, Field


class OpenWalletRequest(BaseModel):
    """Corpo da requisição de abertura de carteira."""

    owner_name: str = Field(
        min_length=1,
        max_length=120,
        description="Nome do titular da carteira.",
        examples=["Maria Silva"],
    )


class TransactionRequest(BaseModel):
    """Corpo da requisição de depósito ou saque."""

    amount: str = Field(
        description=(
            "Quantia decimal representada como string (ex.: \"150.00\") — "
            "evita erros de arredondamento de ponto flutuante no JSON."
        ),
        examples=["150.00"],
    )
    description: str = Field(
        default="",
        max_length=255,
        description="Descrição opcional da movimentação.",
        examples=["Salário de junho"],
    )


class WalletCreatedResponse(BaseModel):
    """Resposta da criação de carteira."""

    id: str


class WalletResponse(BaseModel):
    """Estado atual da carteira, derivado do fluxo de eventos."""

    id: str
    owner_name: str
    balance: str
    version: int


class StatementEntry(BaseModel):
    """Uma linha do extrato: a projeção de um evento de domínio."""

    type: str
    amount: str
    balance_after: str
    description: str
    occurred_at: str


class StatementResponse(BaseModel):
    """Extrato completo da carteira, na ordem dos eventos."""

    wallet_id: str
    entries: list[StatementEntry]
