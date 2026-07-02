"""Testes de integração do Event Store e do WalletRepository (SQLite em memória)."""

from decimal import Decimal

import pytest

from wallet.domain.aggregate import Wallet
from wallet.domain.events import FundsDeposited, WalletOpened
from wallet.domain.exceptions import ConcurrencyError, WalletNotFoundError
from wallet.domain.value_objects import Money
from wallet.infrastructure.event_store import EventStore
from wallet.infrastructure.repository import WalletRepository


@pytest.fixture
def event_store() -> EventStore:
    return EventStore("sqlite:///:memory:")


@pytest.fixture
def repositorio(event_store: EventStore) -> WalletRepository:
    return WalletRepository(event_store)


class TestEventStore:
    def test_round_trip_reconstroi_eventos_identicos(self, event_store: EventStore) -> None:
        abertura = WalletOpened(aggregate_id="w-1", version=1, owner_name="Alice")
        deposito = FundsDeposited(
            aggregate_id="w-1",
            version=2,
            amount=Decimal("100.50"),
            description="salário",
        )

        event_store.append([abertura, deposito])
        carregados = event_store.load("w-1")

        assert [type(evento) for evento in carregados] == [WalletOpened, FundsDeposited]
        assert [evento.version for evento in carregados] == [1, 2]
        assert isinstance(carregados[0], WalletOpened)
        assert carregados[0].owner_name == "Alice"
        assert carregados[0].event_id == abertura.event_id
        assert isinstance(carregados[1], FundsDeposited)
        assert isinstance(carregados[1].amount, Decimal)
        assert carregados[1].amount == Decimal("100.50")
        assert carregados[1].description == "salário"

    def test_mesma_versao_do_mesmo_agregado_lanca_concurrency_error(
        self, event_store: EventStore
    ) -> None:
        event_store.append([WalletOpened(aggregate_id="w-1", version=1, owner_name="Alice")])

        with pytest.raises(ConcurrencyError):
            event_store.append(
                [WalletOpened(aggregate_id="w-1", version=1, owner_name="Bob")]
            )

    def test_load_de_agregado_sem_eventos_retorna_lista_vazia(
        self, event_store: EventStore
    ) -> None:
        assert event_store.load("inexistente") == []


class TestWalletRepository:
    def test_save_e_get_reconstroem_o_agregado(self, repositorio: WalletRepository) -> None:
        carteira = Wallet.open("Alice")
        carteira.deposit(Money(Decimal("150.00")), "salário")
        assert carteira.id is not None
        repositorio.save(carteira)

        reconstruida = repositorio.get(carteira.id)

        assert reconstruida.id == carteira.id
        assert reconstruida.owner_name == "Alice"
        assert reconstruida.balance == Decimal("150.00")
        assert reconstruida.version == 2

    def test_get_de_id_inexistente_lanca_wallet_not_found(
        self, repositorio: WalletRepository
    ) -> None:
        with pytest.raises(WalletNotFoundError):
            repositorio.get("id-que-nao-existe")

    def test_fluxo_completo_carregar_sacar_salvar_e_recarregar(
        self, repositorio: WalletRepository
    ) -> None:
        carteira = Wallet.open("Alice")
        carteira.deposit(Money(Decimal("200.00")), "salário")
        assert carteira.id is not None
        repositorio.save(carteira)

        recarregada = repositorio.get(carteira.id)
        recarregada.withdraw(Money(Decimal("80.00")), "aluguel")
        repositorio.save(recarregada)

        final = repositorio.get(carteira.id)
        assert final.balance == Decimal("120.00")
        assert final.version == 3
