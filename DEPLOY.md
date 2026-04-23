# Guia de Deploy — GeoTrilha LMS

Este guia descreve como subir a plataforma GeoTrilha LMS em um servidor de produção Linux (Ubuntu).

## 1. Requisitos do Servidor
- Ubuntu 22.04 LTS ou superior
- Python 3.11+
- Nginx
- Git

## 2. Preparação do Ambiente

### Instalar Dependências do Sistema
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx certbot python3-certbot-nginx -y
```

### Clonar o Projeto
```bash
git clone https://github.com/Izadoramarquess/APP-de-treinamentos-.git
cd APP-de-treinamentos-
```

### Criar Ambiente Virtual
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r backend/requirements.txt
```

## 3. Configuração de Produção

### Arquivo .env
Edite o arquivo `backend/.env` e ajuste as variáveis:
- `BASE_URL`: Sua URL pública (ex: `https://treinamentos.geobiogas.tech`)
- `ALLOWED_ORIGINS`: O mesmo domínio acima.
- `SECRET_KEY`: Já geramos uma forte, mas você pode trocar se desejar.

### Permissões
Garanta que o usuário do servidor tenha permissão de escrita nas pastas `uploads/` e no banco de dados.

## 4. Configuração do Systemd (Serviço)
Para manter o servidor rodando sempre, crie um serviço no Linux:

```bash
sudo nano /etc/systemd/system/geotrilha.service
```

Cole o conteúdo abaixo (ajustando os caminhos):
```ini
[Unit]
Description=Gunicorn instance to serve GeoTrilha LMS
After=network.target

[Service]
User=ubuntu
Group=www-data
WorkingDirectory=/home/ubuntu/APP-de-treinamentos-/backend
Environment="PATH=/home/ubuntu/APP-de-treinamentos-/venv/bin"
ExecStart=/home/ubuntu/APP-de-treinamentos-/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

[Install]
WantedBy=multi-user.target
```

Ative o serviço:
```bash
sudo systemctl start geotrilha
sudo systemctl enable geotrilha
```

## 5. Proxy Reverso com Nginx
Configure o Nginx para receber as requisições na porta 80/443 e repassar para o FastAPI.

```bash
sudo nano /etc/nginx/sites-available/geotrilha
```

```nginx
server {
    listen 80;
    server_name seu-dominio.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Servir arquivos estáticos diretamente pelo Nginx (Opcional, mas recomendado para performance)
    location /uploads/ {
        alias /home/ubuntu/APP-de-treinamentos-/uploads/;
    }
}
```

Ative o site e reinicie o Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/geotrilha /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

## 6. SSL com Let's Encrypt
```bash
sudo certbot --nginx -d seu-dominio.com
```

## 7. Manutenção
Sempre que atualizar o código:
```bash
git pull
source venv/bin/activate
pip install -r backend/requirements.txt
sudo systemctl restart geotrilha
```
