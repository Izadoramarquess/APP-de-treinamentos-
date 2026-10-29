#!/bin/bash
# Atualiza o app sem perder o banco de dados.
# NUNCA use "docker-compose down -v" — isso apagaria o volume do banco.

set -e

echo "==> Baixando atualizações do repositório..."
git pull

echo "==> Reconstruindo e reiniciando os serviços..."
docker compose up --build -d

echo "==> Verificando status dos serviços..."
docker compose ps

echo ""
echo "Atualização concluída. O banco de dados foi preservado."
