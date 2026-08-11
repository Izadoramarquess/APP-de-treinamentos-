# Deploy — GeoTrilha LMS

Tudo roda via **Docker Compose**. Você precisa apenas de Docker instalado no servidor.

---

## Requisitos

- Linux (Ubuntu 22.04+ recomendado)
- [Docker](https://docs.docker.com/engine/install/ubuntu/) + Docker Compose plugin

```bash
# Instalar Docker (Ubuntu)
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Faça logout e login novamente para o grupo ter efeito
```

---

## 1ª vez: Subir o projeto

```bash
# 1. Clonar o repositório
git clone https://github.com/Izadoramarquess/APP-de-treinamentos-.git
cd APP-de-treinamentos-

# 2. Criar o arquivo de configuração
cp .env.example .env
nano .env   # Preencha SECRET_KEY e DB_PASSWORD — a aplicação recusa subir sem eles

# 3. Preparar a pasta de uploads para o usuário não-root do container (UID 1000)
mkdir -p backend/uploads
sudo chown -R 1000:1000 backend/uploads

# 4. Subir tudo
docker compose up --build -d

# 5. Verificar se está rodando
docker compose ps
```

O app estará disponível em `http://IP-DO-SERVIDOR:8000`

**Login do admin:** a senha inicial é gerada automaticamente e aparece só
uma vez no log de inicialização — pegue com:

```bash
docker compose logs backend | grep -A2 "USUÁRIO ADMIN CRIADO"
```

O admin é obrigado a trocar essa senha no primeiro login.

---

## Atualizar o projeto (sem perder o banco)

```bash
bash update.sh
```

Isso faz `git pull` e reconstrói apenas os containers do app.
**O banco de dados (volume Docker) é sempre preservado.**

---

## Parar / Reiniciar

```bash
# Parar sem apagar nada
docker compose stop

# Reiniciar
docker compose start

# Ver logs em tempo real
docker compose logs -f backend
```

---

## Backup do banco de dados

```bash
# Fazer backup
docker compose exec db pg_dump -U user training_db > backup_$(date +%Y%m%d).sql

# Restaurar backup
cat backup_YYYYMMDD.sql | docker compose exec -T db psql -U user training_db
```

---

## IMPORTANTE — O que NUNCA fazer

```bash
# ❌ NUNCA execute este comando — apaga o banco de dados permanentemente
docker compose down -v
```

Para parar o serviço com segurança use `docker compose stop` ou `docker compose down` (sem o `-v`).

---

## Proxy reverso com Nginx (opcional — para usar domínio + HTTPS)

```bash
sudo apt install nginx certbot python3-certbot-nginx -y

sudo nano /etc/nginx/sites-available/geotrilha
```

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    client_max_body_size 500M;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/geotrilha /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx

# SSL gratuito com Let's Encrypt
sudo certbot --nginx -d seu-dominio.com
```

Depois edite o `.env` com o domínio real e rode `bash update.sh`.
