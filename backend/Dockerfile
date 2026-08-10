# ---- builder: compila as dependências que precisam de gcc/libpq-dev ----
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends libpq-dev gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---- runner: imagem final, sem ferramentas de build ----
FROM python:3.10-slim AS runner

WORKDIR /app

# libpq5 é a lib de runtime (não o toolkit de build) usada pelo psycopg2 em tempo de execução
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*

COPY --from=builder /root/.local /root/.local
COPY . .

RUN mkdir -p uploads

ENV PATH=/root/.local/bin:$PATH

EXPOSE 8000

CMD ["gunicorn", "-w", "4", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:8000"]
