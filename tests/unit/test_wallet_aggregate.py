"""Testes unitários das regras de negócio do agregado Wallet."""

from decimal import Decimal

import pytest

from wallet.domain.aggregate import Wallet
from wallet.domain.events import WalletOpened
from wallet.domain.exceptions import InsufficientFundsError, InvalidAmountError
from wallet.domain.value_objects import Money


class TestAberturaDeCarteira:
    def test_abertura_gera_evento_wallet_opened_e_versao_1(self) -> None:
        carteira = Wallet.open("Alice")

        eventos = carteira.pull_uncommitted_events()
        assert len(eventos) == 1
        assert isinstance(eventos[0], WalletOpened)
        assert eventos[0].owner_name == "Alice"
        assert carteira.version == 1
        assert carteira.owner_name == "Alice"
        assert carteira.balance == Decimal("0.00")


class TestDeposito:
    def test_deposito_soma_ao_saldo(self) -> None:
        carteira = Wallet.open("Alice")

        carteira.deposit(Money(Decimal("100.50")), "salário")
        carteira.deposit(Money(Decimal("9.50")), "reembolso")

        assert carteira.balance == Decimal("110.00")


class TestSaque:
    def test_saque_subtrai_do_saldo(self) -> None:
        carteira = Wallet.open("Alice")
        carteira.deposit(Money(Decimal("100.00")), "salário")

        carteira.withdraw(Money(Decimal("30.00")), "mercado")

        assert carteira.balance == Decimal("70.00")

    def test_saque_acima_do_saldo_lanca_insufficient_funds(self) -> None:
        carteira = Wallet.open("Alice")
        carteira.deposit(Money(Decimal("50.00")), "salário")

        with pytest.raises(InsufficientFundsError):
            carteira.withdraw(Money(Decimal("50.01")), "mercado")

        # O saldo permanece intacto: nenhum evento foi gerado pelo saque inválido
        assert carteira.balance == Decimal("50.00")


class TestMoney:
    def test_money_rejeita_zero(self) -> None:
        with pytest.raises(InvalidAmountError):
            Money(Decimal("0"))

    def test_money_rejeita_negativo(self) -> None:
        with pytest.raises(InvalidAmountError):
            Money(Decimal("-10.00"))

    def test_money_quantiza_em_duas_casas(self) -> None:
        assert Money(Decimal("10.555")).amount == Decimal("10.56")


class TestReplay:
    def test_replay_reconstroi_estado_identico_ao_original(self) -> None:
        original = Wallet.open("Alice")
        original.deposit(Money(Decimal("200.00")), "salário")
        original.withdraw(Money(Decimal("75.25")), "aluguel")
        historico = original.pull_uncommitted_events()

        reconstruida = Wallet.load_from_history(historico)

        assert reconstruida.id == original.id
        assert reconstruida.owner_name == original.owner_name
        assert reconstruida.balance == original.balance == Decimal("124.75")
        assert reconstruida.version == original.version == 3
        assert reconstruida.pull_uncommitted_events() == []
