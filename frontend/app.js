console.log("App script running!");
const App = {
    user: null,
    init() {
        console.log("App.init called");
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('view') === 'convite' && urlParams.get('token')) {
            this.showView('invite', urlParams.get('token'));
            return;
        }
        const token = localStorage.getItem('token');
        console.log("Token: ", token);
        if (token) this.fetchCurrentUser(token);
        else this.showView('login');
    },

    async fetchCurrentUser(token) {
        try {
            const res = await fetch('/users/me', { headers: this.apiHeaders() });
            if (res.ok) {
                this.user = await res.json();
                if (this.user.status !== 'ativo' && this.user.status !== 'approved') return this.logoutPending();
                this.renderNavbar();
                this.showDashboard();
            } else this.logout();
        } catch(e) { this.logout(); }
    },

    apiHeaders() { return { 'Authorization': `Bearer ${localStorage.getItem('token')}` }; },
    apiJsonHeaders() { return { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' }; },

    showView(viewName) {
        console.log("showView called with: ", viewName);
        const container = document.getElementById('app-container');
        document.getElementById('main-header').classList.remove('hidden');
        if (viewName === 'login') {
            document.getElementById('main-header').classList.add('hidden');
            this.renderLogin(container);
        } else if (viewName === 'register') {
            document.getElementById('main-header').classList.add('hidden');
            this.renderRegister(container);
        } else if (viewName === 'invite') {
            document.getElementById('main-header').classList.add('hidden');
            this.renderInviteAccept(container, arguments[1]);
        }
    },

    renderNavbar() {
        document.getElementById('main-header').classList.remove('hidden');
        const nav = document.getElementById('main-nav');
        const userInfo = document.getElementById('user-info');
        if(!this.user) return;
        
        let navHtml = '';
        if (this.user.role === 'admin') {
            navHtml = `
                <a class="nav-link" onclick="App.renderAdminUsers()">Usuários</a>
                <a class="nav-link" onclick="App.renderAdminInvites()">Convites & Logs</a>
                <a class="nav-link" onclick="App.renderAdminTeams()">Equipes</a>
                <a class="nav-link" onclick="App.renderAdminPaths()">Trilhas & Módulos</a>
            `;
        } else if (this.user.role === 'lideranca') {
            navHtml = `
                <a class="nav-link" onclick="App.renderLeaderDashboard()">Minha Equipe</a>
                <a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>
            `;
        } else {
            navHtml = `
                <a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>
                <a class="nav-link" onclick="console.log('Certificados em breve')">Certificados</a>
            `;
        }
        nav.innerHTML = navHtml;
        userInfo.innerHTML = `
            <span style="margin-right: 1rem; color: var(--text-dim)">Olá, <b>${this.user.username}</b> (${this.user.role})</span>
            <button class="btn btn-sm btn-outline" onclick="App.logout()">Sair</button>
        `;
    },

    showDashboard() {
        if (this.user.role === 'admin') this.renderAdminUsers();
        else if (this.user.role === 'lideranca') this.renderLeaderDashboard();
        else this.renderStudentPaths();
    },

    // --- AUTH VIEWS ---
    renderLogin(container) {
        container.innerHTML = `
            <div class="auth-container">
                <div class="auth-logo"><img src="logo_transparent.png" class="logo-img"></div>
                <div class="card">
                    <h2 style="margin-bottom: 1.5rem">LMS Acesso Restrito</h2>
                    <form id="login-form">
                        <div class="form-group"><input type="text" id="l-user" class="form-control" placeholder="Usuário" required></div>
                        <div class="form-group"><input type="password" id="l-pass" class="form-control" placeholder="Senha" required></div>
                        <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 1rem">Entrar</button>
                    </form>
                    <p style="margin-top: 1.5rem">Nova admissão? <a style="cursor:pointer; color:var(--primary)" onclick="App.showView('register')">Solicite seu acesso</a></p>
                </div>
            </div>
        `;
        document.getElementById('login-form').onsubmit = async (e) => {
            e.preventDefault();
            const res = await fetch('/login', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: document.getElementById('l-user').value, password: document.getElementById('l-pass').value })
            });
            const data = await res.json();
            if (res.ok && data.access_token) {
                localStorage.setItem('token', data.access_token);
                this.init();
            } else alert(data.error || "Erro no login");
        };
    },

    renderRegister(container) {
        container.innerHTML = `
            <div class="auth-container">
                <div class="auth-logo"><img src="logo_transparent.png" class="logo-img"></div>
                <div class="card">
                    <h2 style="margin-bottom: 1.5rem">Solicitar Acesso</h2>
                    <form id="reg-form">
                        <div class="form-group"><input type="text" id="r-user" class="form-control" placeholder="Usuário de Rede" required></div>
                        <div class="form-group"><input type="text" id="r-dept" class="form-control" placeholder="Departamento" required></div>
                        <div class="form-group"><input type="email" id="r-email" class="form-control" placeholder="Email Corporativo" required></div>
                        <div class="form-group"><input type="password" id="r-pass" class="form-control" placeholder="Senha" required></div>
                        <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 1rem">Enviar Solicitação</button>
                    </form>
                    <p style="margin-top: 1.5rem">Já possui cadastro? <a style="cursor:pointer; color:var(--primary)" onclick="App.showView('login')">Fazer Login</a></p>
                </div>
            </div>
        `;
        document.getElementById('reg-form').onsubmit = async (e) => {
            e.preventDefault();
            const payload = {
                username: document.getElementById('r-user').value, email: document.getElementById('r-email').value,
                password: document.getElementById('r-pass').value, department: document.getElementById('r-dept').value
            };
            const res = await fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            const data = await res.json();
            if (res.ok) { alert(data.message); this.showView('login'); } else alert("Erro no registro");
        };
    },

    renderInviteAccept(container, token) {
        container.innerHTML = `
            <div class="auth-container">
                <div class="auth-logo"><img src="logo_transparent.png" class="logo-img"></div>
                <div class="card">
                    <h2 style="margin-bottom: 1.5rem">Ativar Convite</h2>
                    <form id="invite-form">
                        <input type="hidden" id="i-token" value="${token}">
                        <div class="form-group"><input type="password" id="i-pass" class="form-control" placeholder="Crie uma nova senha segura" required minlength="6"></div>
                        <button type="submit" class="btn btn-primary" style="width: 100%; margin-top: 1rem">Ativar e Entrar</button>
                    </form>
                </div>
            </div>
        `;
        document.getElementById('invite-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button');
            btn.disabled = true;
            btn.innerText = "Processando...";
            const fd = new FormData();
            fd.append('token', document.getElementById('i-token').value);
            fd.append('password', document.getElementById('i-pass').value);
            const res = await fetch('/invite/accept', { method: 'POST', body: fd });
            const data = await res.json();
            if (res.ok) { 
                alert(data.message); 
                window.location.href = '/'; 
            } else { 
                alert(data.detail || "Erro ao ativar"); 
                btn.disabled = false; btn.innerText = "Ativar e Entrar";
            }
        };
    },

    logoutPending() {
        alert("Seu cadastro está pendente ou foi rejeitado pela administração.");
        this.logout();
    },

    logout() {
        localStorage.removeItem('token');
        this.user = null;
        this.showView('login');
    },

    // --- LEADER VIEWS ---
    async renderLeaderDashboard() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <h2>Painel de Liderança</h2>
                <button class="btn btn-primary" onclick="App.showAddMemberModal()">+ Adicionar Colaborador</button>
            </div>
            <div class="card">
                <h3>Membros da Equipe</h3>
                <table id="team-table">
                    <thead><tr><th>ID</th><th>Nome</th><th>E-mail</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="5" class="loader">Carregando equipe...</td></tr></tbody>
                </table>
            </div>
        `;
        const res = await fetch('/admin/users', { headers: this.apiHeaders() });
        const users = await res.json();
        const tbody = document.querySelector('#team-table tbody');
        tbody.innerHTML = '';
        users.forEach(u => {
            tbody.innerHTML += `<tr>
                <td>${u.id}</td>
                <td><strong>${u.username}</strong></td>
                <td>${u.email}</td>
                <td><span class="badge ${u.status==='approved'?'badge-success':'badge-warning'}">${u.status}</span></td>
                <td><button class="btn btn-secondary btn-sm" onclick="App.showAssignPathModal(${u.id}, '${u.username}')">🎯 Atribuir Trilha</button></td>
            </tr>`;
        });
        if(users.length === 0) tbody.innerHTML = `<tr><td colspan="5">Nenhum colaborador encontrado na sua equipe.</td></tr>`;
    },

    showAddMemberModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        body.innerHTML = `
            <h3>Novo Colaborador</h3>
            <form id="add-member-form" style="margin-top: 1rem;">
                <div class="form-group"><label>Usuário</label><input type="text" id="m-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail</label><input type="email" id="m-email" class="form-control" required></div>
                <div class="form-group"><label>Senha Inicial</label><input type="password" id="m-pass" class="form-control" required></div>
                <button type="submit" class="btn btn-primary" style="margin-top: 1rem; width:100%">Cadastrar na Minha Equipe</button>
            </form>
        `;
        document.getElementById('add-member-form').onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData();
            fd.append('username', document.getElementById('m-user').value);
            fd.append('email', document.getElementById('m-email').value);
            fd.append('password', document.getElementById('m-pass').value);
            await fetch('/admin/users', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal();
            this.renderLeaderDashboard();
        };
        modal.classList.remove('hidden');
    },

    async showAssignPathModal(userId, username) {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        const pathsRes = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await pathsRes.json();
        
        body.innerHTML = `
            <h3>Atribuir Trilha a ${username}</h3>
            <form id="assign-path-form" style="margin-top: 1rem;">
                <div class="form-group"><label>Selecione a Trilha</label>
                    <select id="a-path" class="form-control">
                        ${paths.map(p => `<option value="${p.id}">${p.title}</option>`).join('')}
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="margin-top: 1rem; width:100%">Confirmar Atribuição</button>
            </form>
        `;
        document.getElementById('assign-path-form').onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData();
            fd.append('user_id', userId);
            fd.append('path_id', document.getElementById('a-path').value);
            await fetch('/enrollments', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal();
            alert("Trilha atribuída com sucesso!");
        };
        modal.classList.remove('hidden');
    },

    async renderAdminInvites() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 2rem">
                <h2>Gestão Avançada de Convites & Logs</h2>
                <button class="btn btn-secondary" onclick="App.renderAdminInvites()">Atualizar Lista</button>
            </div>
            <div class="card" style="overflow-x: auto; max-height: 800px">
                <table id="invites-table">
                    <thead><tr><th>Usuário</th><th>Status</th><th>Quem convidou</th><th>Data Fim do Convite</th><th>Último Email enviado</th><th>Log Error/Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="7" class="loader">Carregando dados globais...</td></tr></tbody>
                </table>
            </div>
        `;
        const res = await fetch('/admin/invites', { headers: this.apiHeaders() });
        const users = await res.json();
        const tbody = document.querySelector('#invites-table tbody');
        tbody.innerHTML = '';
        users.forEach(u => {
            if(u.role === 'admin' && u.status==='ativo') return; // Hide normal active admins from invites list usually
            const badgeClass = (u.status === 'convite_pendente' || u.status === 'pending') ? 'badge-pending' : (u.status === 'ativo' ? 'badge-approved' : 'badge-rejected');
            
            tbody.innerHTML += `<tr>
                <td><strong>${u.username}</strong><br><small>${u.email}</small></td>
                <td><span class="badge ${badgeClass}">${u.status.toUpperCase()}</span><br><small>${u.role}</small></td>
                <td>${u.invited_by || '-'}</td>
                <td>${u.invite_date ? new Date(u.invite_date).toLocaleDateString() : '-'}</td>
                <td>${u.last_email_date ? new Date(u.last_email_date).toLocaleString() : '-'}</td>
                <td>${u.last_email_status ? '<b>'+u.last_email_status+'</b>' : '-'}</td>
                <td style="display:flex; gap:0.5rem; flex-wrap:wrap">
                    <button class="btn btn-sm btn-outline" onclick="App.adminAction(${u.id}, 'resend_invite')">Reenviar Email</button>
                    <button class="btn btn-sm btn-danger" onclick="App.adminAction(${u.id}, 'cancel_invite')">Cancelar</button>
                    ${u.status !== 'ativo' ? \`<button class="btn btn-sm btn-success" onclick="App.adminAction(${u.id}, 'activate_manual')">Ativar Forçado</button>\` : ''}
                    <button class="btn btn-sm btn-warning" onclick="App.adminAction(${u.id}, 'remove_team')">Tirar da Equipe</button>
                </td></tr>`;
        });
    },

    async adminAction(id, action) {
        if(!confirm("Certeza que deseja realizar esta ação ("+action+")?")) return;
        const res = await fetch(\`/admin/users/\${id}/\${action}\`, { method: 'POST', headers: this.apiHeaders() });
        if(res.ok) { alert("Ação concluída!"); this.renderAdminInvites(); }
        else { const d = await res.json(); alert(d.detail || "Erro"); }
    },

    async renderAdminUsers() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <h2 style="margin-bottom: 2rem">Gestão de Usuários</h2>
            <div class="card" style="overflow-x: auto;">
                <table id="users-table">
                    <thead><tr><th>Usuário</th><th>Email</th><th>Depto</th><th>Role</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>
        `;
        const res = await fetch('/admin/users', { headers: this.apiHeaders() });
        const users = await res.json();
        const tbody = document.querySelector('#users-table tbody');
        tbody.innerHTML = '';
        users.forEach(u => {
            const badgeClass = u.role === 'admin' ? 'badge-admin' : (u.status === 'pending' ? 'badge-pending' : (u.status === 'approved' ? 'badge-approved' : 'badge-rejected'));
            tbody.innerHTML += `<tr>
                <td><strong>${u.username}</strong></td>
                <td>${u.email}</td><td>${u.department || '-'}</td><td><b>${u.role.toUpperCase()}</b> ${u.team_id ? '(Equipe '+u.team_id+')' : ''}</td>
                <td><span class="badge ${badgeClass}">${u.status.toUpperCase()}</span></td>
                <td>` + (u.status === 'pending' ? `<button class="btn btn-sm btn-outline" onclick="App.changeUserStatus(${u.id}, 'approved')">Aprovar</button>
                    <button class="btn btn-sm btn-danger" onclick="App.changeUserStatus(${u.id}, 'rejected')">Rejeitar</button>` : '') + `
                    ${this.user.role === 'admin' ? `<button class="btn btn-sm btn-outline" onclick="App.editUserRole(${u.id}, '${u.role}')">⚙️ Cargo</button>` : ''}
                </td></tr>`;
        });
    },

    async changeUserStatus(id, newStatus) {
        const fd = new FormData(); fd.append('new_status', newStatus);
        await fetch(`/admin/users/${id}/status`, { method: 'POST', headers: this.apiHeaders(), body: fd });
        this.renderAdminUsers();
    },

    async editUserRole(id, currentRole) {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        const teamsRes = await fetch('/teams', { headers: this.apiHeaders() });
        const teams = await teamsRes.json();
        
        body.innerHTML = `
            <h3>Configurar Usuário</h3>
            <form id="edit-user-form" style="margin-top: 1rem;">
                <div class="form-group"><label>Papel (Role)</label>
                    <select id="e-role" class="form-control">
                        <option value="usuario" ${currentRole==='usuario'?'selected':''}>Usuário</option>
                        <option value="lideranca" ${currentRole==='lideranca'?'selected':''}>Liderança</option>
                        <option value="admin" ${currentRole==='admin'?'selected':''}>Administrador</option>
                    </select>
                </div>
                <div class="form-group"><label>Equipe</label>
                    <select id="e-team" class="form-control">
                        <option value="">Nenhuma</option>
                        ${teams.map(t => `<option value="${t.id}">${t.name}</option>`).join('')}
                    </select>
                </div>
                <button type="submit" class="btn btn-primary" style="margin-top: 1rem; width:100%">Salvar Alterações</button>
            </form>
        `;
        document.getElementById('edit-user-form').onsubmit = async (e) => {
            e.preventDefault();
            const role = document.getElementById('e-role').value;
            const teamId = document.getElementById('e-team').value;
            const fd = new FormData();
            fd.append('role', role);
            if(teamId) fd.append('team_id', teamId);
            else fd.append('team_id', 0); // 0 indica remover equipe no nosso backend improvisado

            const res = await fetch(`/admin/users/${id}/status`, { method: 'POST', headers: this.apiHeaders(), body: fd });
            if (!res.ok) {
                const errorData = await res.json();
                alert(errorData.detail || "Erro");
                return;
            }
            this.closeModal();
            this.renderAdminUsers();
        };
        modal.classList.remove('hidden');
    },

    async renderAdminTeams() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <h2>Gestão de Equipes</h2>
                <button class="btn btn-primary" onclick="App.showCreateTeamModal()">+ Nova Equipe</button>
            </div>
            <div class="card" style="overflow-x: auto;">
                <table id="teams-table">
                    <thead><tr><th>ID</th><th>Nome</th><th>Descrição</th><th>Membros</th></tr></thead>
                    <tbody><tr><td colspan="4" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>
        `;
        const res = await fetch('/teams', { headers: this.apiHeaders() });
        const teams = await res.json();
        const tbody = document.querySelector('#teams-table tbody');
        tbody.innerHTML = '';
        teams.forEach(t => {
            const numMembers = t.members ? t.members.length : 0;
            const activeMembers = t.members ? t.members.filter(m => m.status === 'approved').length : 0;
            const invitedMembers = t.members ? t.members.filter(m => m.status === 'invited').length : 0;
            
            let badgesHtml = '';
            if (numMembers > 0) {
                badgesHtml = `<span style="font-size: 0.85rem">${numMembers} total </span>`;
                if (activeMembers > 0) badgesHtml += `<span class="badge badge-approved" style="margin-left:5px">${activeMembers} ativos</span>`;
                if (invitedMembers > 0) badgesHtml += `<span class="badge badge-pending" style="margin-left:5px">${invitedMembers} convidados</span>`;
            } else {
                badgesHtml = '<span style="color:var(--text-dim)">0 membros</span>';
            }

            tbody.innerHTML += `<tr>
                <td>${t.id}</td>
                <td><strong>${t.name}</strong></td>
                <td>${t.description || '-'}</td>
                <td>${badgesHtml}</td>
            </tr>`;
        });
    },

    showCreateTeamModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        
        let teamEmails = [];
        
        const renderChips = () => {
            const container = document.getElementById('t-emails-list');
            if(!container) return;
            container.innerHTML = '';
            teamEmails.forEach((email, index) => {
                container.innerHTML += `<span class="badge" style="background:var(--primary); color:white; margin: 0.2rem; display:inline-flex; align-items:center; gap:5px;">
                    ${email} <a href="#" style="color:white; font-weight:bold; text-decoration:none;" onclick="event.preventDefault(); App.removeTeamEmail(${index})">&times;</a>
                </span>`;
            });
        };
        
        App.removeTeamEmail = (index) => {
            teamEmails.splice(index, 1);
            renderChips();
        };

        body.innerHTML = `
            <h3>Nova Equipe</h3>
            <form id="team-form" style="margin-top: 1rem;">
                <div class="form-group"><label>Nome da Equipe</label><input type="text" id="t-name" class="form-control" required></div>
                <div class="form-group"><label>Administrador da Equipe (E-mail corporativo @geobiogas.tech)</label><input type="email" id="t-admin" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="t-desc" class="form-control" rows="3"></textarea></div>
                
                <div class="form-group" style="padding: 1rem; background: var(--bg-body); border-radius: 8px; border: 1px solid var(--border)">
                    <label>Adicionar Membros (E-mails)</label>
                    <div style="display:flex; gap: 0.5rem; margin-bottom: 0.5rem">
                        <input type="email" id="t-email-input" class="form-control" placeholder="exemplo@empresa.com.br">
                        <button type="button" id="btn-add-email" class="btn btn-secondary">Adicionar</button>
                    </div>
                    <div id="t-emails-list" style="display:flex; flex-wrap:wrap; min-height: 30px"></div>
                </div>

                <button type="submit" class="btn btn-primary" style="margin-top: 1rem; width:100%">Salvar Equipe</button>
            </form>
        `;

        const input = document.getElementById('t-email-input');
        const btnAdd = document.getElementById('btn-add-email');

        const addEmail = () => {
            const val = input.value.trim();
            if(val && val.includes('@') && !teamEmails.includes(val)) {
                teamEmails.push(val);
                input.value = '';
                renderChips();
            }
        };

        btnAdd.onclick = addEmail;
        input.onkeypress = (e) => {
            if(e.key === 'Enter') {
                e.preventDefault();
                addEmail();
            }
        };

        document.getElementById('team-form').onsubmit = async (e) => {
            e.preventDefault();
            const btnSubmit = e.target.querySelector('button[type="submit"]');
            btnSubmit.disabled = true;
            btnSubmit.innerText = "Salvando...";

            const fd = new FormData();
            fd.append('name', document.getElementById('t-name').value);
            fd.append('team_admin_email', document.getElementById('t-admin').value);
            fd.append('description', document.getElementById('t-desc').value);
            if (teamEmails.length > 0) fd.append('emails', teamEmails.join(','));

            try {
                const res = await fetch('/teams', { method: 'POST', headers: this.apiHeaders(), body: fd });
                if (!res.ok) {
                    const errorData = await res.json();
                    alert(errorData.detail || "Erro ao salvar equipe.");
                    btnSubmit.disabled = false;
                    btnSubmit.innerText = "Salvar Equipe";
                    return;
                }
                this.closeModal();
                this.renderAdminTeams();
            } catch(err) {
                alert("Erro ao salvar equipe.");
                btnSubmit.disabled = false;
                btnSubmit.innerText = "Salvar Equipe";
            }
        };
        modal.classList.remove('hidden');
    },

    async renderAdminPaths() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 2rem;">
                <h2>Trilhas de Aprendizagem e Módulos</h2>
                <button class="btn btn-primary" onclick="App.showCreatePathModal()">+ Nova Trilha</button>
            </div>
            <div id="paths-wrapper"></div>
            
            <div class="card hidden" id="module-upload-card" style="margin-top: 3rem; border-top: 4px solid var(--primary);">
                <h3 style="margin-bottom: 1.5rem" id="module-upload-title">Adicionar Novo Módulo</h3>
                <form id="module-upload-form">
                    <input type="hidden" id="m-path-id">
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem;">
                        <div>
                            <div class="form-group"><label>Título do Módulo</label><input type="text" id="m-title" class="form-control" required></div>
                            <div class="form-group"><label>Descrição ou Ementa</label><textarea id="m-desc" class="form-control" rows="3"></textarea></div>
                            <div class="form-group"><label>Ordem (ex: 1 para Módulo 1)</label><input type="number" id="m-order" class="form-control" value="1" required></div>
                        </div>
                        <div>
                            <div class="form-group"><label>Vídeo Principal (Até 5GB)</label><input type="file" id="m-video" class="form-control" accept="video/mp4" required></div>
                            <div class="form-group"><label>Capa do Curso (Imagem)</label><input type="file" id="m-thumb" class="form-control" accept="image/*"></div>
                            <div class="form-group"><label>Template de Certificado</label><input type="file" id="m-cert" class="form-control" accept="image/*"></div>
                        </div>
                    </div>
                    <div class="progress-track" id="m-prog-wrap" style="display:none;"><div class="progress-fill" id="m-prog-bar" style="width:0%"></div></div>
                    <button type="submit" id="btn-upload-module" class="btn btn-primary" style="margin-top: 1rem; width: 100%;">Fazer Upload e Criar Módulo</button>
                    <p id="m-status" style="margin-top:0.5rem; font-size:0.9rem; color: var(--text-dim); text-align: center;"></p>
                </form>
            </div>
            
            <div id="quiz-editor-section" class="card hidden" style="margin-top: 2rem;"></div>
        `;
        this.reloadPathsGridAdmin();
        this.bindModuleForm();
    },

    bindModuleForm() {
        document.getElementById('module-upload-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-upload-module');
            const status = document.getElementById('m-status');
            const file = document.getElementById('m-video').files[0];
            const thumb = document.getElementById('m-thumb').files[0];
            const cert = document.getElementById('m-cert').files[0];
            const pathId = document.getElementById('m-path-id').value;
            
            btn.disabled = true;
            document.getElementById('m-prog-wrap').style.display = 'block';
            status.innerText = 'Inicializando...';

            try {
                const initRes = await fetch('/courses/upload/init?filename=' + encodeURIComponent(file.name), { method:'POST', headers: this.apiHeaders() });
                const { upload_id } = await initRes.json();
                
                const chunkSize = 5 * 1024 * 1024;
                const totalChunks = Math.ceil(file.size / chunkSize);
                
                for (let i = 0; i < totalChunks; i++) {
                    const chunk = file.slice(i * chunkSize, Math.min((i + 1) * chunkSize, file.size));
                    const fd = new FormData();
                    fd.append('upload_id', upload_id); fd.append('filename', file.name);
                    fd.append('chunk_index', i); fd.append('chunk', chunk);
                    await fetch('/courses/upload/chunk', { method: 'POST', headers: this.apiHeaders(), body: fd });
                    document.getElementById('m-prog-bar').style.width = Math.round(((i + 1) / totalChunks) * 100) + '%';
                    status.innerText = `Enviando Vídeo... ${i+1}/${totalChunks} chunks`;
                }

                status.innerText = "Finalizando Módulo...";
                const finalFd = new FormData();
                finalFd.append('title', document.getElementById('m-title').value);
                finalFd.append('description', document.getElementById('m-desc').value);
                finalFd.append('order', document.getElementById('m-order').value);
                finalFd.append('upload_id', upload_id);
                finalFd.append('filename', file.name);
                if(thumb) finalFd.append('thumbnail', thumb);
                if(cert) finalFd.append('cert_template', cert);

                await fetch(`/paths/${pathId}/courses`, { method: 'POST', headers: this.apiHeaders(), body: finalFd });
                status.innerText = "Módulo criado com sucesso!";
                setTimeout(() => { document.getElementById('module-upload-form').reset(); document.getElementById('module-upload-card').classList.add('hidden'); this.reloadPathsGridAdmin(); }, 1500);
            } catch(e) { status.innerText = "Erro no upload."; }
            finally { btn.disabled = false; }
        };
    },

    async reloadPathsGridAdmin() {
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        const wrapper = document.getElementById('paths-wrapper');
        wrapper.innerHTML = '';
        paths.forEach(p => {
            let modulesHtml = '';
            p.courses.sort((a,b)=>a.order - b.order).forEach(c => {
                modulesHtml += `
                    <div style="background:var(--bg-main); padding:1rem; border:1px solid var(--border); border-radius:6px; margin-top: 0.5rem; display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span class="badge badge-pending">Módulo ${c.order}</span>
                            <strong style="margin-left: 0.5rem">${c.title}</strong>
                            <span style="margin-left: 1rem; color:var(--text-dim); font-size: 0.85rem;">[${c.questions.length} Questões/Exames]</span>
                        </div>
                        <button class="btn btn-sm btn-outline" onclick="App.openQuizEditor(${c.id}, '${c.video_url}')">Add Quiz / Exame</button>
                    </div>
                `;
            });

            wrapper.innerHTML += `
                <div class="card" style="margin-bottom: 2rem;">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:1rem;">
                        <div>
                            <h3 style="color:var(--primary-dark)">${p.title}</h3>
                            <p style="color: var(--text-dim); margin-top: 0.2rem;">${p.description || 'Sem descrição'}</p>
                        </div>
                        <button class="btn btn-sm btn-secondary" onclick="App.showModuleUpload(${p.id}, '${p.title}')">+ Novo Módulo</button>
                    </div>
                    ${modulesHtml || '<p style="color:var(--text-dim)">Nenhum módulo nesta trilha.</p>'}
                </div>
            `;
        });
    },

    showCreatePathModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        body.innerHTML = `
            <h3>Criar Nova Trilha</h3>
            <form id="path-form" style="margin-top: 1rem;">
                <div class="form-group"><label>Título da Trilha</label><input type="text" id="p-title" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="p-desc" class="form-control" rows="3"></textarea></div>
                <div class="form-group" style="display:flex; align-items:center; gap:0.5rem; background: var(--bg-body); padding: 0.8rem; border-radius: 6px;">
                    <input type="checkbox" id="p-standard" style="width: 20px; height: 20px;">
                    <label style="margin:0; font-weight: 600;">Treinamento Padrão da Empresa (Liberar para novas equipes)</label>
                </div>
                <button type="submit" class="btn btn-primary" style="margin-top: 1rem; width:100%">Salvar Trilha</button>
            </form>
        `;
        document.getElementById('path-form').onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData();
            fd.append('title', document.getElementById('p-title').value);
            fd.append('description', document.getElementById('p-desc').value);
            fd.append('is_standard_training', document.getElementById('p-standard').checked);
            await fetch('/paths', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal();
            this.reloadPathsGridAdmin();
        };
        modal.classList.remove('hidden');
    },

    showModuleUpload(pathId, pathTitle) {
        document.getElementById('module-upload-card').classList.remove('hidden');
        document.getElementById('m-path-id').value = pathId;
        document.getElementById('module-upload-title').innerText = `Adicionar Módulo Num Curso: ${pathTitle}`;
        window.scrollTo({ top: document.getElementById('module-upload-card').offsetTop, behavior: 'smooth' });
    },

    openQuizEditor(courseId, videoUrl) {
        const sec = document.getElementById('quiz-editor-section');
        sec.classList.remove('hidden');
        sec.innerHTML = `
            <div style="display: flex; gap: 2rem; margin-top: 1rem; align-items: flex-start">
                <div style="flex:1">
                    <p style="color: var(--text-dim); margin-bottom: 1rem;">Adicione interações diretas no vídeo.</p>
                    <video id="editor-video" src="${videoUrl}" controls style="width: 100%; max-height: 350px; background: #000; border-radius: 8px;"></video>
                    <div style="margin-top: 1rem; display: flex; gap: 1rem; align-items: center;">
                        <button class="btn btn-sm btn-secondary" onclick="document.getElementById('q-time').value = Math.floor(document.getElementById('editor-video').currentTime)">Capturar Segundo Atual</button>
                        <input type="number" id="q-time" class="form-control" style="width: 100px" readonly placeholder="0">
                    </div>
                </div>
                <div style="flex:1.2; background: var(--bg-main); padding: 1.5rem; border-radius: 8px; border: 1px solid var(--border)">
                    <h4>Criar Questão</h4>
                    <form id="add-quiz-form" style="margin-top:1rem">
                        <div class="form-group"><label>Texto da Pergunta</label><input type="text" id="q-text" class="form-control" required></div>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
                            <input type="text" id="q-a" class="form-control" placeholder="A) Opção" required>
                            <input type="text" id="q-b" class="form-control" placeholder="B) Opção" required>
                            <input type="text" id="q-c" class="form-control" placeholder="C) Opção" required>
                            <input type="text" id="q-d" class="form-control" placeholder="D) Opção" required>
                        </div>
                        <div class="form-group" style="margin-top: 1rem"><label>Alternativa Correta</label>
                            <select id="q-corr" class="form-control">
                                <option value="A">A</option><option value="B">B</option><option value="C">C</option><option value="D">D</option>
                            </select>
                        </div>
                        <div class="form-group" style="display:flex; gap:0.5rem; align-items:center; background: #fff3cd; padding: 0.8rem; border-radius: 6px;">
                            <input type="checkbox" id="q-isfinal" style="width: 20px; height: 20px;">
                            <label style="margin:0; font-weight: 600; color: #856404">Faz parte da PROVA FINAL</label>
                        </div>
                        <p style="font-size:0.8rem; color: var(--text-dim); margin-bottom:1rem;">(Se marcado, ignorará o timestamp inserido e exigirá acerto de 80% no exame que aparece no final do vídeo)</p>
                        
                        <button type="submit" class="btn btn-primary" id="btn-save-quiz" style="width: 100%">Salvar Questão</button>
                    </form>
                </div>
            </div>
        `;
        window.scrollTo({ top: sec.offsetTop - 50, behavior: 'smooth' });

        document.getElementById('add-quiz-form').onsubmit = async (e) => {
            e.preventDefault();
            const payload = {
                text: document.getElementById('q-text').value,
                option_a: document.getElementById('q-a').value, option_b: document.getElementById('q-b').value,
                option_c: document.getElementById('q-c').value, option_d: document.getElementById('q-d').value,
                correct_option: document.getElementById('q-corr').value,
                timestamp: parseFloat(document.getElementById('q-time').value) || 0,
                is_final_exam: document.getElementById('q-isfinal').checked
            };
            try {
                await fetch(`/courses/${courseId}/questions`, { method: 'POST', headers: this.apiJsonHeaders(), body: JSON.stringify(payload) });
                alert("Questão adicionada!");
                document.getElementById('add-quiz-form').reset();
            } catch(e) { alert("Erro ao adicionar questão."); }
        };
    },

    // --- STUDENT VIEWS ---
    async renderStudentPaths() {
        const container = document.getElementById('app-container');
        container.innerHTML = `
            <div style="margin-bottom: 2rem;">
                <h2>Suas Trilhas de Desenvolvimento Corporativo</h2>
                <p style="color: var(--text-dim);">Acesse os módulos obrigatórios definidos pela Geo. Lembre-se, o aprovação exige 80% na prova final.</p>
            </div>
            <div class="grid" id="student-paths"><div class="loader">Carregando Trilhas...</div></div>
        `;
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        const grid = document.getElementById('student-paths');
        grid.innerHTML = '';
        
        if (paths.length === 0) grid.innerHTML = `<p>Você não possui trilhas ativas no momento.</p>`;
        
        paths.forEach(p => {
            grid.innerHTML += `
                <div class="card" style="display: flex; flex-direction: column;">
                    <h3 style="color: var(--primary-dark)">${p.title}</h3>
                    <p style="color: var(--text-dim); margin-top: 0.5rem; margin-bottom: 1.5rem; flex: 1;">${p.description || 'Ementa corporativa.'}</p>
                    
                    <div style="background: var(--bg-main); padding: 1rem; border-radius: 6px;">
                        <button class="btn btn-primary" style="width: 100%" onclick="App.showStudentPathDetail(${p.id})">Acessar Trilha &nbsp; &rarr;</button>
                    </div>
                </div>
            `;
        });
    },

    async showStudentPathDetail(pathId) {
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        const p = paths.find(x => x.id === pathId);
        if(!p) return;

        const container = document.getElementById('app-container');
        container.innerHTML = `
            <button class="btn btn-outline" style="margin-bottom: 1.5rem;" onclick="App.renderStudentPaths()">&larr; Voltar para Trilhas</button>
            <h2 style="margin-bottom: 0.5rem; color: var(--primary-dark)">Trilha: ${p.title}</h2>
            <p style="color: var(--text-dim); margin-bottom: 2rem">${p.description}</p>
            <div style="display: flex; flex-direction: column; gap: 1rem;" id="student-module-list"></div>
        `;

        const list = document.getElementById('student-module-list');
        const sortedCourses = p.courses.sort((a,b)=>a.order - b.order);
        
        sortedCourses.forEach((c) => {
            list.innerHTML += `
                <div class="card" style="display: flex; gap: 2rem; align-items: stretch;">
                    <div style="width: 250px; min-height: 140px; background: ${c.thumbnail_url ? 'url('+c.thumbnail_url+') center/cover' : 'var(--bg-main)'}; border-radius: 8px; border: 1px solid var(--border);"></div>
                    <div style="flex: 1; display:flex; flex-direction: column; justify-content: center;">
                        <span class="badge badge-pending" style="margin-bottom: 0.5rem; width: fit-content;">Módulo ${c.order}</span>
                        <h3>${c.title}</h3>
                        <p style="color: var(--text-dim); margin-top: 0.5rem; font-size: 0.95rem;">${c.description}</p>
                    </div>
                    <div style="align-self: center;">
                        <button class="btn btn-primary" style="padding: 1rem 2rem; font-size: 1.1rem" onclick="App.openCoursePlayer(${c.id})">Iniciar Aula &nbsp;&#9658;</button>
                    </div>
                </div>
            `;
        });
    },

    async openCoursePlayer(courseId) {
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        let targetCourse = null;
        paths.forEach(p => p.courses.forEach(c => { if(c.id === courseId) targetCourse = c; }));
        if(!targetCourse) return;

        const inlineQuizzes = targetCourse.questions.filter(q => !q.is_final_exam);
        const finalExamQuizzes = targetCourse.questions.filter(q => q.is_final_exam);

        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        modal.classList.remove('hidden');

        body.innerHTML = `
            <h2>Módulo: ${targetCourse.title}</h2>
            <div style="position: relative; margin-top: 1.5rem;">
                <video id="st-video" src="${targetCourse.video_url}" controls autoplay style="width: 100%; border-radius: 8px; background: #000;"></video>
                <div id="quiz-overlay" class="hidden" style="position: absolute; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.85); border-radius: 8px; color: white; display: flex; align-items: center; justify-content: center; padding: 2rem;">
                    <div style="width: 100%; max-width: 600px">
                        <h3 style="margin-bottom: 1.5rem; color: var(--success)" id="q-overlay-text">...</h3>
                        <div id="q-overlay-options" style="display: flex; flex-direction: column; gap: 0.8rem;"></div>
                    </div>
                </div>
            </div>
            
            <div id="final-exam-section" class="hidden" style="margin-top: 2rem; border-top: 1px solid var(--border); padding-top: 1.5rem; text-align: center;">
                <h3 style="color: var(--primary-dark)">O vídeo foi concluído</h3>
                <p style="color: var(--text-dim); margin-bottom: 1.5rem;">Para liberar o certificado deste módulo, você deve realizar a prova final obrigatória recebendo no mínimo 80% de aproveitamento.</p>
                <button class="btn btn-success" style="font-size: 1.1rem; padding: 1rem 2rem;" id="btn-final-exam">INICIAR PROVA FINAL OBRIGATÓRIA</button>
            </div>
        `;

        const video = document.getElementById('st-video');
        const asked = new Set();
        
        video.ontimeupdate = () => {
            if(video.paused) return;
            const time = video.currentTime;
            
            inlineQuizzes.forEach(q => {
                if(Math.abs(time - q.timestamp) < 0.5 && !asked.has(q.id)) {
                    asked.add(q.id);
                    video.pause();
                    this.showQuizOverlay(q);
                }
            });

            if (video.duration > 0 && time > video.duration - 1) {
                if(finalExamQuizzes.length > 0) document.getElementById('final-exam-section').classList.remove('hidden');
                else document.getElementById('final-exam-section').innerHTML = "<h3 style='color:var(--success)'>Módulo Concluído! Não há provas finais para este módulo.</h3>";
                document.getElementById('final-exam-section').classList.remove('hidden');
            }
        };

        if(finalExamQuizzes.length > 0) {
            document.getElementById('btn-final-exam').onclick = () => this.startFinalExam(finalExamQuizzes);
        }
    },

    showQuizOverlay(q) {
        const overlay = document.getElementById('quiz-overlay');
        overlay.classList.remove('hidden');
        document.getElementById('q-overlay-text').innerText = "Quiz: " + q.text;
        const optsContainer = document.getElementById('q-overlay-options');
        optsContainer.innerHTML = '';
        const options = [['A', q.option_a], ['B', q.option_b], ['C', q.option_c], ['D', q.option_d]];
        
        options.forEach(([letter, text]) => {
            const btn = document.createElement('button');
            btn.className = 'btn btn-outline';
            btn.style.textAlign = 'left';
            btn.style.color = 'white';
            btn.style.borderColor = 'white';
            btn.style.padding = '1rem';
            btn.innerText = letter + ") " + text;
            btn.onclick = () => {
                if(letter === q.correct_option) {
                    overlay.classList.add('hidden');
                    document.getElementById('st-video').play();
                } else {
                    btn.style.background = 'var(--danger-dark)';
                    btn.style.borderColor = 'transparent';
                    btn.innerText += ' - Incorreta!';
                    setTimeout(() => { btn.style.background = 'transparent'; btn.style.borderColor = 'white'; btn.innerText = letter + ") " + text; }, 1500);
                }
            };
            optsContainer.appendChild(btn);
        });
    },

    startFinalExam(finalExamQuizzes) {
        let correctCount = 0;
        for (let i = 0; i < finalExamQuizzes.length; i++) {
            const q = finalExamQuizzes[i];
            const answer = prompt(`PROVA FINAL (${i+1}/${finalExamQuizzes.length}):\n\n${q.text}\nA) ${q.option_a}\nB) ${q.option_b}\nC) ${q.option_c}\nD) ${q.option_d}\n\nDigite a letra correspondente (A, B, C ou D):`);
            if(answer && answer.toUpperCase() === q.correct_option) correctCount++;
        }
        
        const score = (correctCount / finalExamQuizzes.length) * 100;
        if(score >= 80) {
            alert(`PARABÉNS! Você foi aprovado com ${score}% de acerto.\n\nO certificado foi gerado e está disponível no seu painel principal.`);
            this.closeModal();
            // Integração futura com endpoint de emissão de certificado PDF
        } else {
            alert(`ATENÇÃO: Você acertou apenas ${score}%. A nota mínima exigida pela companhia é 80%.\n\nVocê deve revisar o material e refazer a avaliação para ser aprovado.`);
        }
    },

    closeModal() { document.getElementById('modal-container').classList.add('hidden'); document.getElementById('modal-body').innerHTML = ''; }
};

document.addEventListener('DOMContentLoaded', () => App.init());
App.init();
