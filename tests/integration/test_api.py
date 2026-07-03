"""Testes de integração da API HTTP, do request ao event store em memória."""

from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from wallet.api.main import app, get_command_handler, get_query_service
from wallet.application.handlers import WalletCommandHandler
from wallet.application.queries import WalletQueryService
from wallet.infrastructure.event_store import EventStore
from wallet.infrastructure.repository import WalletRepository


@pytest.fixture
def client() -> Iterator[TestClient]:
    """TestClient com um EventStore em memória isolado por teste."""
    event_store = EventStore("sqlite:///:memory:")
    repositorio = WalletRepository(event_store)
    app.dependency_overrides[get_command_handler] = lambda: WalletCommandHandler(repositorio)
    app.dependency_overrides[get_query_service] = lambda: WalletQueryService(event_store)
    with TestClient(app) as cliente:
        yield cliente
    app.dependency_overrides.clear()


def _abrir_carteira(client: TestClient, owner_name: str = "Alice") -> str:
    resposta = client.post("/wallets", json={"owner_name": owner_name})
    assert resposta.status_code == 201
    return resposta.json()["id"]


class TestCicloCompleto:
    def test_abrir_depositar_sacar_consultar_e_extrato(self, client: TestClient) -> None:
        wallet_id = _abrir_carteira(client)

        deposito = client.post(
            f"/wallets/{wallet_id}/deposits",
            json={"amount": "500.00", "description": "salário"},
        )
        assert deposito.status_code == 204

        saque = client.post(
            f"/wallets/{wallet_id}/withdrawals",
            json={"amount": "120.50", "description": "aluguel"},
        )
        assert saque.status_code == 204

        carteira = client.get(f"/wallets/{wallet_id}")
        assert carteira.status_code == 200
        assert carteira.json() == {
            "id": wallet_id,
            "owner_name": "Alice",
            "balance": "379.50",
            "version": 3,
        }

        extrato = client.get(f"/wallets/{wallet_id}/statement")
        assert extrato.status_code == 200
        corpo = extrato.json()
        assert corpo["wallet_id"] == wallet_id
        assert [entrada["type"] for entrada in corpo["entries"]] == [
            "abertura",
            "deposito",
            "saque",
        ]
        assert corpo["entries"][-1]["balance_after"] == "379.50"


class TestErros:
    def test_saque_sem_saldo_retorna_409(self, client: TestClient) -> None:
        wallet_id = _abrir_carteira(client)

        resposta = client.post(
            f"/wallets/{wallet_id}/withdrawals", json={"amount": "10.00"}
        )

        assert resposta.status_code == 409
        assert "Saldo insuficiente" in resposta.json()["detail"]

    @pytest.mark.parametrize("quantia_invalida", ["-5", "abc"])
    def test_deposito_com_amount_invalido_retorna_422(
        self, client: TestClient, quantia_invalida: str
    ) -> None:
        wallet_id = _abrir_carteira(client)

        resposta = client.post(
            f"/wallets/{wallet_id}/deposits", json={"amount": quantia_invalida}
        )

        assert resposta.status_code == 422
        assert resposta.json()["detail"] == "Valor inválido."

    def test_consulta_de_carteira_inexistente_retorna_404(self, client: TestClient) -> None:
        resposta = client.get("/wallets/id-que-nao-existe")

        assert resposta.status_code == 404

    def test_abertura_com_owner_name_vazio_retorna_422(self, client: TestClient) -> None:
        resposta = client.post("/wallets", json={"owner_name": ""})

        assert resposta.status_code == 422  # validação de borda do Pydantic


class TestHealth:
    def test_health_retorna_ok(self, client: TestClient) -> None:
        resposta = client.get("/health")

        assert resposta.status_code == 200
        assert resposta.json() == {"status": "ok"}

    def test_health_aceita_head_sem_corpo(self, client: TestClient) -> None:
        resposta = client.head("/health")

        assert resposta.status_code == 200
        assert resposta.content == b""


class TestCors:
    def test_origem_permitida_recebe_header_de_cors(self, client: TestClient) -> None:
        origem = "http://localhost:3000"

        resposta = client.post(
            "/wallets", json={"owner_name": "Alice"}, headers={"Origin": origem}
        )

        assert resposta.status_code == 201
        assert resposta.headers["access-control-allow-origin"] == origem
