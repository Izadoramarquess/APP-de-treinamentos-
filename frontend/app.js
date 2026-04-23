console.log("GeoTrilha LMS carregado.");

const App = {
    user: null,
    currentPath: null,
    currentCourse: null,

    init() {
        const urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('view') === 'convite' && urlParams.get('token')) {
            this.showView('invite', urlParams.get('token')); return;
        }
        if (urlParams.get('view') === 'reset' && urlParams.get('token')) {
            this.showView('reset', urlParams.get('token')); return;
        }
        const token = localStorage.getItem('token');
        if (token) this.fetchCurrentUser(token);
        else this.showView('login');
    },

    async fetchCurrentUser(token) {
        try {
            const res = await fetch('/users/me', { headers: this.apiHeaders() });
            if (res.ok) {
                this.user = await res.json();
                if (this.user.status !== 'ativo' && this.user.status !== 'approved') return this.logoutPending();
                if (this.user.must_change_password) {
                    this.renderNavbar();
                    this.showForcePasswordChangeModal();
                } else {
                    this.renderNavbar();
                    this.showDashboard();
                }
            } else this.logout();
        } catch(e) { this.logout(); }
    },

    apiHeaders() { return { 'Authorization': `Bearer ${localStorage.getItem('token')}` }; },
    apiJsonHeaders() { return { 'Authorization': `Bearer ${localStorage.getItem('token')}`, 'Content-Type': 'application/json' }; },

    statusBadge(status) {
        const map = {
            'ativo':            { label: 'Ativo',      color: '#22c55e' },
            'approved':         { label: 'Aprovado',   color: '#22c55e' },
            'pending':          { label: 'Pendente',   color: '#f59e0b' },
            'convite_pendente': { label: 'Convidado',  color: '#3b82f6' },
            'invited':          { label: 'Convidado',  color: '#3b82f6' },
            'inactive':         { label: 'Inativo',    color: '#ef4444' },
            'cancelled':        { label: 'Cancelado',  color: '#ef4444' },
            'convite_expirado': { label: 'Expirado',   color: '#ef4444' },
            'rejected':         { label: 'Rejeitado',  color: '#ef4444' },
        };
        const s = (status || '').toLowerCase();
        const cfg = map[s] || { label: status || '-', color: '#888' };
        return `<span style="padding:3px 10px;border-radius:12px;font-size:0.75rem;font-weight:600;text-transform:uppercase;letter-spacing:0.03em;color:${cfg.color};background:${cfg.color}20;border:1px solid ${cfg.color}40">${cfg.label}</span>`;
    },

    actionBtn(label, onclick, variant = 'outline') {
        const styles = {
            outline:   'background:transparent;border:1px solid var(--border);color:var(--text-dim)',
            primary:   'background:var(--primary);border:1px solid var(--primary);color:white',
            success:   'background:#22c55e20;border:1px solid #22c55e60;color:#16a34a',
            danger:    'background:#ef444420;border:1px solid #ef444460;color:#dc2626',
            secondary: 'background:var(--bg-main);border:1px solid var(--border);color:var(--text)',
        };
        return `<button onclick="${onclick}" style="padding:4px 10px;border-radius:6px;font-size:0.8rem;cursor:pointer;white-space:nowrap;${styles[variant]||styles.outline}">${label}</button>`;
    },

    showCopyLinkModal(title, message, link) {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        body.innerHTML = `
            <h3 style="margin-bottom:0.5rem">${title}</h3>
            <p style="color:var(--text-dim);font-size:0.9rem;margin-bottom:1rem">${message}</p>
            <div style="padding:1rem;background:var(--bg-main);border:1px solid var(--border);border-radius:8px;word-break:break-all;font-family:monospace;font-size:0.85rem;color:var(--primary);margin-bottom:1rem;">
                ${link}
            </div>
            <div style="display:flex;gap:0.5rem;">
                <button type="button" class="btn btn-primary" style="flex:1" onclick="navigator.clipboard.writeText('${link}');this.textContent='Copiado!';setTimeout(()=>this.textContent='📋 Copiar link',2000)">📋 Copiar link</button>
                <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Fechar</button>
            </div>
        `;
        modal.classList.remove('hidden');
    },

    showView(viewName, extraParam) {
        const container = document.getElementById('app-container');
        document.getElementById('main-header').classList.remove('hidden');
        if (viewName === 'login') { document.getElementById('main-header').classList.add('hidden'); this.renderLogin(container); }
        else if (viewName === 'register') { document.getElementById('main-header').classList.add('hidden'); this.renderRegister(container); }
        else if (viewName === 'invite') { document.getElementById('main-header').classList.add('hidden'); this.renderInviteAccept(container, extraParam); }
        else if (viewName === 'forgot') { document.getElementById('main-header').classList.add('hidden'); this.renderForgotPassword(container); }
        else if (viewName === 'reset') { document.getElementById('main-header').classList.add('hidden'); this.renderResetPassword(container, extraParam); }
    },

    renderNavbar() {
        document.getElementById('main-header').classList.remove('hidden');
        const nav = document.getElementById('main-nav');
        const userInfo = document.getElementById('user-info');
        if (!this.user) return;
        let navHtml = '';
        if (this.user.role === 'admin') {
            navHtml = `<a class="nav-link" onclick="App.renderAdminUsers()">Usuários</a>
                <a class="nav-link" onclick="App.renderAdminInvites()">Convites & Logs</a>
                <a class="nav-link" onclick="App.renderAdminTeams()">Equipes</a>
                <a class="nav-link" onclick="App.renderAdminPaths()">Trilhas & Cursos</a>`;
        } else if (this.user.role === 'lideranca') {
            navHtml = `<a class="nav-link" onclick="App.renderLeaderDashboard()">Minha Equipe</a>
                <a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>`;
        } else {
            navHtml = `<a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>
                <a class="nav-link">Certificados</a>`;
        }
        nav.innerHTML = navHtml;
        userInfo.innerHTML = `<span style="margin-right:1rem;color:var(--text-dim);font-size:0.9rem">Olá, <b>${this.user.username}</b></span>
            <button onclick="App.logout()" style="padding:4px 12px;border-radius:6px;font-size:0.8rem;cursor:pointer;background:transparent;border:1px solid var(--border);color:var(--text-dim)">Sair</button>`;
    },

    showDashboard() {
        if (this.user.role === 'admin') this.renderAdminUsers();
        else if (this.user.role === 'lideranca') this.renderLeaderDashboard();
        else this.renderStudentPaths();
    },

    sectionHeader({ title, backLabel, backFn, actionLabel, actionFn, breadcrumbs } = {}) {
        let breadHtml = '';
        if (breadcrumbs && breadcrumbs.length) {
            breadHtml = `<nav style="font-size:0.85rem;color:var(--text-dim);margin-bottom:0.75rem">` +
                breadcrumbs.map((b, i) => i < breadcrumbs.length - 1
                    ? `<a href="#" onclick="${b.fn}" style="color:var(--primary)">${b.label}</a> &rsaquo; `
                    : `<span>${b.label}</span>`).join('') + `</nav>`;
        }
        const backBtn = backFn ? `<button onclick="${backFn}" style="padding:4px 10px;border-radius:6px;font-size:0.82rem;cursor:pointer;background:transparent;border:1px solid var(--border);color:var(--text-dim);margin-right:0.75rem">← ${backLabel||'Voltar'}</button>` : '';
        const actBtn  = actionFn ? `<button onclick="${actionFn}" style="padding:6px 14px;border-radius:6px;font-size:0.85rem;cursor:pointer;background:var(--primary);border:none;color:white">${actionLabel}</button>` : '';
        return `${breadHtml}<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem"><div style="display:flex;align-items:center">${backBtn}<h2 style="margin:0">${title}</h2></div>${actBtn}</div>`;
    },

    // --- AUTH ---
    renderLogin(container) {
        container.innerHTML = `<div class="auth-container">
            <div class="auth-logo"><img src="logo_transparent.png" style="height:70px;display:block;margin:0 auto 1.5rem"></div>
            <div class="card" style="border:none;box-shadow:var(--shadow-strong)">
                <h2 style="margin-bottom:1.5rem;font-weight:700">Acesso à GeoTrilha</h2>
                <form id="login-form">
                    <div class="form-group"><label>Usuário ou E-mail</label><input type="text" id="l-user" class="form-control" placeholder="colaborador@geobiogas.tech" required></div>
                    <div class="form-group"><label>Senha</label><input type="password" id="l-pass" class="form-control" placeholder="••••••••" required></div>
                    <div style="text-align:right;margin:-0.25rem 0 1rem"><a href="#" onclick="App.showView('forgot')" style="font-size:0.85rem;color:var(--primary)">Esqueci minha senha</a></div>
                    <button type="submit" class="btn btn-primary" style="width:100%">Entrar →</button>
                </form>
                <div style="margin-top:1.5rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:0.88rem;color:var(--text-dim)">
                    Novo colaborador? <a href="#" onclick="App.showView('register')" style="color:var(--primary);font-weight:600">Solicitar acesso</a>
                </div>
            </div></div>`;
        document.getElementById('login-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = 'Entrando...';
            const res = await fetch('/login', { method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username: document.getElementById('l-user').value, password: document.getElementById('l-pass').value }) });
            const data = await res.json();
            if (res.ok && data.access_token) { localStorage.setItem('token', data.access_token); this.init(); }
            else { alert(data.detail || 'Usuário ou senha inválidos.'); btn.disabled = false; btn.textContent = 'Entrar →'; }
        };
    },

    renderForgotPassword(container) {
        container.innerHTML = `<div class="auth-container">
            <div class="auth-logo"><img src="logo_transparent.png" style="height:70px;display:block;margin:0 auto 1.5rem"></div>
            <div class="card" style="border:none;box-shadow:var(--shadow-strong)">
                <h2 style="margin-bottom:0.5rem;font-weight:700">Recuperar senha</h2>
                <div style="padding: 1.5rem; background: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; margin-bottom: 1.5rem; color: #92400e; text-align: center;">
                    Para redefinir sua senha, entre em contato com o administrador do sistema.
                </div>
                <div style="margin-top:1.25rem;text-align:center">
                    <a href="#" onclick="App.showView('login')" class="btn btn-outline" style="display: block; width: 100%;">← Voltar ao login</a>
                </div>
            </div></div>`;
    },

    renderResetPassword(container, token) {
        container.innerHTML = `<div class="auth-container">
            <div class="auth-logo"><img src="logo_transparent.png" style="height:70px;display:block;margin:0 auto 1.5rem"></div>
            <div class="card" style="border:none;box-shadow:var(--shadow-strong)">
                <h2 style="margin-bottom:0.5rem;font-weight:700">Redefinir senha</h2>
                <p style="color:var(--text-dim);margin-bottom:1.5rem;font-size:0.9rem">Escolha uma nova senha para sua conta.</p>
                <form id="reset-form">
                    <input type="hidden" id="reset-token" value="${token}">
                    <div class="form-group"><label>Nova senha</label><input type="password" id="r-pass" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                    <div class="form-group"><label>Confirmar nova senha</label><input type="password" id="r-pass2" class="form-control" placeholder="Repita a senha" required minlength="6"></div>
                    <p id="reset-err" style="color:#ef4444;font-size:0.85rem;display:none;margin-bottom:0.5rem"></p>
                    <button type="submit" class="btn btn-primary" style="width:100%">Redefinir senha</button>
                </form>
                <div style="margin-top:1.25rem;text-align:center">
                    <a href="#" onclick="App.showView('login')" style="font-size:0.88rem;color:var(--primary)">← Voltar ao login</a>
                </div>
            </div></div>`;
        document.getElementById('reset-form').onsubmit = async (e) => {
            e.preventDefault();
            const pass = document.getElementById('r-pass').value;
            const pass2 = document.getElementById('r-pass2').value;
            const err = document.getElementById('reset-err');
            if (pass !== pass2) { err.textContent = 'As senhas não coincidem.'; err.style.display = 'block'; return; }
            const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = 'Salvando...';
            const fd = new FormData(); fd.append('token', document.getElementById('reset-token').value); fd.append('password', pass);
            const res = await fetch('/auth/reset-password', { method: 'POST', body: fd });
            if (res.ok) { alert('Senha redefinida! Faça login.'); window.location.href = '/'; }
            else { const d = await res.json(); err.textContent = d.detail || 'Token inválido ou expirado.'; err.style.display = 'block'; btn.disabled = false; btn.textContent = 'Redefinir senha'; }
        };
    },

    renderInviteAccept(container, token) {
        container.innerHTML = `<div class="auth-container">
            <div class="auth-logo"><img src="logo_transparent.png" style="height:70px;display:block;margin:0 auto 1.5rem"></div>
            <div class="card" style="border:none;box-shadow:var(--shadow-strong)">
                <h2 style="margin-bottom:0.5rem;font-weight:700">Ativar convite</h2>
                <p style="color:var(--text-dim);margin-bottom:1.5rem;font-size:0.9rem">Crie uma senha para ativar seu acesso ao GeoTrilha.</p>
                <form id="invite-form">
                    <input type="hidden" id="i-token" value="${token}">
                    <div class="form-group"><label>Senha</label><input type="password" id="i-pass" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                    <button type="submit" class="btn btn-primary" style="width:100%">Ativar acesso</button>
                </form>
            </div></div>`;
        document.getElementById('invite-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button'); btn.disabled = true; btn.textContent = 'Ativando...';
            const fd = new FormData(); fd.append('token', document.getElementById('i-token').value); fd.append('password', document.getElementById('i-pass').value);
            const res = await fetch('/invite/accept', { method: 'POST', body: fd });
            const data = await res.json();
            if (res.ok) { alert(data.message || 'Acesso ativado!'); window.location.href = '/'; }
            else { alert(data.detail || 'Erro ao ativar.'); btn.disabled = false; btn.textContent = 'Ativar acesso'; }
        };
    },

    renderRegister(container) {
        container.innerHTML = `<div class="auth-container">
            <div class="auth-logo"><img src="logo_transparent.png" style="height:70px;display:block;margin:0 auto 1.5rem"></div>
            <div class="card" style="border:none;box-shadow:var(--shadow-strong)">
                <h2 style="margin-bottom:1.5rem;font-weight:700">Solicitar acesso</h2>
                <form id="reg-form">
                    <div class="form-group"><label>Nome de usuário</label><input type="text" id="r-user" class="form-control" required></div>
                    <div class="form-group"><label>Departamento</label><input type="text" id="r-dept" class="form-control" required></div>
                    <div class="form-group"><label>E-mail corporativo</label><input type="email" id="r-email" class="form-control" placeholder="e-mail@geobiogas.tech" required></div>
                    <div class="form-group"><label>Senha</label><input type="password" id="r-pass" class="form-control" required></div>
                    <button type="submit" class="btn btn-primary" style="width:100%;margin-top:0.5rem">Enviar solicitação</button>
                </form>
                <div style="margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:0.88rem;color:var(--text-dim)">
                    Já tem acesso? <a href="#" onclick="App.showView('login')" style="color:var(--primary);font-weight:600">Fazer login</a>
                </div>
            </div></div>`;
        document.getElementById('reg-form').onsubmit = async (e) => {
            e.preventDefault();
            const payload = { username: document.getElementById('r-user').value, email: document.getElementById('r-email').value, password: document.getElementById('r-pass').value, department: document.getElementById('r-dept').value };
            const res = await fetch('/register', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
            if (res.ok) { alert('Solicitação enviada! Aguarde aprovação.'); this.showView('login'); }
            else { const d = await res.json(); alert(d.detail || 'Erro no registro.'); }
        };
    },

    showForcePasswordChangeModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        modal.classList.remove('hidden');
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) closeBtn.style.display = 'none';
        modal.onclick = (e) => { if (e.target === modal) e.stopPropagation(); };
        body.innerHTML = `
            <h3 style="margin-bottom:0.5rem">🔐 Troque sua senha</h3>
            <p style="color:var(--text-dim);font-size:0.9rem;margin-bottom:1.5rem">Por segurança, defina uma senha pessoal antes de continuar.</p>
            <form id="force-form">
                <div class="form-group"><label>Nova senha</label><input type="password" id="fc-p1" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                <div class="form-group"><label>Confirmar nova senha</label><input type="password" id="fc-p2" class="form-control" placeholder="Repita a senha" required minlength="6"></div>
                <p id="fc-err" style="color:#ef4444;font-size:0.85rem;display:none;margin-bottom:0.5rem"></p>
                <button type="submit" class="btn btn-primary" style="width:100%">Salvar e continuar</button>
            </form>`;
        document.getElementById('force-form').onsubmit = async (e) => {
            e.preventDefault();
            const p1 = document.getElementById('fc-p1').value;
            const p2 = document.getElementById('fc-p2').value;
            const err = document.getElementById('fc-err');
            if (p1 !== p2) { err.textContent = 'As senhas não coincidem.'; err.style.display = 'block'; return; }
            if (p1 === 'Mudar@123') { err.textContent = 'Escolha uma senha diferente da temporária.'; err.style.display = 'block'; return; }
            // FIX: campo correto é 'password', não 'new_password'
            const fd = new FormData(); fd.append('password', p1);
            const res = await fetch('/auth/change-password', { method: 'POST', headers: this.apiHeaders(), body: fd });
            if (res.ok) {
                this.user.must_change_password = false;
                if (closeBtn) closeBtn.style.display = '';
                this.closeModal(); this.showDashboard();
            } else { const d = await res.json(); err.textContent = d.detail || 'Erro ao trocar senha.'; err.style.display = 'block'; }
        };
    },

    logout() { localStorage.removeItem('token'); this.user = null; this.showView('login'); },
    logoutPending() { alert('Seu cadastro está pendente ou foi rejeitado.'); this.logout(); },

    // --- ADMIN: USUÁRIOS ---
    async renderAdminUsers() {
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Gestão de Usuários', actionLabel: '+ Convidar Usuário', actionFn: 'App.showInviteUserModal()' }) + `
            <div class="card" style="overflow-x:auto">
                <table id="u-table">
                    <thead><tr><th>Usuário</th><th>E-mail</th><th>Depto</th><th>Cargo</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>`;
        const res = await fetch('/admin/users', { headers: this.apiHeaders() });
        const users = await res.json();
        const tbody = document.querySelector('#u-table tbody');
        tbody.innerHTML = '';
        users.forEach(u => {
            tbody.innerHTML += `<tr>
                <td><strong>${u.username}</strong></td>
                <td style="font-size:0.85rem">${u.email}</td>
                <td style="font-size:0.85rem;color:var(--text-dim)">${u.department||'-'}</td>
                <td style="font-size:0.85rem">${u.role}</td>
                <td>${this.statusBadge(u.status)}</td>
                <td><div style="display:flex;gap:4px;flex-wrap:wrap">
                    ${u.status==='pending' ? this.actionBtn('✓ Aprovar',`App.changeUserStatus(${u.id},'approved')`,'success') : ''}
                    ${u.status==='pending' ? this.actionBtn('✕ Rejeitar',`App.changeUserStatus(${u.id},'rejected')`,'danger') : ''}
                    ${this.actionBtn('Cargo',`App.editUserRole(${u.id},'${u.role}',${u.team_id||0})`)}
                    ${this.actionBtn('🔑 Resetar',`App.triggerPasswordReset(${u.id},'${u.username}')`)}
                    ${this.user.id!==u.id ? this.actionBtn('🗑 Excluir',`App.deleteUser(${u.id},'${u.username}')`,'danger') : ''}
                </div></td>
            </tr>`;
        });
        if (!users.length) tbody.innerHTML = '<tr><td colspan="6" style="text-align:center;color:var(--text-dim)">Nenhum usuário encontrado.</td></tr>';
    },

    async changeUserStatus(id, status) {
        const fd = new FormData(); fd.append('new_status', status);
        await fetch(`/admin/users/${id}/status`, { method: 'POST', headers: this.apiHeaders(), body: fd });
        this.renderAdminUsers();
    },

    async showInviteUserModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        const teamsRes = await fetch('/teams', { headers: this.apiHeaders() });
        const teams = await teamsRes.json();
        body.innerHTML = `<h3 style="margin-bottom:1rem">Convidar Novo Usuário</h3>
            <form id="invite-user-form">
                <div class="form-group"><label>Nome de usuário</label><input type="text" id="iu-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail corporativo</label><input type="email" id="iu-email" class="form-control" required></div>
                <div class="form-group"><label>Cargo</label>
                    <select id="iu-role" class="form-control">
                        <option value="colaborador">Colaborador</option>
                        <option value="lideranca">Liderança</option>
                        <option value="admin">Administrador</option>
                    </select>
                </div>
                <div class="form-group"><label>Equipe</label>
                    <select id="iu-team" class="form-control">
                        <option value="">Nenhuma</option>
                        ${teams.map(t=>`<option value="${t.id}">${t.name}</option>`).join('')}
                    </select>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Gerar Convite</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('invite-user-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]'); btn.disabled = true; btn.textContent = 'Gerando...';
            const fd = new FormData();
            fd.append('username', document.getElementById('iu-user').value);
            fd.append('email', document.getElementById('iu-email').value);
            fd.append('role', document.getElementById('iu-role').value);
            const teamId = document.getElementById('iu-team').value;
            if (teamId) fd.append('team_id', teamId);
            
            const res = await fetch('/admin/users/invite', { method: 'POST', headers: this.apiHeaders(), body: fd });
            const data = await res.json();
            if (res.ok) {
                this.renderAdminUsers();
                this.showCopyLinkModal('Convite Gerado', 'Envie este link para o novo usuário ativar a conta:', data.invite_link);
            } else {
                alert(data.detail || 'Erro ao gerar convite.');
                btn.disabled = false; btn.textContent = 'Gerar Convite';
            }
        };
        modal.classList.remove('hidden');
    },

    async editUserRole(id, currentRole, currentTeam) {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        const teamsRes = await fetch('/teams', { headers: this.apiHeaders() });
        const teams = await teamsRes.json();
        body.innerHTML = `<h3 style="margin-bottom:1rem">Alterar cargo</h3>
            <form id="role-form">
                <div class="form-group"><label>Cargo</label>
                    <select id="e-role" class="form-control">
                        <option value="colaborador" ${currentRole==='colaborador'?'selected':''}>Colaborador</option>
                        <option value="lideranca" ${currentRole==='lideranca'?'selected':''}>Liderança</option>
                        <option value="admin" ${currentRole==='admin'?'selected':''}>Administrador</option>
                    </select>
                </div>
                <div class="form-group"><label>Equipe</label>
                    <select id="e-team" class="form-control">
                        <option value="">Nenhuma</option>
                        ${teams.map(t=>`<option value="${t.id}" ${currentTeam===t.id?'selected':''}>${t.name}</option>`).join('')}
                    </select>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('role-form').onsubmit = async (e) => {
            e.preventDefault();
            const fd = new FormData(); fd.append('role', document.getElementById('e-role').value);
            const res = await fetch(`/admin/users/${id}/role`, { method: 'POST', headers: this.apiHeaders(), body: fd });
            if (!res.ok) { alert((await res.json()).detail); return; }
            this.closeModal(); this.renderAdminUsers();
        };
        modal.classList.remove('hidden');
    },

    async deleteUser(id, username) {
        if (!confirm(`Excluir o usuário "${username}"? Esta ação não pode ser desfeita.`)) return;
        const res = await fetch(`/admin/users/${id}`, { method: 'DELETE', headers: this.apiHeaders() });
        if (res.ok) this.renderAdminUsers();
        else alert((await res.json()).detail || 'Erro ao excluir.');
    },

    async triggerPasswordReset(id, username) {
        if (!confirm(`Resetar a senha de "${username}" para a senha padrão? O usuário deverá criar uma nova no próximo login.`)) return;
        const res = await fetch(`/admin/users/${id}/reset-password`, { method: 'POST', headers: this.apiHeaders() });
        const data = await res.json();
        if (res.ok) {
            this.showCopyLinkModal('Senha Resetada', 'Envie este link para o usuário redefinir a senha:', data.reset_link);
        } else {
            alert(data.detail || 'Erro ao resetar.');
        }
    },

    // --- ADMIN: CONVITES ---
    async renderAdminInvites() {
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Convites & Logs', actionLabel: '↻ Atualizar', actionFn: 'App.renderAdminInvites()' }) + `
            <div class="card" style="overflow-x:auto">
                <table id="inv-table">
                    <thead><tr><th>Usuário</th><th>Status</th><th>Convidado por</th><th>Expira</th><th>Último email</th><th>Log</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="7" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>`;
        const res = await fetch('/admin/invites', { headers: this.apiHeaders() });
        const invites = await res.json();
        const tbody = document.querySelector('#inv-table tbody');
        tbody.innerHTML = '';
        if (!invites.length) { tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-dim)">Nenhum convite encontrado.</td></tr>'; return; }
        invites.forEach(i => {
            const expira = i.invite_date ? new Date(new Date(i.invite_date).getTime() + 7*24*60*60*1000).toLocaleDateString('pt-BR') : '-';
            tbody.innerHTML += `<tr>
                <td><strong>${i.username}</strong><br><small style="color:var(--text-dim)">${i.email}</small></td>
                <td>${this.statusBadge(i.status)}</td>
                <td style="font-size:0.85rem">${i.invited_by||'-'}</td>
                <td style="font-size:0.85rem">${expira}</td>
                <td style="font-size:0.85rem">${i.last_email_date ? new Date(i.last_email_date).toLocaleString('pt-BR') : '-'}</td>
                <td style="font-size:0.8rem;color:var(--text-dim)">${i.last_email_status||'-'}</td>
                <td><div style="display:flex;gap:4px;flex-wrap:wrap">
                    ${this.actionBtn('Reenviar',`App.adminAction(${i.id},'resend_invite')`)}
                    ${i.status!=='ativo' ? this.actionBtn('Ativar',`App.adminAction(${i.id},'activate_manual')`,'success') : ''}
                    ${i.status!=='ativo'&&i.status!=='convite_expirado' ? this.actionBtn('Cancelar',`App.adminAction(${i.id},'cancel_invite')`,'danger') : ''}
                </div></td>
            </tr>`;
        });
    },

    async adminAction(id, action) {
        if (!confirm('Confirmar ação?')) return;
        const res = await fetch(`/admin/users/${id}/${action}`, { method: 'POST', headers: this.apiHeaders() });
        const data = await res.json();
        if (res.ok) { 
            if (action === 'resend_invite' && data.invite_link) {
                this.showCopyLinkModal('Convite Reenviado', 'Envie este novo link para o usuário:', data.invite_link);
            } else {
                alert('Ação concluída!'); 
            }
            this.renderAdminInvites(); 
        } else { 
            alert(data.detail || 'Erro ao executar ação.'); 
        }
    },

    // --- ADMIN: EQUIPES ---
    async renderAdminTeams() {
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Gestão de Equipes', actionLabel: '+ Nova Equipe', actionFn: 'App.showCreateTeamModal()' }) + `
            <div class="card" style="overflow-x:auto">
                <table id="t-table">
                    <thead><tr><th>Nome</th><th>Descrição</th><th>Membros</th></tr></thead>
                    <tbody><tr><td colspan="3" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>`;
        const res = await fetch('/teams', { headers: this.apiHeaders() });
        const teams = await res.json();
        const tbody = document.querySelector('#t-table tbody');
        tbody.innerHTML = '';
        teams.forEach(t => {
            const total = t.members ? t.members.length : 0;
            tbody.innerHTML += `<tr><td><strong>${t.name}</strong></td><td style="font-size:0.85rem;color:var(--text-dim)">${t.description||'-'}</td><td style="font-size:0.85rem">${total} membro${total!==1?'s':''}</td></tr>`;
        });
        if (!teams.length) tbody.innerHTML = '<tr><td colspan="3" style="text-align:center;color:var(--text-dim)">Nenhuma equipe criada.</td></tr>';
    },

    showCreateTeamModal() {
        const modal = document.getElementById('modal-container');
        const body = document.getElementById('modal-body');
        let emails = [];
        const renderChips = () => {
            const el = document.getElementById('chips'); if (!el) return;
            el.innerHTML = emails.map((e,i) => `<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;background:var(--primary)20;border:1px solid var(--primary)40;border-radius:20px;font-size:0.8rem;margin:2px">${e} <a href="#" onclick="event.preventDefault();App._removeEmail(${i})" style="color:var(--primary);font-weight:bold;text-decoration:none">×</a></span>`).join('');
        };
        App._removeEmail = (i) => { emails.splice(i,1); renderChips(); };
        body.innerHTML = `<h3 style="margin-bottom:1rem">Nova Equipe</h3>
            <form id="team-form">
                <div class="form-group"><label>Nome da equipe</label><input type="text" id="t-name" class="form-control" required></div>
                <div class="form-group"><label>Líder (e-mail)</label><input type="email" id="t-admin" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="t-desc" class="form-control" rows="2"></textarea></div>
                <div class="form-group">
                    <label>Membros</label>
                    <div style="display:flex;gap:0.5rem;margin-bottom:0.5rem">
                        <input type="email" id="t-email-input" class="form-control" placeholder="e-mail@geobiogas.tech">
                        <button type="button" onclick="App._addTeamEmail()" style="padding:0 14px;border-radius:6px;background:var(--primary);color:white;border:none;cursor:pointer;font-size:0.85rem;white-space:nowrap">Adicionar</button>
                    </div>
                    <div id="chips" style="display:flex;flex-wrap:wrap;gap:2px"></div>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Criar equipe</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        App._addTeamEmail = () => {
            const input = document.getElementById('t-email-input'); const val = input.value.trim();
            if (val && val.includes('@') && !emails.includes(val)) { emails.push(val); input.value = ''; renderChips(); }
        };
        document.getElementById('t-email-input').onkeypress = (e) => { if (e.key==='Enter') { e.preventDefault(); App._addTeamEmail(); } };
        document.getElementById('team-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = e.target.querySelector('button[type="submit"]'); btn.disabled = true; btn.textContent = 'Salvando...';
            const fd = new FormData();
            fd.append('name', document.getElementById('t-name').value);
            fd.append('team_admin_email', document.getElementById('t-admin').value);
            fd.append('description', document.getElementById('t-desc').value);
            if (emails.length) fd.append('emails', emails.join(','));
            const res = await fetch('/teams', { method: 'POST', headers: this.apiHeaders(), body: fd });
            if (res.ok) { this.closeModal(); this.renderAdminTeams(); }
            else { alert((await res.json()).detail || 'Erro ao criar equipe.'); btn.disabled = false; btn.textContent = 'Criar equipe'; }
        };
        modal.classList.remove('hidden');
    },

    // --- ADMIN: TRILHAS ---
    async renderAdminPaths() {
        this.currentPath = null; this.currentCourse = null;
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Trilhas de Aprendizagem', actionLabel: '+ Nova Trilha', actionFn: 'App.showCreatePathModal()' }) +
            `<div id="paths-wrapper"><div class="loader">Carregando...</div></div>`;
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        const wrapper = document.getElementById('paths-wrapper'); wrapper.innerHTML = '';
        if (!paths.length) { wrapper.innerHTML = '<p style="color:var(--text-dim)">Nenhuma trilha criada ainda.</p>'; return; }
        paths.forEach(p => {
            wrapper.innerHTML += `<div class="card" style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1"><h3 style="margin:0 0 0.25rem">${p.title}</h3><p style="color:var(--text-dim);font-size:0.88rem;margin:0">${p.description||'Sem descrição.'}</p></div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditPathModal(${p.id},'${p.title.replace(/'/g,"\\'")}','${(p.description||'').replace(/'/g,"\\'")}',${!!p.is_standard_training})`)}
                    ${this.actionBtn('🗑 Excluir',`App.deletePath(${p.id},'${p.title.replace(/'/g,"\\'")}')`, 'danger')}
                    ${this.actionBtn('Ver cursos →',`App.renderAdminCourses(${p.id},'${p.title.replace(/'/g,"\\'")}')`, 'primary')}
                </div></div>`;
        });
    },

    showCreatePathModal() {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:1rem">Nova Trilha</h3>
            <form id="path-form">
                <div class="form-group"><label>Título</label><input type="text" id="p-title" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="p-desc" class="form-control" rows="3"></textarea></div>
                <div class="form-group" style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="p-std" style="width:16px;height:16px"><label style="margin:0;font-size:0.9rem">Treinamento obrigatório padronizado</label></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Criar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('path-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('title', document.getElementById('p-title').value);
            fd.append('description', document.getElementById('p-desc').value);
            fd.append('is_standard_training', document.getElementById('p-std').checked);
            await fetch('/paths', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderAdminPaths();
        };
        modal.classList.remove('hidden');
    },

    showEditPathModal(id, title, desc, is_std) {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:1rem">Editar Trilha</h3>
            <form id="epath-form">
                <div class="form-group"><label>Título</label><input type="text" id="ep-title" class="form-control" value="${title}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="ep-desc" class="form-control" rows="3">${desc}</textarea></div>
                <div class="form-group" style="display:flex;gap:8px;align-items:center"><input type="checkbox" id="ep-std" ${is_std?'checked':''} style="width:16px;height:16px"><label style="margin:0;font-size:0.9rem">Treinamento obrigatório padronizado</label></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('epath-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('title', document.getElementById('ep-title').value);
            fd.append('description', document.getElementById('ep-desc').value);
            fd.append('is_standard_training', document.getElementById('ep-std').checked);
            await fetch(`/paths/${id}`, { method: 'PUT', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderAdminPaths();
        };
        modal.classList.remove('hidden');
    },

    async deletePath(id, title) {
        if (!confirm(`Excluir a trilha "${title}"? Todos os cursos e módulos serão removidos.`)) return;
        await fetch(`/paths/${id}`, { method: 'DELETE', headers: this.apiHeaders() });
        this.renderAdminPaths();
    },

    // --- ADMIN: CURSOS ---
    async renderAdminCourses(pathId, pathTitle) {
        this.currentPath = { id: pathId, title: pathTitle }; this.currentCourse = null;
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({
            title: `Cursos — ${pathTitle}`,
            backLabel: 'Trilhas', backFn: 'App.renderAdminPaths()',
            actionLabel: '+ Novo Curso', actionFn: `App.showCreateCourseModal(${pathId})`,
            breadcrumbs: [{ label: 'Trilhas', fn: 'App.renderAdminPaths()' }, { label: pathTitle }]
        }) + `<div id="courses-wrapper"><div class="loader">Carregando...</div></div>`;
        const res = await fetch(`/paths/${pathId}/courses`, { headers: this.apiHeaders() });
        const courses = await res.json();
        const wrapper = document.getElementById('courses-wrapper'); wrapper.innerHTML = '';
        if (!courses.length) { wrapper.innerHTML = '<p style="color:var(--text-dim)">Nenhum curso nesta trilha ainda.</p>'; return; }
        courses.forEach(c => {
            wrapper.innerHTML += `<div class="card" style="margin-bottom:1rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1"><h3 style="margin:0 0 0.25rem">${c.order?c.order+'. ':''}${c.title}</h3><p style="color:var(--text-dim);font-size:0.88rem;margin:0">${c.description||''}</p></div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditCourseModal(${c.id},'${c.title.replace(/'/g,"\\'")}','${(c.description||'').replace(/'/g,"\\'")}',${c.order||1})`)}
                    ${this.actionBtn('🗑 Excluir',`App.deleteCourse(${c.id},'${c.title.replace(/'/g,"\\'")}',${pathId})`,'danger')}
                    ${this.actionBtn('Módulos →',`App.renderAdminModules(${c.id},'${c.title.replace(/'/g,"\\'")}')`, 'primary')}
                </div></div>`;
        });
    },

    showCreateCourseModal(pathId) {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:1rem">Novo Curso</h3>
            <form id="course-form">
                <div class="form-group"><label>Título</label><input type="text" id="c-title" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="c-desc" class="form-control" rows="3"></textarea></div>
                <div class="form-group"><label>Ordem</label><input type="number" id="c-order" class="form-control" value="1"></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Criar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('course-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('title', document.getElementById('c-title').value);
            fd.append('description', document.getElementById('c-desc').value);
            fd.append('order', document.getElementById('c-order').value);
            await fetch(`/paths/${pathId}/courses`, { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderAdminCourses(pathId, this.currentPath.title);
        };
        modal.classList.remove('hidden');
    },

    showEditCourseModal(id, title, desc, order) {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:1rem">Editar Curso</h3>
            <form id="ecourse-form">
                <div class="form-group"><label>Título</label><input type="text" id="ec-title" class="form-control" value="${title}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="ec-desc" class="form-control" rows="3">${desc}</textarea></div>
                <div class="form-group"><label>Ordem</label><input type="number" id="ec-order" class="form-control" value="${order}"></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('ecourse-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('title', document.getElementById('ec-title').value);
            fd.append('description', document.getElementById('ec-desc').value);
            fd.append('order', document.getElementById('ec-order').value);
            await fetch(`/courses/${id}`, { method: 'PUT', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderAdminCourses(this.currentPath.id, this.currentPath.title);
        };
        modal.classList.remove('hidden');
    },

    async deleteCourse(id, title, pathId) {
        if (!confirm(`Excluir o curso "${title}"? Todos os módulos serão removidos.`)) return;
        await fetch(`/courses/${id}`, { method: 'DELETE', headers: this.apiHeaders() });
        this.renderAdminCourses(pathId, this.currentPath.title);
    },

    // --- ADMIN: MÓDULOS ---
    async renderAdminModules(courseId, courseTitle) {
        this.currentCourse = { id: courseId, title: courseTitle };
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({
            title: `Módulos — ${courseTitle}`,
            backLabel: 'Cursos', backFn: `App.renderAdminCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')`,
            actionLabel: '+ Novo Módulo', actionFn: `App.showModuleUpload(${courseId},'${courseTitle.replace(/'/g,"\\'")}')`,
            breadcrumbs: [
                { label: 'Trilhas', fn: 'App.renderAdminPaths()' },
                { label: this.currentPath.title, fn: `App.renderAdminCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')` },
                { label: courseTitle }
            ]
        }) + `
            <div id="modules-wrapper"><div class="loader">Carregando...</div></div>
            <div class="card hidden" id="module-upload-card" style="margin-top:2rem;border-top:3px solid var(--primary)">
                <h3 id="module-upload-title" style="margin-bottom:1.5rem">Novo Módulo</h3>
                <form id="module-upload-form">
                    <input type="hidden" id="m-course-id">
                    <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">
                        <div>
                            <div class="form-group"><label>Título</label><input type="text" id="m-title" class="form-control" required></div>
                            <div class="form-group"><label>Descrição</label><textarea id="m-desc" class="form-control" rows="3"></textarea></div>
                            <div class="form-group"><label>Ordem</label><input type="number" id="m-order" class="form-control" value="1" required></div>
                        </div>
                        <div>
                            <div class="form-group"><label>Vídeo (.mp4 / .mov)</label><input type="file" id="m-video" class="form-control" accept="video/*" required></div>
                            <div class="form-group"><label>Thumbnail</label><input type="file" id="m-thumb" class="form-control" accept="image/*"></div>
                        </div>
                    </div>
                    <div class="progress-track" id="m-prog-wrap" style="display:none"><div class="progress-fill" id="m-prog-bar" style="width:0%"></div></div>
                    <p id="m-status" style="font-size:0.85rem;color:var(--text-dim);text-align:center;margin-top:0.5rem"></p>
                    <div style="display:flex;gap:0.5rem;margin-top:1rem">
                        <button type="submit" id="btn-upload-module" class="btn btn-primary" style="flex:1">Fazer upload</button>
                        <button type="button" class="btn btn-outline" style="flex:1" onclick="document.getElementById('module-upload-card').classList.add('hidden')">Cancelar</button>
                    </div>
                </form>
            </div>
            <div id="quiz-editor-section" class="card hidden" style="margin-top:2rem"></div>`;
        const res = await fetch(`/courses/${courseId}/modules`, { headers: this.apiHeaders() });
        const modules = await res.json();
        const wrapper = document.getElementById('modules-wrapper'); wrapper.innerHTML = '';
        if (!modules.length) { wrapper.innerHTML = '<p style="color:var(--text-dim)">Nenhum módulo neste curso ainda.</p>'; }
        modules.forEach(m => {
            wrapper.innerHTML += `<div class="card" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1">
                    <span style="font-size:0.75rem;color:var(--text-dim);font-weight:600;text-transform:uppercase;letter-spacing:0.05em">Módulo ${m.order||'-'}</span>
                    <h4 style="margin:0.2rem 0 0">${m.title}</h4>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditModuleModal(${m.id},'${m.title.replace(/'/g,"\\'")}','${(m.description||'').replace(/'/g,"\\'")}',${m.order||1},${m.validity_months||0})`)}
                    ${this.actionBtn('🗑 Excluir',`App.deleteModule(${m.id},'${m.title.replace(/'/g,"\\'")}',${courseId})`,'danger')}
                    ${this.actionBtn('🎮 Quiz',`App.openQuizEditor(${m.id},'${m.video_url}')`)}
                </div></div>`;
        });
        this.bindModuleForm();
    },

    showEditModuleModal(id, title, desc, order, valMonths) {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:0.5rem">Editar Módulo</h3>
            <p style="color:var(--text-dim);font-size:0.85rem;margin-bottom:1rem">Para substituir o vídeo, exclua e recrie o módulo.</p>
            <form id="emod-form">
                <div class="form-group"><label>Título</label><input type="text" id="em-title" class="form-control" value="${title}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="em-desc" class="form-control" rows="3">${desc}</textarea></div>
                <div style="display:flex;gap:1rem">
                    <div class="form-group" style="flex:1"><label>Ordem</label><input type="number" id="em-order" class="form-control" value="${order}"></div>
                    <div class="form-group" style="flex:1"><label>Validade certif. (meses)</label><input type="number" id="em-val" class="form-control" value="${valMonths||''}" placeholder="Opcional"></div>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('emod-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('title', document.getElementById('em-title').value);
            fd.append('description', document.getElementById('em-desc').value);
            fd.append('order', document.getElementById('em-order').value);
            if (document.getElementById('em-val').value) fd.append('validity_months', document.getElementById('em-val').value);
            await fetch(`/modules/${id}`, { method: 'PUT', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderAdminModules(this.currentCourse.id, this.currentCourse.title);
        };
        modal.classList.remove('hidden');
    },

    async deleteModule(id, title, courseId) {
        if (!confirm(`Excluir o módulo "${title}"? O vídeo e os progressos dos alunos serão removidos.`)) return;
        await fetch(`/modules/${id}`, { method: 'DELETE', headers: this.apiHeaders() });
        this.renderAdminModules(courseId, this.currentCourse.title);
    },

    showModuleUpload(courseId, courseTitle) {
        const card = document.getElementById('module-upload-card');
        card.classList.remove('hidden');
        document.getElementById('m-course-id').value = courseId;
        document.getElementById('module-upload-title').textContent = `Novo Módulo em: ${courseTitle}`;
        card.scrollIntoView({ behavior: 'smooth' });
    },

    bindModuleForm() {
        document.getElementById('module-upload-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn = document.getElementById('btn-upload-module');
            const status = document.getElementById('m-status');
            const file = document.getElementById('m-video').files[0];
            const thumb = document.getElementById('m-thumb').files[0];
            const courseId = document.getElementById('m-course-id').value;
            btn.disabled = true; btn.textContent = 'Enviando...';
            document.getElementById('m-prog-wrap').style.display = 'block';
            status.textContent = 'Iniciando upload...';
            try {
                const initRes = await fetch('/modules/upload/init?filename=' + encodeURIComponent(file.name), { method: 'POST', headers: this.apiHeaders() });
                const { upload_id } = await initRes.json();
                const chunkSize = 5 * 1024 * 1024;
                const totalChunks = Math.ceil(file.size / chunkSize);
                for (let i = 0; i < totalChunks; i++) {
                    const chunk = file.slice(i * chunkSize, Math.min((i + 1) * chunkSize, file.size));
                    const fd = new FormData();
                    fd.append('upload_id', upload_id); fd.append('filename', file.name);
                    fd.append('chunk_index', i); fd.append('chunk', chunk);
                    await fetch('/modules/upload/chunk', { method: 'POST', headers: this.apiHeaders(), body: fd });
                    const pct = Math.round(((i + 1) / totalChunks) * 100);
                    document.getElementById('m-prog-bar').style.width = pct + '%';
                    status.textContent = `Enviando... ${pct}%`;
                }
                status.textContent = 'Finalizando...';
                const finalFd = new FormData();
                finalFd.append('title', document.getElementById('m-title').value);
                finalFd.append('description', document.getElementById('m-desc').value);
                finalFd.append('order', document.getElementById('m-order').value);
                finalFd.append('upload_id', upload_id); finalFd.append('filename', file.name);
                if (thumb) finalFd.append('thumbnail', thumb);
                await fetch(`/courses/${courseId}/modules`, { method: 'POST', headers: this.apiHeaders(), body: finalFd });
                status.textContent = 'Upload concluído!';
                setTimeout(() => this.renderAdminModules(courseId, this.currentCourse.title), 1000);
            } catch(err) { status.textContent = 'Erro no upload. Tente novamente.'; btn.disabled = false; btn.textContent = 'Fazer upload'; }
        };
    },

    openQuizEditor(moduleId, videoUrl) {
        const sec = document.getElementById('quiz-editor-section');
        sec.classList.remove('hidden');
        sec.innerHTML = `<h3 style="margin-bottom:1rem">Configurar Quiz</h3>
            <div style="display:flex;gap:2rem;align-items:flex-start;flex-wrap:wrap">
                <div style="flex:1;min-width:280px">
                    <video id="editor-video" src="${videoUrl}" controls style="width:100%;border-radius:8px;background:#000;max-height:300px"></video>
                    <div style="display:flex;gap:0.5rem;margin-top:0.5rem;align-items:center">
                        <button type="button" onclick="document.getElementById('q-time').value=Math.floor(document.getElementById('editor-video').currentTime)" style="padding:5px 12px;border-radius:6px;font-size:0.82rem;cursor:pointer;background:var(--bg-main);border:1px solid var(--border);color:var(--text)">📌 Marcar momento</button>
                        <input type="number" id="q-time" class="form-control" style="width:100px" placeholder="seg." readonly>
                    </div>
                </div>
                <div style="flex:1.2;min-width:280px">
                    <form id="quiz-form">
                        <div class="form-group"><label>Pergunta</label><input type="text" id="q-text" class="form-control" required></div>
                        <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.75rem;margin-bottom:1rem">
                            <input type="text" id="q-a" class="form-control" placeholder="A)" required>
                            <input type="text" id="q-b" class="form-control" placeholder="B)" required>
                            <input type="text" id="q-c" class="form-control" placeholder="C)" required>
                            <input type="text" id="q-d" class="form-control" placeholder="D)" required>
                        </div>
                        <div class="form-group"><label>Opção correta</label>
                            <select id="q-corr" class="form-control"><option>A</option><option>B</option><option>C</option><option>D</option></select>
                        </div>
                        <div class="form-group" style="display:flex;gap:8px;align-items:center;padding:0.75rem;background:#fffbeb;border-radius:6px;border:1px solid #fde68a">
                            <input type="checkbox" id="q-final" style="width:16px;height:16px">
                            <label style="margin:0;font-size:0.88rem;color:#92400e">Prova final (exibida ao fim do vídeo)</label>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width:100%">Salvar questão</button>
                    </form>
                </div>
            </div>`;
        sec.scrollIntoView({ behavior: 'smooth' });
        document.getElementById('quiz-form').onsubmit = async (e) => {
            e.preventDefault();
            const payload = {
                text: document.getElementById('q-text').value,
                option_a: document.getElementById('q-a').value, option_b: document.getElementById('q-b').value,
                option_c: document.getElementById('q-c').value, option_d: document.getElementById('q-d').value,
                correct_option: document.getElementById('q-corr').value,
                timestamp: parseFloat(document.getElementById('q-time').value) || 0,
                is_final_exam: document.getElementById('q-final').checked
            };
            await fetch(`/modules/${moduleId}/questions`, { method: 'POST', headers: this.apiJsonHeaders(), body: JSON.stringify(payload) });
            alert('Questão salva!'); e.target.reset();
        };
    },

    // --- LIDERANÇA ---
    async renderLeaderDashboard() {
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Minha Equipe', actionLabel: '+ Adicionar Colaborador', actionFn: 'App.showAddMemberModal()' }) + `
            <div class="card" style="overflow-x:auto">
                <table id="team-table">
                    <thead><tr><th>Nome</th><th>E-mail</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="4" class="loader">Carregando...</td></tr></tbody>
                </table>
            </div>`;
        const res = await fetch('/admin/users', { headers: this.apiHeaders() });
        const users = await res.json();
        const tbody = document.querySelector('#team-table tbody'); tbody.innerHTML = '';
        users.forEach(u => {
            tbody.innerHTML += `<tr>
                <td><strong>${u.username}</strong></td>
                <td style="font-size:0.85rem">${u.email}</td>
                <td>${this.statusBadge(u.status)}</td>
                <td>${this.actionBtn('🎯 Atribuir Trilha',`App.showAssignPathModal(${u.id},'${u.username}')`)}</td>
            </tr>`;
        });
        if (!users.length) tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-dim)">Nenhum colaborador encontrado.</td></tr>';
    },

    showAddMemberModal() {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        body.innerHTML = `<h3 style="margin-bottom:1rem">Novo Colaborador</h3>
            <form id="add-member-form">
                <div class="form-group"><label>Usuário</label><input type="text" id="m-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail</label><input type="email" id="m-email" class="form-control" required></div>
                <div class="form-group"><label>Senha inicial</label><input type="password" id="m-pass" class="form-control" required></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Cadastrar</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('add-member-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('username', document.getElementById('m-user').value);
            fd.append('email', document.getElementById('m-email').value);
            fd.append('password', document.getElementById('m-pass').value);
            await fetch('/admin/users', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal(); this.renderLeaderDashboard();
        };
        modal.classList.remove('hidden');
    },

    async showAssignPathModal(userId, username) {
        const modal = document.getElementById('modal-container'); const body = document.getElementById('modal-body');
        const pathsRes = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await pathsRes.json();
        body.innerHTML = `<h3 style="margin-bottom:1rem">Atribuir Trilha — ${username}</h3>
            <form id="assign-form">
                <div class="form-group"><label>Trilha</label>
                    <select id="a-path" class="form-control">${paths.map(p=>`<option value="${p.id}">${p.title}</option>`).join('')}</select>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Atribuir</button>
                    <button type="button" class="btn btn-outline" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div></form>`;
        document.getElementById('assign-form').onsubmit = async (e) => {
            e.preventDefault(); const fd = new FormData();
            fd.append('user_id', userId); fd.append('path_id', document.getElementById('a-path').value);
            await fetch('/enrollments', { method: 'POST', headers: this.apiHeaders(), body: fd });
            this.closeModal(); alert('Trilha atribuída com sucesso!');
        };
        modal.classList.remove('hidden');
    },

    // --- ALUNO ---
    async renderStudentPaths() {
        this.currentPath = null; this.currentCourse = null;
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({ title: 'Minhas Trilhas' }) +
            `<div class="grid" id="student-paths"><div class="loader">Carregando...</div></div>`;
        const res = await fetch('/paths', { headers: this.apiHeaders() });
        const paths = await res.json();
        const grid = document.getElementById('student-paths'); grid.innerHTML = '';
        if (!paths.length) { grid.innerHTML = '<p style="color:var(--text-dim)">Nenhuma trilha disponível.</p>'; return; }
        paths.forEach(p => {
            grid.innerHTML += `<div class="card" style="display:flex;flex-direction:column">
                <h3>${p.title}</h3>
                <p style="color:var(--text-dim);flex:1;margin:0.75rem 0">${p.description}</p>
                <button class="btn btn-primary" onclick="App.showStudentCourses(${p.id},'${p.title.replace(/'/g,"\\'")}')">Acessar →</button>
            </div>`;
        });
    },

    async showStudentCourses(pathId, pathTitle) {
        this.currentPath = { id: pathId, title: pathTitle };
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({
            title: pathTitle,
            backLabel: 'Trilhas', backFn: 'App.renderStudentPaths()',
            breadcrumbs: [{ label: 'Trilhas', fn: 'App.renderStudentPaths()' }, { label: pathTitle }]
        }) + `<div class="grid" id="student-courses"><div class="loader">Carregando...</div></div>`;
        const res = await fetch(`/paths/${pathId}/courses`, { headers: this.apiHeaders() });
        const courses = await res.json();
        const grid = document.getElementById('student-courses'); grid.innerHTML = '';
        courses.forEach(c => {
            grid.innerHTML += `<div class="card" style="display:flex;flex-direction:column">
                <h3>${c.order?c.order+'. ':''}${c.title}</h3>
                <p style="color:var(--text-dim);flex:1;margin:0.75rem 0">${c.description}</p>
                <button class="btn btn-primary" onclick="App.showStudentModules(${c.id},'${c.title.replace(/'/g,"\\'")}')">Ver módulos →</button>
            </div>`;
        });
        if (!courses.length) grid.innerHTML = '<p style="color:var(--text-dim)">Nenhum curso disponível nesta trilha.</p>';
    },

    async showStudentModules(courseId, courseTitle) {
        this.currentCourse = { id: courseId, title: courseTitle };
        const container = document.getElementById('app-container');
        container.innerHTML = this.sectionHeader({
            title: courseTitle,
            backLabel: this.currentPath.title, backFn: `App.showStudentCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')`,
            breadcrumbs: [
                { label: 'Trilhas', fn: 'App.renderStudentPaths()' },
                { label: this.currentPath.title, fn: `App.showStudentCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')` },
                { label: courseTitle }
            ]
        }) + `<div class="grid" id="student-modules"><div class="loader">Carregando...</div></div>`;
        const res = await fetch(`/courses/${courseId}/modules`, { headers: this.apiHeaders() });
        const modules = await res.json();
        const grid = document.getElementById('student-modules'); grid.innerHTML = '';
        modules.forEach(m => {
            grid.innerHTML += `<div class="card" onclick="App.playModule(${m.id},${courseId})" style="cursor:pointer;transition:transform 0.15s" onmouseover="this.style.transform='translateY(-2px)'" onmouseout="this.style.transform=''">
                <img src="${m.thumbnail_url||'logo_transparent.png'}" style="width:100%;border-radius:6px;aspect-ratio:16/9;object-fit:cover">
                <h4 style="margin:0.75rem 0 0.25rem">${m.title}</h4>
                <p style="font-size:0.82rem;color:var(--text-dim);margin:0">Módulo ${m.order||''}</p>
            </div>`;
        });
        if (!modules.length) grid.innerHTML = '<p style="color:var(--text-dim)">Nenhum módulo disponível.</p>';
    },

    async playModule(moduleId, courseId) {
        const res = await fetch(`/courses/${courseId}/modules`, { headers: this.apiHeaders() });
        const modules = await res.json();
        const target = modules.find(m => m.id === moduleId);
        if (!target) return alert('Módulo não encontrado.');
        const inlineQuizzes = (target.questions||[]).filter(q => !q.is_final_exam);
        const finalQuizzes  = (target.questions||[]).filter(q => q.is_final_exam);
        const modal = document.getElementById('modal-container');
        const body  = document.getElementById('modal-body');
        modal.classList.remove('hidden');
        body.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                <h3 style="margin:0">${target.title}</h3>
                <button onclick="App.closeModal()" style="background:transparent;border:none;cursor:pointer;font-size:1.5rem;color:var(--text-dim);padding:0;line-height:1">×</button>
            </div>
            <div style="position:relative">
                <video id="st-video" src="${target.video_url}" controls autoplay style="width:100%;border-radius:8px;background:#000;display:block"></video>
                <div id="quiz-overlay" style="display:none;position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(0,0,0,0.92);border-radius:8px;align-items:center;justify-content:center;padding:2rem;box-sizing:border-box;pointer-events:all;z-index:10">
                    <div style="width:100%;max-width:560px">
                        <p style="color:#86efac;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.08em;margin-bottom:0.5rem">Quiz</p>
                        <h3 id="q-text-display" style="color:white;margin-bottom:1.25rem;line-height:1.4"></h3>
                        <div id="q-opts" style="display:flex;flex-direction:column;gap:0.5rem"></div>
                    </div>
                </div>
            </div>
            <div id="final-exam-section" style="display:none;margin-top:1.5rem;padding-top:1.5rem;border-top:1px solid var(--border);text-align:center">
                <h4 style="margin-bottom:0.5rem">Módulo concluído!</h4>
                <p style="color:var(--text-dim);font-size:0.9rem;margin-bottom:1rem">Responda à prova final para completar este módulo.</p>
                <button class="btn btn-primary" id="btn-final-exam">Iniciar Prova Final</button>
            </div>`;
        const video = document.getElementById('st-video');
        const asked = new Set();
        video.ontimeupdate = () => {
            if (video.paused) return;
            inlineQuizzes.forEach(q => {
                if (Math.abs(video.currentTime - q.timestamp) < 0.5 && !asked.has(q.id)) {
                    asked.add(q.id); video.pause(); video.controls = false; this.showQuizOverlay(q);
                }
            });
            if (video.duration > 0 && video.currentTime >= video.duration - 1 && finalQuizzes.length > 0)
                document.getElementById('final-exam-section').style.display = 'block';
        };
        if (finalQuizzes.length > 0)
            document.getElementById('btn-final-exam').onclick = () => this.startFinalExam(finalQuizzes);
    },

    showQuizOverlay(q) {
        const overlay = document.getElementById('quiz-overlay');
        overlay.style.display = 'flex';
        document.getElementById('q-text-display').textContent = q.text;
        const opts = document.getElementById('q-opts'); opts.innerHTML = '';
        ['A','B','C','D'].forEach(l => {
            const btn = document.createElement('button');
            btn.textContent = `${l}) ${q['option_'+l.toLowerCase()]}`;
            btn.style.cssText = 'text-align:left;padding:0.75rem 1rem;border-radius:8px;background:rgba(255,255,255,0.08);border:1px solid rgba(255,255,255,0.2);color:white;cursor:pointer;font-size:0.9rem;transition:background 0.15s';
            btn.onmouseover = () => { if (!btn.disabled) btn.style.background = 'rgba(255,255,255,0.15)'; };
            btn.onmouseout  = () => { if (!btn.disabled) btn.style.background = 'rgba(255,255,255,0.08)'; };
            btn.onclick = () => {
                if (l === q.correct_option) {
                    overlay.style.display = 'none';
                    const video = document.getElementById('st-video');
                    video.controls = true; video.play();
                } else {
                    btn.style.background = 'rgba(239,68,68,0.25)'; btn.style.borderColor = 'rgba(239,68,68,0.5)'; btn.style.color = '#fca5a5'; btn.disabled = true;
                }
            };
            opts.appendChild(btn);
        });
    },

    startFinalExam(questions) {
        const modal = document.getElementById('modal-container');
        const body  = document.getElementById('modal-body');
        let current = 0; let correct = 0;
        const renderQ = () => {
            const q = questions[current];
            body.innerHTML = `
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                    <h3 style="margin:0">Prova Final</h3>
                    <span style="font-size:0.85rem;color:var(--text-dim)">${current+1} / ${questions.length}</span>
                </div>
                <div style="background:var(--bg-main);border-radius:8px;padding:1.25rem;margin-bottom:1.25rem">
                    <p style="font-weight:600;margin:0;line-height:1.5">${q.text}</p>
                </div>
                <div id="exam-opts" style="display:flex;flex-direction:column;gap:0.5rem"></div>`;
            const opts = document.getElementById('exam-opts');
            ['A','B','C','D'].forEach(l => {
                const btn = document.createElement('button');
                btn.textContent = `${l}) ${q['option_'+l.toLowerCase()]}`;
                btn.style.cssText = 'text-align:left;padding:0.75rem 1rem;border-radius:8px;background:var(--bg-body);border:1px solid var(--border);cursor:pointer;font-size:0.9rem;transition:background 0.15s';
                btn.onclick = () => {
                    opts.querySelectorAll('button').forEach(b => b.disabled = true);
                    if (l === q.correct_option) {
                        btn.style.background = '#22c55e20'; btn.style.borderColor = '#22c55e60'; btn.style.color = '#16a34a'; correct++;
                    } else {
                        btn.style.background = '#ef444420'; btn.style.borderColor = '#ef444460'; btn.style.color = '#dc2626';
                        opts.querySelectorAll('button').forEach(b => { if (b.textContent.startsWith(q.correct_option+')')) { b.style.background='#22c55e20'; b.style.borderColor='#22c55e60'; b.style.color='#16a34a'; } });
                    }
                    setTimeout(() => { current++; if (current < questions.length) renderQ(); else showResult(); }, 1200);
                };
                opts.appendChild(btn);
            });
        };
        const showResult = () => {
            const score = Math.round((correct / questions.length) * 100);
            const passed = score >= 80;
            body.innerHTML = `<div style="text-align:center;padding:1rem 0">
                <div style="font-size:3rem;margin-bottom:0.5rem">${passed?'🎉':'📚'}</div>
                <h3 style="margin-bottom:0.5rem">${passed?'Aprovado!':'Não atingiu o mínimo'}</h3>
                <p style="font-size:2rem;font-weight:700;color:${passed?'#22c55e':'#f59e0b'};margin:0.5rem 0">${score}%</p>
                <p style="color:var(--text-dim);font-size:0.9rem">${correct} de ${questions.length} corretas — mínimo 80%</p>
                <button class="btn ${passed?'btn-primary':'btn-outline'}" style="margin-top:1.5rem" onclick="App.closeModal()">
                    ${passed?'Concluir módulo':'Fechar e rever o conteúdo'}
                </button>
            </div>`;
        };
        renderQ();
    },

    closeModal() {
        document.getElementById('modal-container').classList.add('hidden');
        document.getElementById('modal-body').innerHTML = '';
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
