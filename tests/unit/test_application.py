"""Testes da camada de application: handlers de comandos e queries de leitura."""

from decimal import Decimal

import pytest

from wallet.application.commands import DepositFunds, OpenWallet, WithdrawFunds
from wallet.application.handlers import WalletCommandHandler
from wallet.application.queries import WalletQueryService
from wallet.domain.exceptions import InvalidAmountError, WalletNotFoundError
from wallet.infrastructure.event_store import EventStore
from wallet.infrastructure.repository import WalletRepository


@pytest.fixture
def event_store() -> EventStore:
    return EventStore("sqlite:///:memory:")


@pytest.fixture
def repositorio(event_store: EventStore) -> WalletRepository:
    return WalletRepository(event_store)


@pytest.fixture
def handler(repositorio: WalletRepository) -> WalletCommandHandler:
    return WalletCommandHandler(repositorio)


@pytest.fixture
def queries(event_store: EventStore) -> WalletQueryService:
    return WalletQueryService(event_store)


class TestWalletCommandHandler:
    def test_handle_open_cria_carteira_recuperavel_pelo_repositorio(
        self, handler: WalletCommandHandler, repositorio: WalletRepository
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))

        carteira = repositorio.get(wallet_id)
        assert carteira.id == wallet_id
        assert carteira.owner_name == "Alice"
        assert carteira.version == 1

    def test_handle_deposit_soma_ao_saldo(
        self, handler: WalletCommandHandler, repositorio: WalletRepository
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))

        handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount="100.50"))

        assert repositorio.get(wallet_id).balance == Decimal("100.50")

    def test_handle_withdraw_subtrai_do_saldo(
        self, handler: WalletCommandHandler, repositorio: WalletRepository
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))
        handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount="100.00"))

        handler.handle_withdraw(WithdrawFunds(wallet_id=wallet_id, amount="35.00"))

        assert repositorio.get(wallet_id).balance == Decimal("65.00")

    @pytest.mark.parametrize("quantia_invalida", ["abc", "-5", "0"])
    def test_deposito_com_amount_invalido_lanca_invalid_amount(
        self, handler: WalletCommandHandler, quantia_invalida: str
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))

        with pytest.raises(InvalidAmountError):
            handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount=quantia_invalida))

    @pytest.mark.parametrize("quantia_invalida", ["abc", "-5", "0"])
    def test_saque_com_amount_invalido_lanca_invalid_amount(
        self, handler: WalletCommandHandler, quantia_invalida: str
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))
        handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount="50.00"))

        with pytest.raises(InvalidAmountError):
            handler.handle_withdraw(WithdrawFunds(wallet_id=wallet_id, amount=quantia_invalida))


class TestWalletQueryService:
    def test_get_wallet_retorna_campos_esperados(
        self, handler: WalletCommandHandler, queries: WalletQueryService
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))
        handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount="200.00"))
        handler.handle_withdraw(WithdrawFunds(wallet_id=wallet_id, amount="49.90"))

        resultado = queries.get_wallet(wallet_id)

        assert resultado == {
            "id": wallet_id,
            "owner_name": "Alice",
            "balance": "150.10",
            "version": 3,
        }

    def test_get_wallet_de_id_inexistente_lanca_wallet_not_found(
        self, queries: WalletQueryService
    ) -> None:
        with pytest.raises(WalletNotFoundError):
            queries.get_wallet("id-que-nao-existe")

    def test_get_statement_retorna_entradas_em_ordem_com_saldo_acumulado(
        self, handler: WalletCommandHandler, queries: WalletQueryService
    ) -> None:
        wallet_id = handler.handle_open(OpenWallet(owner_name="Alice"))
        handler.handle_deposit(
            DepositFunds(wallet_id=wallet_id, amount="200.00", description="salário")
        )
        handler.handle_withdraw(WithdrawFunds(wallet_id=wallet_id, amount="80.00"))
        handler.handle_deposit(DepositFunds(wallet_id=wallet_id, amount="10.50"))

        extrato = queries.get_statement(wallet_id)

        assert [linha["type"] for linha in extrato] == [
            "abertura",
            "deposito",
            "saque",
            "deposito",
        ]
        assert [linha["balance_after"] for linha in extrato] == [
            "0.00",
            "200.00",
            "120.00",
            "130.50",
        ]
        assert extrato[0]["description"] == "Carteira aberta para Alice"
        assert extrato[1]["description"] == "salário"
        assert extrato[2]["description"] == "Saque"  # fallback sem descrição
        assert extrato[3]["amount"] == "10.50"
        assert all("T" in linha["occurred_at"] for linha in extrato)  # ISO 8601
