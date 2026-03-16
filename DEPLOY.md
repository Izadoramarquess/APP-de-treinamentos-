## Rodando Localmente (Seu Próprio Servidor)
Como você decidiu não usar o Vercel e rodar no seu próprio servidor local, o processo é muito simples:

1. **Instale as dependências**:
   Abra o seu terminal na pasta do projeto e rode:
   ```bash
   pip install -r backend/requirements.txt
   ```

2. **Inicie o servidor**:
   Rode o comando:
   ```bash
   python backend/main.py
   ```

3. **Acesse no Navegador**:
   A aplicação estará disponível em `http://localhost:8000`. 
   
O backend está configurado para entregar os arquivos do frontend automaticamente.

---

## Requisitos de Ambiente
A aplicação agora utiliza variáveis de ambiente para configuração sensível:
- `DATABASE_URL`: Link de conexão PostgreSQL (ex: `postgresql://user:pass@host:5432/db`)
- `PORT`: Porta onde o servidor vai rodar (padrão 8000)
- `ALLOWED_ORIGINS`: Lista de domínios permitidos para CORS (separados por vírgula)

## Localização dos Arquivos
O arquivo principal do frontend (`index.html`) está localizado dentro da pasta `frontend/`. Quando você sobe para o GitHub, ele não aparece na raiz do repositório por questões de organização (separação de Backend e Frontend).

- **Frontend**: `frontend/index.html`
- **Backend**: `backend/main.py`

## Opções de Deploy

### 1. Vercel (Somente Frontend)
Se você quer apenas visualizar a interface:
1. No Vercel, importe seu repositório.
2. Nas configurações de "Framework Preset", selecione `Other`.
3. Em **Root Directory**, selecione a pasta `frontend`.
4. Clique em Deploy.

### 2. Render / Railway / Fly.io (Full Stack - Recomendado)
Como a aplicação tem um Backend em Python, você precisa de um serviço que suporte Docker ou Python:
1. Conecte seu GitHub ao serviço escolhido.
2. O serviço detectará o `Dockerfile` ou o `docker-compose.yml`.
3. Configure as variáveis de ambiente (veja acima).
4. O Backend está configurado para servir o Frontend automaticamente.

### 3. GitHub Pages (Somente Frontend)
1. Vá em **Settings** > **Pages** no seu repositório.
2. Se você quiser usar a pasta `docs`, você deve mover o conteúdo de `frontend/` para uma pasta chamada `docs/` na raiz.
3. Caso contrário, o GitHub Pages não encontrará o `index.html` na raiz.

## Notas de Produção
- O Backend está configurado para servir a pasta `frontend/` automaticamente se estiver no mesmo nível de diretório.
- Certifique-se de alterar a `SECRET_KEY` no arquivo `auth.py` para uma chave segura antes do deploy real.
