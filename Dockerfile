# Mesma versão de Python usada no desenvolvimento local (consistência)
FROM python:3.14-slim

WORKDIR /app

# Dependências antes do código-fonte: enquanto requirements.txt não mudar,
# a camada do pip install permanece em cache entre builds
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/

EXPOSE 8000

# --app-dir src coloca o pacote wallet no caminho de import, como no pytest.ini
CMD ["uvicorn", "--app-dir", "src", "wallet.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
