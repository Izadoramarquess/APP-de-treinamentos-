console.log("GeoTrilha LMS carregado.");

const App = {
    user: null,
    currentPath: null,
    currentCourse: null,

    init() {
        const p = new URLSearchParams(window.location.search);
        if (p.get('view') === 'convite' && p.get('token')) { this.showView('invite', p.get('token')); return; }
        if (p.get('view') === 'reset'   && p.get('token')) { this.showView('reset',  p.get('token')); return; }
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
                this.renderNavbar();
                if (this.user.must_change_password) this.showForcePasswordChangeModal();
                else this.showDashboard();
            } else this.logout();
        } catch(e) { this.logout(); }
    },

    apiHeaders()     { return { 'Authorization': `Bearer ${localStorage.getItem('token')}` }; },
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
            'colaborador':      { label: 'Colaborador',color: '#888'    },
            'usuario':          { label: 'Usuário',    color: '#888'    },
        };
        const s = (status||'').toLowerCase();
        const c = map[s] || { label: status||'-', color: '#888' };
        return `<span style="padding:3px 10px;border-radius:20px;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.05em;color:${c.color};background:${c.color}18;border:1px solid ${c.color}35">${c.label}</span>`;
    },

    actionBtn(label, onclick, variant='outline') {
        const s = {
            outline:  'background:transparent;border:1px solid var(--border);color:var(--text-dim)',
            primary:  'background:var(--primary-light);border:none;color:white',
            success:  'background:#22c55e18;border:1px solid #22c55e50;color:#16a34a',
            danger:   'background:#ef444418;border:1px solid #ef444450;color:#dc2626',
            secondary:'background:var(--bg-main);border:1px solid var(--border);color:var(--text-main)',
        };
        return `<button onclick="${onclick}" style="padding:4px 10px;border-radius:6px;font-size:0.78rem;font-family:Outfit,sans-serif;font-weight:500;cursor:pointer;white-space:nowrap;transition:opacity .15s;${s[variant]||s.outline}" onmouseover="this.style.opacity='.75'" onmouseout="this.style.opacity='1'">${label}</button>`;
    },

    showCopyLinkModal(title, message, link) {
        const modal = document.getElementById('modal-container');
        const body  = document.getElementById('modal-body');
        body.className = '';
        body.innerHTML = `
            <h3 style="margin-bottom:0.5rem">${title}</h3>
            <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1rem">${message}</p>
            <div style="padding:0.9rem 1rem;background:var(--bg-main);border:1.5px dashed var(--border-dark);border-radius:8px;word-break:break-all;font-family:monospace;font-size:0.82rem;color:var(--primary-light);margin-bottom:1rem;user-select:all">${link}</div>
            <div style="display:flex;gap:0.5rem">
                <button class="btn btn-primary" style="flex:1" onclick="navigator.clipboard.writeText('${link}').then(()=>{this.textContent='✓ Copiado!';setTimeout(()=>this.textContent='📋 Copiar link',2000)})">📋 Copiar link</button>
                <button class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Fechar</button>
            </div>`;
        modal.classList.remove('hidden');
    },

    sectionHeader({ title, backLabel, backFn, actionLabel, actionFn, breadcrumbs } = {}) {
        let bread = '';
        if (breadcrumbs && breadcrumbs.length) {
            bread = `<nav style="font-size:0.82rem;color:var(--text-dim);margin-bottom:0.6rem;display:flex;align-items:center;gap:0.3rem;flex-wrap:wrap">` +
                breadcrumbs.map((b,i) => i < breadcrumbs.length-1
                    ? `<a href="#" onclick="${b.fn};return false" style="color:var(--primary-light);text-decoration:none">${b.label}</a><span style="color:var(--border-dark)">›</span>`
                    : `<span style="color:var(--text-main);font-weight:500">${b.label}</span>`).join('') + `</nav>`;
        }
        const back = backFn ? `<button onclick="${backFn}" style="padding:5px 12px;border-radius:6px;font-size:0.82rem;cursor:pointer;background:transparent;border:1px solid var(--border);color:var(--text-dim);margin-right:0.75rem;font-family:Outfit,sans-serif;transition:all .2s" onmouseover="this.style.borderColor='var(--primary-light)';this.style.color='var(--primary-light)'" onmouseout="this.style.borderColor='var(--border)';this.style.color='var(--text-dim)'">← ${backLabel||'Voltar'}</button>` : '';
        const act  = actionFn ? `<button onclick="${actionFn}" style="padding:7px 16px;border-radius:8px;font-size:0.85rem;cursor:pointer;background:linear-gradient(135deg,var(--primary-mid),var(--primary-light));border:none;color:white;font-family:Outfit,sans-serif;font-weight:600;box-shadow:0 2px 8px rgba(37,99,235,.25)">${actionLabel}</button>` : '';
        return `${bread}<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1.5rem;gap:1rem"><div style="display:flex;align-items:center;min-width:0">${back}<h2 style="margin:0;font-size:1.35rem;font-weight:700;color:var(--primary);white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${title}</h2></div>${act}</div>`;
    },

    showView(viewName, extraParam) {
        const container = document.getElementById('app-container');
        const header    = document.getElementById('main-header');
        const authViews = ['login','register','invite','forgot','reset'];
        if (authViews.includes(viewName)) header.classList.add('hidden');
        else header.classList.remove('hidden');
        this._resetContainerStyles();
        if      (viewName==='login')    this.renderLogin(container);
        else if (viewName==='register') this.renderRegister(container);
        else if (viewName==='invite')   this.renderInviteAccept(container, extraParam);
        else if (viewName==='forgot')   this.renderForgotPassword(container);
        else if (viewName==='reset')    this.renderResetPassword(container, extraParam);
    },

    renderNavbar() {
        document.getElementById('main-header').classList.remove('hidden');
        const nav      = document.getElementById('main-nav');
        const userInfo = document.getElementById('user-info');
        if (!this.user) return;
        const role = this.user.role;
        let navHtml = '';
        if (role === 'admin') {
            navHtml = `
                <a class="nav-link" onclick="App.renderAdminDashboard()">Dashboard</a>
                <a class="nav-link" onclick="App.renderAdminUsers()">Usuários</a>
                <a class="nav-link" onclick="App.renderAdminInvites()">Convites</a>
                <a class="nav-link" onclick="App.renderAdminTeams()">Equipes</a>
                <a class="nav-link" onclick="App.renderAdminPaths()">Trilhas & Cursos</a>`;
        } else if (role === 'lideranca') {
            navHtml = `
                <a class="nav-link" onclick="App.renderLeaderDashboard()">Minha Equipe</a>
                <a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>`;
        } else {
            navHtml = `
                <a class="nav-link" onclick="App.renderStudentDashboard()">Início</a>
                <a class="nav-link" onclick="App.renderStudentPaths()">Minhas Trilhas</a>
                <a class="nav-link" onclick="App.renderStudentCertificates()">🏆 Certificados</a>`;
        }
        nav.innerHTML = navHtml;
        userInfo.innerHTML = `
            <span style="font-size:0.83rem;color:rgba(255,255,255,.65)">Olá, <b style="color:white">${this.user.username}</b></span>
            <button onclick="App.logout()" class="btn btn-ghost btn-sm">Sair</button>`;
    },

    showDashboard() {
        const r = this.user.role;
        if (r==='admin')          this.renderAdminDashboard();
        else if (r==='lideranca') this.renderLeaderDashboard();
        else                      this.renderStudentDashboard();
    },

    _resetContainerStyles() {
        const c = document.getElementById('app-container');
        c.style.maxWidth=''; c.style.margin=''; c.style.padding='';
    },

    _authWrap(content) {
        return `<div class="auth-wrapper">
            <div class="auth-box">
                <div class="auth-logo"><img src="logo_transparent.png" style="height:48px" onerror="this.style.display='none'"></div>
                ${content}
            </div>
        </div>`;
    },

    /* ════════════════════════════════════════
       AUTH
    ════════════════════════════════════════ */
    renderLogin(container) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:1.5rem;font-weight:700;font-size:1.35rem;color:var(--primary)">Acesso à GeoTrilha</h2>
            <form id="login-form">
                <div class="form-group"><label>Usuário ou E-mail</label><input type="text" id="l-user" class="form-control" placeholder="colaborador@geobiogas.tech" required></div>
                <div class="form-group">
                    <label>Senha</label>
                    <input type="password" id="l-pass" class="form-control" placeholder="••••••••" required>
                    <div style="text-align:right;margin-top:0.35rem"><a href="#" onclick="App.showView('forgot')" style="font-size:0.82rem;color:var(--primary-light)">Esqueci minha senha</a></div>
                </div>
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.75rem">Entrar →</button>
            </form>
            <div style="margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:0.85rem;color:var(--text-dim);text-align:center">
                Novo colaborador? <a href="#" onclick="App.showView('register')" style="color:var(--primary-light);font-weight:600">Solicitar acesso</a>
            </div>`);
        document.getElementById('login-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Entrando...';
            const res=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},
                body:JSON.stringify({username:document.getElementById('l-user').value,password:document.getElementById('l-pass').value})});
            const data=await res.json();
            if(res.ok&&data.access_token){localStorage.setItem('token',data.access_token);this._resetContainerStyles();this.init();}
            else{alert(data.detail||'Usuário ou senha inválidos.');btn.disabled=false;btn.textContent='Entrar →';}
        };
    },

    renderForgotPassword(container) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:0.5rem;font-weight:700;color:var(--primary)">Recuperar senha</h2>
            <div style="padding:1rem 1.25rem;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;color:#1e40af;font-size:0.88rem;line-height:1.55;margin-bottom:1.5rem">
                Para redefinir sua senha, entre em contato com o <strong>administrador do sistema</strong>. Ele irá gerar um link e te enviar pelo canal da empresa.
            </div>
            <a href="#" onclick="App.showView('login')" class="btn btn-outline" style="display:block;width:100%;text-align:center">← Voltar ao login</a>`);
    },

    renderResetPassword(container, token) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:0.5rem;font-weight:700;color:var(--primary)">Redefinir senha</h2>
            <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1.5rem">Escolha uma nova senha para sua conta.</p>
            <form id="reset-form">
                <input type="hidden" id="reset-token" value="${token}">
                <div class="form-group"><label>Nova senha</label><input type="password" id="r-pass" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                <div class="form-group"><label>Confirmar senha</label><input type="password" id="r-pass2" class="form-control" placeholder="Repita a senha" required minlength="6"></div>
                <p id="reset-err" style="color:#ef4444;font-size:0.85rem;display:none;margin-bottom:0.5rem"></p>
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.75rem">Redefinir senha</button>
            </form>
            <div style="margin-top:1rem;text-align:center"><a href="#" onclick="App.showView('login')" style="font-size:0.83rem;color:var(--primary-light)">← Voltar ao login</a></div>`);
        document.getElementById('reset-form').onsubmit = async (e) => {
            e.preventDefault();
            const pass=document.getElementById('r-pass').value, pass2=document.getElementById('r-pass2').value;
            const err=document.getElementById('reset-err');
            if(pass!==pass2){err.textContent='As senhas não coincidem.';err.style.display='block';return;}
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData(); fd.append('token',document.getElementById('reset-token').value); fd.append('password',pass);
            const res=await fetch('/auth/reset-password',{method:'POST',body:fd});
            if(res.ok){alert('Senha redefinida! Faça login.');window.location.href='/';}
            else{const d=await res.json();err.textContent=d.detail||'Token inválido ou expirado.';err.style.display='block';btn.disabled=false;btn.textContent='Redefinir senha';}
        };
    },

    renderInviteAccept(container, token) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:0.5rem;font-weight:700;color:var(--primary)">Ativar convite</h2>
            <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1.5rem">Crie uma senha para acessar o GeoTrilha.</p>
            <form id="invite-form">
                <input type="hidden" id="i-token" value="${token}">
                <div class="form-group"><label>Senha</label><input type="password" id="i-pass" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.75rem">Ativar acesso</button>
            </form>`);
        document.getElementById('invite-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Ativando...';
            const fd=new FormData(); fd.append('token',document.getElementById('i-token').value); fd.append('password',document.getElementById('i-pass').value);
            const res=await fetch('/invite/accept',{method:'POST',body:fd});
            const data=await res.json();
            if(res.ok){alert(data.message||'Acesso ativado!');window.location.href='/';}
            else{alert(data.detail||'Erro ao ativar.');btn.disabled=false;btn.textContent='Ativar acesso';}
        };
    },

    renderRegister(container) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:1.5rem;font-weight:700;font-size:1.35rem;color:var(--primary)">Solicitar acesso</h2>
            <form id="reg-form">
                <div class="form-group"><label>Nome de usuário</label><input type="text" id="r-user" class="form-control" required></div>
                <div class="form-group"><label>Departamento</label><input type="text" id="r-dept" class="form-control" required></div>
                <div class="form-group"><label>E-mail corporativo</label><input type="email" id="r-email" class="form-control" placeholder="e-mail@geobiogas.tech" required></div>
                <div class="form-group"><label>Senha</label><input type="password" id="r-pass" class="form-control" required></div>
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.75rem;margin-top:0.25rem">Enviar solicitação</button>
            </form>
            <div style="margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid var(--border);font-size:0.85rem;color:var(--text-dim);text-align:center">
                Já tem acesso? <a href="#" onclick="App.showView('login')" style="color:var(--primary-light);font-weight:600">Fazer login</a>
            </div>`);
        document.getElementById('reg-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Enviando...';
            const payload={username:document.getElementById('r-user').value,email:document.getElementById('r-email').value,password:document.getElementById('r-pass').value,department:document.getElementById('r-dept').value};
            const res=await fetch('/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
            if(res.ok){alert('Solicitação enviada! Aguarde aprovação.');this.showView('login');}
            else{const d=await res.json();alert(d.detail||d.error||'Erro no registro.');btn.disabled=false;btn.textContent='Enviar solicitação';}
        };
    },

    showForcePasswordChangeModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        modal.classList.remove('hidden'); body.className='';
        const closeBtn=modal.querySelector('.modal-close');
        if(closeBtn) closeBtn.style.display='none';
        modal.onclick=(e)=>{if(e.target===modal)e.stopPropagation();};
        body.innerHTML=`
            <div style="text-align:center;margin-bottom:1.5rem">
                <div style="width:56px;height:56px;border-radius:14px;background:linear-gradient(135deg,var(--primary),var(--primary-mid));display:flex;align-items:center;justify-content:center;margin:0 auto 1rem;font-size:1.5rem">🔐</div>
                <h3 style="margin-bottom:0.25rem;color:var(--primary)">Troque sua senha</h3>
                <p style="color:var(--text-dim);font-size:0.88rem">Por segurança, defina uma senha pessoal antes de continuar.</p>
            </div>
            <form id="force-form">
                <div class="form-group"><label>Nova senha</label><input type="password" id="fc-p1" class="form-control" placeholder="Mínimo 6 caracteres" required minlength="6"></div>
                <div class="form-group"><label>Confirmar nova senha</label><input type="password" id="fc-p2" class="form-control" placeholder="Repita a senha" required minlength="6"></div>
                <p id="fc-err" style="color:#ef4444;font-size:0.85rem;display:none;margin-bottom:0.5rem"></p>
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.7rem">Salvar e continuar</button>
            </form>`;
        document.getElementById('force-form').onsubmit = async (e) => {
            e.preventDefault();
            const p1=document.getElementById('fc-p1').value, p2=document.getElementById('fc-p2').value;
            const err=document.getElementById('fc-err');
            if(p1!==p2){err.textContent='As senhas não coincidem.';err.style.display='block';return;}
            if(p1==='Mudar@123'){err.textContent='Escolha uma senha diferente da temporária.';err.style.display='block';return;}
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData(); fd.append('password',p1);
            const res=await fetch('/auth/change-password',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){this.user.must_change_password=false;if(closeBtn)closeBtn.style.display='';this.closeModal();this.showDashboard();}
            else{const d=await res.json();err.textContent=d.detail||'Erro ao trocar senha.';err.style.display='block';btn.disabled=false;btn.textContent='Salvar e continuar';}
        };
    },

    logout()        { localStorage.removeItem('token'); this.user=null; this._resetContainerStyles(); this.showView('login'); },
    logoutPending() { alert('Seu cadastro está pendente ou foi rejeitado.'); this.logout(); },

    /* ════════════════════════════════════════
       ADMIN — DASHBOARD (métricas reais)
    ════════════════════════════════════════ */
    async renderAdminDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Dashboard'})+`
            <div class="grid-stats" id="stats-grid">
                <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-info"><div class="stat-value" id="s-users">—</div><div class="stat-label">Usuários Ativos</div></div></div>
                <div class="stat-card"><div class="stat-icon">📚</div><div class="stat-info"><div class="stat-value" id="s-paths">—</div><div class="stat-label">Trilhas</div></div></div>
                <div class="stat-card"><div class="stat-icon">🎬</div><div class="stat-info"><div class="stat-value" id="s-modules">—</div><div class="stat-label">Módulos</div></div></div>
                <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info"><div class="stat-value" id="s-completions">—</div><div class="stat-label">Conclusões</div></div></div>
                <div class="stat-card"><div class="stat-icon">⏳</div><div class="stat-info"><div class="stat-value" id="s-pending">—</div><div class="stat-label">Aprovações Pendentes</div></div></div>
                <div class="stat-card"><div class="stat-icon">📬</div><div class="stat-info"><div class="stat-value" id="s-invites">—</div><div class="stat-label">Convites Pendentes</div></div></div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.25rem;margin-top:0.5rem">
                <div class="card">
                    <h3 style="margin-bottom:1rem;font-size:1rem;color:var(--primary)">Últimos Usuários Cadastrados</h3>
                    <div id="recent-users"><div class="loader">Carregando</div></div>
                </div>
                <div class="card">
                    <h3 style="margin-bottom:1rem;font-size:1rem;color:var(--primary)">Convites Aguardando Ativação</h3>
                    <div id="pending-invites"><div class="loader">Carregando</div></div>
                </div>
            </div>`;

        // Buscar métricas reais do novo endpoint
        try {
            const [statsRes, usersRes] = await Promise.all([
                fetch('/dashboard/stats', {headers:this.apiHeaders()}),
                fetch('/admin/users',     {headers:this.apiHeaders()})
            ]);
            const stats = await statsRes.json();
            const users = await usersRes.json();

            document.getElementById('s-users').textContent      = stats.total_users      ?? '—';
            document.getElementById('s-paths').textContent      = stats.total_paths      ?? '—';
            document.getElementById('s-modules').textContent    = stats.total_modules    ?? '—';
            document.getElementById('s-completions').textContent= stats.completions      ?? '0';
            document.getElementById('s-pending').textContent    = stats.pending_users    ?? '0';
            document.getElementById('s-invites').textContent    = stats.pending_invites  ?? '0';

            // Últimos usuários
            const recentEl=document.getElementById('recent-users');
            const recent=[...users].reverse().slice(0,6);
            recentEl.innerHTML=recent.length?recent.map(u=>`
                <div style="display:flex;justify-content:space-between;align-items:center;padding:0.6rem 0;border-bottom:1px solid var(--border)">
                    <div>
                        <div style="font-weight:600;font-size:0.88rem">${u.username}</div>
                        <div style="font-size:0.75rem;color:var(--text-dim)">${u.email}</div>
                    </div>
                    ${this.statusBadge(u.status)}
                </div>`).join(''):'<p style="color:var(--text-dim);font-size:0.88rem">Nenhum usuário.</p>';

            // Convites pendentes
            const invEl=document.getElementById('pending-invites');
            const convites=users.filter(u=>u.status==='convite_pendente'||u.status==='invited');
            invEl.innerHTML=convites.length?convites.slice(0,6).map(u=>`
                <div style="display:flex;justify-content:space-between;align-items:center;padding:0.6rem 0;border-bottom:1px solid var(--border)">
                    <div style="min-width:0;flex:1">
                        <div style="font-weight:600;font-size:0.88rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${u.username}</div>
                        <div style="font-size:0.75rem;color:var(--text-dim)">${u.email}</div>
                    </div>
                    ${this.actionBtn('Reenviar',`App.adminAction(${u.id},'resend_invite')`)}
                </div>`).join(''):'<p style="color:var(--text-dim);font-size:0.88rem">Nenhum convite pendente. ✓</p>';
        } catch(e) {
            console.error('Erro ao carregar dashboard:', e);
        }
    },

    /* ════════════════════════════════════════
       ADMIN — USUÁRIOS
    ════════════════════════════════════════ */
    async renderAdminUsers() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Gestão de Usuários',actionLabel:'+ Convidar Usuário',actionFn:'App.showInviteUserModal()'})+`
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="u-table">
                    <thead><tr><th>Usuário</th><th>E-mail</th><th>Depto</th><th>Cargo</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        const res=await fetch('/admin/users',{headers:this.apiHeaders()});
        const users=await res.json();
        const tbody=document.querySelector('#u-table tbody'); tbody.innerHTML='';
        if(!users.length){tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">👥</div><p>Nenhum usuário.</p></div></td></tr>';return;}
        users.forEach(u=>{
            tbody.innerHTML+=`<tr>
                <td><strong>${u.username}</strong></td>
                <td style="font-size:0.82rem;color:var(--text-dim)">${u.email}</td>
                <td style="font-size:0.82rem;color:var(--text-dim)">${u.department||'—'}</td>
                <td style="font-size:0.82rem">${u.role}</td>
                <td>${this.statusBadge(u.status)}</td>
                <td><div style="display:flex;gap:4px;flex-wrap:wrap;padding:4px 0">
                    ${u.status==='pending'?this.actionBtn('✓ Aprovar',`App.changeUserStatus(${u.id},'approved')`,'success'):''}
                    ${u.status==='pending'?this.actionBtn('✕ Rejeitar',`App.changeUserStatus(${u.id},'rejected')`,'danger'):''}
                    ${this.actionBtn('Cargo',`App.editUserRole(${u.id},'${u.role}',${u.team_id||0})`)}
                    ${this.actionBtn('🔑 Resetar',`App.triggerPasswordReset(${u.id},'${u.username}')`)}
                    ${this.user.id!==u.id?this.actionBtn('🗑',`App.deleteUser(${u.id},'${u.username}')`,'danger'):''}
                </div></td>
            </tr>`;
        });
    },

    async changeUserStatus(id, status) {
        const fd=new FormData(); fd.append('new_status',status);
        await fetch(`/admin/users/${id}/status`,{method:'POST',headers:this.apiHeaders(),body:fd});
        this.renderAdminUsers();
    },

    async showInviteUserModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const teamsRes=await fetch('/teams',{headers:this.apiHeaders()}); const teams=await teamsRes.json();
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Convidar Novo Usuário</h3>
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
                    <button type="submit" class="btn btn-primary" style="flex:1">Gerar convite</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('invite-user-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Gerando...';
            const fd=new FormData();
            fd.append('username',document.getElementById('iu-user').value);
            fd.append('email',document.getElementById('iu-email').value);
            fd.append('role',document.getElementById('iu-role').value);
            const tid=document.getElementById('iu-team').value; if(tid) fd.append('team_id',tid);
            const res=await fetch('/admin/users/invite',{method:'POST',headers:this.apiHeaders(),body:fd});
            const data=await res.json();
            if(res.ok){this.renderAdminUsers();this.showCopyLinkModal('Convite Gerado ✓','Envie este link para o novo usuário:',data.invite_link);}
            else{alert(data.detail||'Erro ao gerar convite.');btn.disabled=false;btn.textContent='Gerar convite';}
        };
        modal.classList.remove('hidden');
    },

    async editUserRole(id, currentRole, currentTeam) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const teamsRes=await fetch('/teams',{headers:this.apiHeaders()}); const teams=await teamsRes.json();
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Alterar cargo</h3>
            <form id="role-form">
                <div class="form-group"><label>Cargo</label>
                    <select id="e-role" class="form-control">
                        <option value="colaborador" ${currentRole==='colaborador'?'selected':''}>Colaborador</option>
                        <option value="lideranca"   ${currentRole==='lideranca'?'selected':''}>Liderança</option>
                        <option value="admin"       ${currentRole==='admin'?'selected':''}>Administrador</option>
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
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('role-form').onsubmit=async(e)=>{
            e.preventDefault();
            const fd=new FormData(); fd.append('role',document.getElementById('e-role').value);
            const res=await fetch(`/admin/users/${id}/role`,{method:'POST',headers:this.apiHeaders(),body:fd});
            if(!res.ok){alert((await res.json()).detail);return;}
            this.closeModal(); this.renderAdminUsers();
        };
        modal.classList.remove('hidden');
    },

    async deleteUser(id, username) {
        if(!confirm(`Excluir o usuário "${username}"? Esta ação não pode ser desfeita.`)) return;
        const res=await fetch(`/admin/users/${id}`,{method:'DELETE',headers:this.apiHeaders()});
        if(res.ok) this.renderAdminUsers();
        else alert((await res.json()).detail||'Erro ao excluir.');
    },

    async triggerPasswordReset(id, username) {
        if(!confirm(`Resetar a senha de "${username}" para a senha padrão?`)) return;
        const res=await fetch(`/admin/users/${id}/reset-password`,{method:'POST',headers:this.apiHeaders()});
        const data=await res.json();
        if(res.ok) this.showCopyLinkModal('Senha Resetada ✓',`Envie este link para ${username}:`,data.reset_link);
        else alert(data.detail||'Erro ao resetar.');
    },

    /* ════════════════════════════════════════
       ADMIN — CONVITES
    ════════════════════════════════════════ */
    async renderAdminInvites() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Convites & Logs',actionLabel:'↻ Atualizar',actionFn:'App.renderAdminInvites()'})+`
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="inv-table">
                    <thead><tr><th>Usuário</th><th>Status</th><th>Convidado por</th><th>Expira</th><th>Log</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        const res=await fetch('/admin/invites',{headers:this.apiHeaders()});
        const invites=await res.json();
        const tbody=document.querySelector('#inv-table tbody'); tbody.innerHTML='';
        if(!invites.length){tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">📬</div><p>Nenhum convite encontrado.</p></div></td></tr>';return;}
        invites.forEach(i=>{
            const expira=i.invite_date?new Date(new Date(i.invite_date).getTime()+7*24*60*60*1000).toLocaleDateString('pt-BR'):'—';
            tbody.innerHTML+=`<tr>
                <td><strong>${i.username}</strong><br><small style="color:var(--text-dim)">${i.email}</small></td>
                <td>${this.statusBadge(i.status)}</td>
                <td style="font-size:0.82rem">${i.invited_by||'—'}</td>
                <td style="font-size:0.82rem">${expira}</td>
                <td style="font-size:0.78rem;color:var(--text-dim)">${i.last_email_status||'—'}</td>
                <td><div style="display:flex;gap:4px;flex-wrap:wrap">
                    ${this.actionBtn('Reenviar',`App.adminAction(${i.id},'resend_invite')`)}
                    ${i.status!=='ativo'?this.actionBtn('Ativar',`App.adminAction(${i.id},'activate_manual')`,'success'):''}
                    ${i.status!=='ativo'&&i.status!=='convite_expirado'?this.actionBtn('Cancelar',`App.adminAction(${i.id},'cancel_invite')`,'danger'):''}
                </div></td>
            </tr>`;
        });
    },

    async adminAction(id, action) {
        if(!confirm('Confirmar ação?')) return;
        const res=await fetch(`/admin/users/${id}/${action}`,{method:'POST',headers:this.apiHeaders()});
        const data=await res.json();
        if(res.ok){
            if(action==='resend_invite'&&data.invite_link) this.showCopyLinkModal('Novo Convite Gerado','Envie este link para o usuário:',data.invite_link);
            else alert('Ação concluída!');
            this.renderAdminInvites();
        } else alert(data.detail||'Erro ao executar ação.');
    },

    /* ════════════════════════════════════════
       ADMIN — EQUIPES
    ════════════════════════════════════════ */
    async renderAdminTeams() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Gestão de Equipes',actionLabel:'+ Nova Equipe',actionFn:'App.showCreateTeamModal()'})+`
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="t-table">
                    <thead><tr><th>Nome</th><th>Descrição</th><th>Membros</th></tr></thead>
                    <tbody><tr><td colspan="3" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        const res=await fetch('/teams',{headers:this.apiHeaders()}); const teams=await res.json();
        const tbody=document.querySelector('#t-table tbody'); tbody.innerHTML='';
        if(!teams.length){tbody.innerHTML='<tr><td colspan="3"><div class="empty-state"><div class="empty-icon">🏢</div><p>Nenhuma equipe criada.</p></div></td></tr>';return;}
        teams.forEach(t=>{
            const total=t.members?t.members.length:0;
            tbody.innerHTML+=`<tr><td><strong>${t.name}</strong></td><td style="font-size:0.85rem;color:var(--text-dim)">${t.description||'—'}</td><td style="font-size:0.85rem">${total} membro${total!==1?'s':''}</td></tr>`;
        });
    },

    showCreateTeamModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        let emails=[];
        const renderChips=()=>{
            const el=document.getElementById('chips'); if(!el)return;
            el.innerHTML=emails.map((e,i)=>`<span style="display:inline-flex;align-items:center;gap:4px;padding:3px 10px;background:rgba(37,99,235,.08);border:1px solid rgba(37,99,235,.2);border-radius:20px;font-size:0.78rem;margin:2px">${e} <a href="#" onclick="event.preventDefault();App._removeEmail(${i})" style="color:var(--primary-light);font-weight:700;text-decoration:none;line-height:1">×</a></span>`).join('');
        };
        App._removeEmail=(i)=>{emails.splice(i,1);renderChips();};
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Nova Equipe</h3>
            <form id="team-form">
                <div class="form-group"><label>Nome da equipe</label><input type="text" id="t-name" class="form-control" required></div>
                <div class="form-group"><label>Líder (e-mail)</label><input type="email" id="t-admin" class="form-control" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="t-desc" class="form-control" rows="2"></textarea></div>
                <div class="form-group">
                    <label>Membros</label>
                    <div style="display:flex;gap:0.5rem;margin-bottom:0.5rem">
                        <input type="email" id="t-email-input" class="form-control" placeholder="e-mail@geobiogas.tech">
                        <button type="button" onclick="App._addTeamEmail()" style="padding:0 14px;border-radius:8px;background:var(--primary-light);color:white;border:none;cursor:pointer;font-size:0.85rem;white-space:nowrap;font-family:Outfit,sans-serif">Adicionar</button>
                    </div>
                    <div id="chips" style="display:flex;flex-wrap:wrap;gap:2px;min-height:28px"></div>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Criar equipe</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        App._addTeamEmail=()=>{const input=document.getElementById('t-email-input');const val=input.value.trim();if(val&&val.includes('@')&&!emails.includes(val)){emails.push(val);input.value='';renderChips();}};
        document.getElementById('t-email-input').onkeypress=(e)=>{if(e.key==='Enter'){e.preventDefault();App._addTeamEmail();}};
        document.getElementById('team-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData();
            fd.append('name',document.getElementById('t-name').value);
            fd.append('team_admin_email',document.getElementById('t-admin').value);
            fd.append('description',document.getElementById('t-desc').value);
            if(emails.length) fd.append('emails',emails.join(','));
            const res=await fetch('/teams',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){this.closeModal();this.renderAdminTeams();}
            else{alert((await res.json()).detail||'Erro ao criar equipe.');btn.disabled=false;btn.textContent='Criar equipe';}
        };
        modal.classList.remove('hidden');
    },

    /* ════════════════════════════════════════
       ADMIN — TRILHAS / CURSOS / MÓDULOS
    ════════════════════════════════════════ */
    async renderAdminPaths() {
        this._resetContainerStyles(); this.currentPath=null; this.currentCourse=null;
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Trilhas de Aprendizagem',actionLabel:'+ Nova Trilha',actionFn:'App.showCreatePathModal()'})+
            `<div id="paths-wrapper"><div class="loader">Carregando</div></div>`;
        const res=await fetch('/paths',{headers:this.apiHeaders()}); const paths=await res.json();
        const wrapper=document.getElementById('paths-wrapper'); wrapper.innerHTML='';
        if(!paths.length){wrapper.innerHTML='<div class="empty-state"><div class="empty-icon">📚</div><p>Nenhuma trilha criada ainda.</p></div>';return;}
        paths.forEach(p=>{
            wrapper.innerHTML+=`<div class="card" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1;min-width:0">
                    <h3 style="margin:0 0 0.2rem;font-size:1rem;color:var(--primary)">${p.title}</h3>
                    <p style="color:var(--text-dim);font-size:0.83rem;margin:0">${p.description||'Sem descrição.'}</p>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditPathModal(${p.id},'${p.title.replace(/'/g,"\\'")}','${(p.description||'').replace(/'/g,"\\'")}',${!!p.is_standard_training})`)}
                    ${this.actionBtn('🗑',`App.deletePath(${p.id},'${p.title.replace(/'/g,"\\'")}')`, 'danger')}
                    ${this.actionBtn('Ver cursos →',`App.renderAdminCourses(${p.id},'${p.title.replace(/'/g,"\\'")}')`, 'primary')}
                </div>
            </div>`;
        });
    },

    _pathModal(id, title, desc, is_std, isEdit) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">${isEdit?'Editar':'Nova'} Trilha</h3>
            <form id="pform">
                <div class="form-group"><label>Título</label><input type="text" id="p-title" class="form-control" value="${title||''}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="p-desc" class="form-control" rows="3">${desc||''}</textarea></div>
                <div class="form-group" style="display:flex;gap:8px;align-items:center">
                    <input type="checkbox" id="p-std" ${is_std?'checked':''} style="width:16px;height:16px;accent-color:var(--primary-light)">
                    <label style="margin:0;font-size:0.88rem">Treinamento obrigatório padronizado</label>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">${isEdit?'Salvar':'Criar'}</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('pform').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('title',document.getElementById('p-title').value);
            fd.append('description',document.getElementById('p-desc').value);
            fd.append('is_standard_training',document.getElementById('p-std').checked);
            await fetch(isEdit?`/paths/${id}`:'/paths',{method:isEdit?'PUT':'POST',headers:this.apiHeaders(),body:fd});
            this.closeModal(); this.renderAdminPaths();
        };
        modal.classList.remove('hidden');
    },
    showCreatePathModal()                   { this._pathModal(null,'','',false,false); },
    showEditPathModal(id,title,desc,is_std) { this._pathModal(id,title,desc,is_std,true); },
    async deletePath(id, title) {
        if(!confirm(`Excluir a trilha "${title}"?\nTodos os cursos e módulos serão removidos.`)) return;
        await fetch(`/paths/${id}`,{method:'DELETE',headers:this.apiHeaders()});
        this.renderAdminPaths();
    },

    async renderAdminCourses(pathId, pathTitle) {
        this._resetContainerStyles(); this.currentPath={id:pathId,title:pathTitle}; this.currentCourse=null;
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:`Cursos — ${pathTitle}`,
            backLabel:'Trilhas',backFn:'App.renderAdminPaths()',
            actionLabel:'+ Novo Curso',actionFn:`App.showCreateCourseModal(${pathId})`,
            breadcrumbs:[{label:'Trilhas',fn:'App.renderAdminPaths()'},{label:pathTitle}]
        })+`<div id="courses-wrapper"><div class="loader">Carregando</div></div>`;
        const res=await fetch(`/paths/${pathId}/courses`,{headers:this.apiHeaders()}); const courses=await res.json();
        const wrapper=document.getElementById('courses-wrapper'); wrapper.innerHTML='';
        if(!courses.length){wrapper.innerHTML='<div class="empty-state"><div class="empty-icon">📖</div><p>Nenhum curso nesta trilha ainda.</p></div>';return;}
        courses.forEach(c=>{
            wrapper.innerHTML+=`<div class="card" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1;min-width:0">
                    <h3 style="margin:0 0 0.2rem;font-size:1rem;color:var(--primary)">${c.order?c.order+'. ':''}${c.title}</h3>
                    <p style="color:var(--text-dim);font-size:0.83rem;margin:0">${c.description||''}</p>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️',`App.showEditCourseModal(${c.id},'${c.title.replace(/'/g,"\\'")}','${(c.description||'').replace(/'/g,"\\'")}',${c.order||1})`)}
                    ${this.actionBtn('🗑',`App.deleteCourse(${c.id},'${c.title.replace(/'/g,"\\'")}',${pathId})`,'danger')}
                    ${this.actionBtn('Módulos →',`App.renderAdminModules(${c.id},'${c.title.replace(/'/g,"\\'")}')`, 'primary')}
                </div>
            </div>`;
        });
    },

    _courseModal(id, title, desc, order, pathId, isEdit) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">${isEdit?'Editar':'Novo'} Curso</h3>
            <form id="cform">
                <div class="form-group"><label>Título</label><input type="text" id="c-title" class="form-control" value="${title||''}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="c-desc" class="form-control" rows="3">${desc||''}</textarea></div>
                <div class="form-group"><label>Ordem</label><input type="number" id="c-order" class="form-control" value="${order||1}"></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">${isEdit?'Salvar':'Criar'}</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('cform').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('title',document.getElementById('c-title').value);
            fd.append('description',document.getElementById('c-desc').value);
            fd.append('order',document.getElementById('c-order').value);
            await fetch(isEdit?`/courses/${id}`:`/paths/${pathId}/courses`,{method:isEdit?'PUT':'POST',headers:this.apiHeaders(),body:fd});
            this.closeModal(); this.renderAdminCourses(this.currentPath.id,this.currentPath.title);
        };
        modal.classList.remove('hidden');
    },
    showCreateCourseModal(pathId)           { this._courseModal(null,'','',1,pathId,false); },
    showEditCourseModal(id,title,desc,order){ this._courseModal(id,title,desc,order,null,true); },
    async deleteCourse(id, title, pathId) {
        if(!confirm(`Excluir o curso "${title}"?`)) return;
        await fetch(`/courses/${id}`,{method:'DELETE',headers:this.apiHeaders()});
        this.renderAdminCourses(pathId,this.currentPath.title);
    },

    async renderAdminModules(courseId, courseTitle) {
        this._resetContainerStyles(); this.currentCourse={id:courseId,title:courseTitle};
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:`Módulos — ${courseTitle}`,
            backLabel:'Cursos',backFn:`App.renderAdminCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')`,
            actionLabel:'+ Novo Módulo',actionFn:`App.showModuleUpload(${courseId},'${courseTitle.replace(/'/g,"\\'")}')`,
            breadcrumbs:[
                {label:'Trilhas',fn:'App.renderAdminPaths()'},
                {label:this.currentPath.title,fn:`App.renderAdminCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')` },
                {label:courseTitle}
            ]
        })+`
        <div id="modules-wrapper"><div class="loader">Carregando</div></div>
        <div class="card hidden" id="module-upload-card" style="margin-top:2rem;border-top:3px solid var(--primary-light)">
            <h3 id="module-upload-title" style="margin-bottom:1.5rem;color:var(--primary)">Novo Módulo</h3>
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
                        <div class="form-group"><label>Thumbnail (opcional)</label><input type="file" id="m-thumb" class="form-control" accept="image/*"></div>
                    </div>
                </div>
                <div class="progress-track" id="m-prog-wrap" style="display:none;margin-top:0.5rem"><div class="progress-fill" id="m-prog-bar" style="width:0%"></div></div>
                <p id="m-status" style="font-size:0.83rem;color:var(--text-dim);text-align:center;margin-top:0.4rem;min-height:1.2em"></p>
                <div style="display:flex;gap:0.5rem;margin-top:0.75rem">
                    <button type="submit" id="btn-upload-module" class="btn btn-primary" style="flex:1">Fazer upload</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="document.getElementById('module-upload-card').classList.add('hidden')">Cancelar</button>
                </div>
            </form>
        </div>
        <div id="quiz-editor-section" class="card hidden" style="margin-top:2rem"></div>`;
        const res=await fetch(`/courses/${courseId}/modules`,{headers:this.apiHeaders()}); const modules=await res.json();
        const wrapper=document.getElementById('modules-wrapper'); wrapper.innerHTML='';
        if(!modules.length){wrapper.innerHTML='<div class="empty-state"><div class="empty-icon">🎬</div><p>Nenhum módulo neste curso ainda.</p></div>';}
        modules.forEach(m=>{
            wrapper.innerHTML+=`<div class="card" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1;min-width:0">
                    <span style="font-size:0.7rem;color:var(--text-dim);font-weight:700;text-transform:uppercase;letter-spacing:0.07em">Módulo ${m.order||'—'}</span>
                    <h4 style="margin:0.15rem 0 0;font-size:0.95rem">${m.title}</h4>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️',`App.showEditModuleModal(${m.id},'${m.title.replace(/'/g,"\\'")}','${(m.description||'').replace(/'/g,"\\'")}',${m.order||1},${m.validity_months||0})`)}
                    ${this.actionBtn('🗑',`App.deleteModule(${m.id},'${m.title.replace(/'/g,"\\'")}',${courseId})`,'danger')}
                    ${this.actionBtn('🎮 Quiz',`App.openQuizEditor(${m.id},'${m.video_url}')`)}
                </div>
            </div>`;
        });
        this.bindModuleForm();
    },

    showEditModuleModal(id, title, desc, order, valMonths) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:0.5rem;color:var(--primary)">Editar Módulo</h3>
            <p style="color:var(--text-dim);font-size:0.83rem;margin-bottom:1rem">Para trocar o vídeo, exclua e recrie o módulo.</p>
            <form id="emod-form">
                <div class="form-group"><label>Título</label><input type="text" id="em-title" class="form-control" value="${title}" required></div>
                <div class="form-group"><label>Descrição</label><textarea id="em-desc" class="form-control" rows="3">${desc}</textarea></div>
                <div style="display:flex;gap:1rem">
                    <div class="form-group" style="flex:1"><label>Ordem</label><input type="number" id="em-order" class="form-control" value="${order}"></div>
                    <div class="form-group" style="flex:1"><label>Validade certif. (meses)</label><input type="number" id="em-val" class="form-control" value="${valMonths||''}" placeholder="Opcional"></div>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('emod-form').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('title',document.getElementById('em-title').value);
            fd.append('description',document.getElementById('em-desc').value);
            fd.append('order',document.getElementById('em-order').value);
            if(document.getElementById('em-val').value) fd.append('validity_months',document.getElementById('em-val').value);
            await fetch(`/modules/${id}`,{method:'PUT',headers:this.apiHeaders(),body:fd});
            this.closeModal(); this.renderAdminModules(this.currentCourse.id,this.currentCourse.title);
        };
        modal.classList.remove('hidden');
    },

    async deleteModule(id, title, courseId) {
        if(!confirm(`Excluir o módulo "${title}"?`)) return;
        await fetch(`/modules/${id}`,{method:'DELETE',headers:this.apiHeaders()});
        this.renderAdminModules(courseId,this.currentCourse.title);
    },

    showModuleUpload(courseId, courseTitle) {
        const card=document.getElementById('module-upload-card');
        card.classList.remove('hidden');
        document.getElementById('m-course-id').value=courseId;
        document.getElementById('module-upload-title').textContent=`Novo Módulo em: ${courseTitle}`;
        card.scrollIntoView({behavior:'smooth',block:'start'});
    },

    bindModuleForm() {
        document.getElementById('module-upload-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=document.getElementById('btn-upload-module'), status=document.getElementById('m-status');
            const file=document.getElementById('m-video').files[0], thumb=document.getElementById('m-thumb').files[0];
            const courseId=document.getElementById('m-course-id').value;
            btn.disabled=true; btn.textContent='Enviando...';
            document.getElementById('m-prog-wrap').style.display='block';
            status.textContent='Iniciando upload...';
            try{
                const initRes=await fetch('/modules/upload/init?filename='+encodeURIComponent(file.name),{method:'POST',headers:this.apiHeaders()});
                const{upload_id}=await initRes.json();
                const chunkSize=5*1024*1024, totalChunks=Math.ceil(file.size/chunkSize);
                for(let i=0;i<totalChunks;i++){
                    const chunk=file.slice(i*chunkSize,Math.min((i+1)*chunkSize,file.size));
                    const fd=new FormData(); fd.append('upload_id',upload_id); fd.append('filename',file.name); fd.append('chunk_index',i); fd.append('chunk',chunk);
                    await fetch('/modules/upload/chunk',{method:'POST',headers:this.apiHeaders(),body:fd});
                    const pct=Math.round(((i+1)/totalChunks)*100);
                    document.getElementById('m-prog-bar').style.width=pct+'%';
                    status.textContent=`Enviando... ${pct}%`;
                }
                status.textContent='Finalizando...';
                const finalFd=new FormData();
                finalFd.append('title',document.getElementById('m-title').value);
                finalFd.append('description',document.getElementById('m-desc').value);
                finalFd.append('order',document.getElementById('m-order').value);
                finalFd.append('upload_id',upload_id); finalFd.append('filename',file.name);
                if(thumb) finalFd.append('thumbnail',thumb);
                await fetch(`/courses/${courseId}/modules`,{method:'POST',headers:this.apiHeaders(),body:finalFd});
                status.textContent='✓ Upload concluído!';
                setTimeout(()=>this.renderAdminModules(courseId,this.currentCourse.title),1000);
            }catch(err){status.textContent='Erro no upload. Tente novamente.';btn.disabled=false;btn.textContent='Fazer upload';}
        };
    },

    openQuizEditor(moduleId, videoUrl) {
        const sec=document.getElementById('quiz-editor-section'); sec.classList.remove('hidden');
        sec.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Configurar Quiz</h3>
            <div style="display:flex;gap:2rem;align-items:flex-start;flex-wrap:wrap">
                <div style="flex:1;min-width:260px">
                    <video id="editor-video" src="${videoUrl}" controls style="width:100%;border-radius:8px;background:#000;max-height:280px"></video>
                    <div style="display:flex;gap:0.5rem;margin-top:0.5rem;align-items:center">
                        <button type="button" onclick="document.getElementById('q-time').value=Math.floor(document.getElementById('editor-video').currentTime)" style="padding:5px 12px;border-radius:6px;font-size:0.8rem;cursor:pointer;background:var(--bg-main);border:1px solid var(--border);color:var(--text-main);font-family:Outfit,sans-serif">📌 Marcar momento</button>
                        <input type="number" id="q-time" class="form-control" style="width:90px" placeholder="seg." readonly>
                    </div>
                </div>
                <div style="flex:1.2;min-width:260px">
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
                        <div style="display:flex;gap:8px;align-items:center;padding:0.75rem;background:#eff6ff;border-radius:8px;border:1px solid #bfdbfe;margin-bottom:1rem">
                            <input type="checkbox" id="q-final" style="width:16px;height:16px;accent-color:var(--primary-light)">
                            <label style="margin:0;font-size:0.87rem;color:#1e40af">Prova final (exibida ao fim do vídeo)</label>
                        </div>
                        <button type="submit" class="btn btn-primary" style="width:100%">Salvar questão</button>
                    </form>
                </div>
            </div>`;
        sec.scrollIntoView({behavior:'smooth'});
        document.getElementById('quiz-form').onsubmit=async(e)=>{
            e.preventDefault();
            const payload={text:document.getElementById('q-text').value,option_a:document.getElementById('q-a').value,option_b:document.getElementById('q-b').value,option_c:document.getElementById('q-c').value,option_d:document.getElementById('q-d').value,correct_option:document.getElementById('q-corr').value,timestamp:parseFloat(document.getElementById('q-time').value)||0,is_final_exam:document.getElementById('q-final').checked};
            await fetch(`/modules/${moduleId}/questions`,{method:'POST',headers:this.apiJsonHeaders(),body:JSON.stringify(payload)});
            alert('Questão salva!'); e.target.reset();
        };
    },

    /* ════════════════════════════════════════
       LIDERANÇA
    ════════════════════════════════════════ */
    async renderLeaderDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Minha Equipe',actionLabel:'+ Convidar Colaborador',actionFn:'App.showInviteUserModal()'})+`
            <!-- Stats da equipe -->
            <div class="grid-stats" id="team-stats" style="margin-bottom:1.5rem">
                <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-info"><div class="stat-value" id="ts-members">—</div><div class="stat-label">Membros Ativos</div></div></div>
                <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info"><div class="stat-value" id="ts-done">—</div><div class="stat-label">Módulos Concluídos</div></div></div>
                <div class="stat-card"><div class="stat-icon">📊</div><div class="stat-info"><div class="stat-value" id="ts-pct">—</div><div class="stat-label">Progresso Médio</div></div></div>
            </div>
            <!-- Tabela de progresso -->
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="team-table">
                    <thead><tr><th>Colaborador</th><th>E-mail</th><th>Cargo</th><th>Módulos</th><th>Progresso</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;

        try {
            const res=await fetch('/team/progress',{headers:this.apiHeaders()});
            const members=await res.json();
            const tbody=document.querySelector('#team-table tbody'); tbody.innerHTML='';

            if(!members.length){
                tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">👥</div><p>Nenhum colaborador na equipe ainda.</p></div></td></tr>';
                document.getElementById('ts-members').textContent='0';
                document.getElementById('ts-done').textContent='0';
                document.getElementById('ts-pct').textContent='0%';
                return;
            }

            // Stats
            const totalDone=members.reduce((s,m)=>s+m.modules_done,0);
            const avgPct=Math.round(members.reduce((s,m)=>s+m.percent,0)/members.length);
            document.getElementById('ts-members').textContent=members.length;
            document.getElementById('ts-done').textContent=totalDone;
            document.getElementById('ts-pct').textContent=avgPct+'%';

            members.forEach(u=>{
                const pct=u.percent||0;
                const barColor=pct===100?'#22c55e':pct>=50?'var(--primary-light)':'#f59e0b';
                tbody.innerHTML+=`<tr>
                    <td><strong>${u.username}</strong></td>
                    <td style="font-size:0.82rem;color:var(--text-dim)">${u.email}</td>
                    <td style="font-size:0.82rem">${u.role}</td>
                    <td style="font-size:0.82rem">${u.modules_done}/${u.modules_total}</td>
                    <td style="min-width:120px">
                        <div style="display:flex;align-items:center;gap:0.5rem">
                            <div class="progress-track" style="flex:1;height:6px">
                                <div class="progress-fill" style="width:${pct}%;background:${barColor}"></div>
                            </div>
                            <span style="font-size:0.75rem;font-weight:700;color:${barColor};width:30px">${pct}%</span>
                        </div>
                    </td>
                    <td>${this.actionBtn('🎯 Atribuir Trilha',`App.showAssignPathModal(${u.user_id},'${u.username}')`)}</td>
                </tr>`;
            });
        } catch(e) {
            console.error('Erro ao carregar equipe:', e);
        }
    },

    showAddMemberModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Novo Colaborador</h3>
            <form id="add-member-form">
                <div class="form-group"><label>Usuário</label><input type="text" id="m-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail</label><input type="email" id="m-email" class="form-control" required></div>
                <div class="form-group"><label>Senha inicial</label><input type="password" id="m-pass" class="form-control" required></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Cadastrar</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('add-member-form').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('username',document.getElementById('m-user').value);
            fd.append('email',document.getElementById('m-email').value);
            fd.append('password',document.getElementById('m-pass').value);
            await fetch('/admin/users',{method:'POST',headers:this.apiHeaders(),body:fd});
            this.closeModal(); this.renderLeaderDashboard();
        };
        modal.classList.remove('hidden');
    },

    async showAssignPathModal(userId, username) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const pathsRes=await fetch('/paths',{headers:this.apiHeaders()}); const paths=await pathsRes.json();
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Atribuir Trilha — ${username}</h3>
            <form id="assign-form">
                <div class="form-group"><label>Trilha</label>
                    <select id="a-path" class="form-control">${paths.map(p=>`<option value="${p.id}">${p.title}</option>`).join('')}</select>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Atribuir</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('assign-form').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('user_id',userId); fd.append('path_id',document.getElementById('a-path').value);
            await fetch('/enrollments',{method:'POST',headers:this.apiHeaders(),body:fd});
            this.closeModal(); alert('Trilha atribuída com sucesso!');
        };
        modal.classList.remove('hidden');
    },

    /* ════════════════════════════════════════
       ALUNO — DASHBOARD com progresso real
    ════════════════════════════════════════ */
    async renderStudentDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:`Olá, ${this.user.username}! 👋`})+`
            <div class="grid-stats">
                <div class="stat-card"><div class="stat-icon">📚</div><div class="stat-info"><div class="stat-value" id="sd-paths">—</div><div class="stat-label">Trilhas Matriculadas</div></div></div>
                <div class="stat-card"><div class="stat-icon">🎬</div><div class="stat-info"><div class="stat-value" id="sd-modules">—</div><div class="stat-label">Total de Módulos</div></div></div>
                <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info"><div class="stat-value" id="sd-done">—</div><div class="stat-label">Módulos Concluídos</div></div></div>
                <div class="stat-card"><div class="stat-icon">🏆</div><div class="stat-info"><div class="stat-value" id="sd-certs">—</div><div class="stat-label">Certificados</div></div></div>
            </div>
            <h3 style="margin-bottom:1rem;color:var(--primary);font-size:1.1rem">Minhas Trilhas</h3>
            <div class="grid" id="dash-paths"><div class="loader">Carregando</div></div>`;

        // Usa /my-paths — só trilhas matriculadas
        const [pathsRes, certsRes] = await Promise.all([
            fetch('/my-paths', {headers:this.apiHeaders()}),
            fetch('/my-certificates', {headers:this.apiHeaders()})
        ]);
        const paths = pathsRes.ok ? await pathsRes.json() : [];
        const certs = certsRes.ok ? await certsRes.json() : [];

        document.getElementById('sd-paths').textContent=paths.length;
        document.getElementById('sd-certs').textContent=certs.length;

        let totalModules=0, totalDone=0;
        const grid=document.getElementById('dash-paths'); grid.innerHTML='';

        if(!paths.length){
            grid.innerHTML=`<div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">📚</div>
                <p>Você ainda não está matriculado em nenhuma trilha.</p>
                <p style="font-size:0.85rem;margin-top:0.5rem">Entre em contato com seu líder ou administrador.</p>
            </div>`;
            document.getElementById('sd-modules').textContent='0';
            document.getElementById('sd-done').textContent='0';
            return;
        }

        for(const p of paths){
            let progData={total:0,completed:0,percent:0};
            try{
                const pRes=await fetch(`/paths/${p.id}/progress`,{headers:this.apiHeaders()});
                if(pRes.ok) progData=await pRes.json();
            }catch(e){}
            totalModules+=progData.total;
            totalDone+=progData.completed;
            const pct=progData.percent||0;
            const fillColor=pct===100?'#22c55e':'var(--primary-light)';
            grid.innerHTML+=`<div class="path-card">
                <div class="path-icon">📚</div>
                <h3 style="margin:0 0 0.4rem;font-size:1rem;color:var(--primary)">${p.title}</h3>
                <p style="color:var(--text-dim);font-size:0.85rem;flex:1;margin:0 0 1rem;line-height:1.5">${p.description||''}</p>
                <div style="margin-bottom:0.75rem">
                    <div style="display:flex;justify-content:space-between;font-size:0.78rem;color:var(--text-dim);margin-bottom:0.3rem">
                        <span>${progData.completed} de ${progData.total} módulos</span>
                        <span style="font-weight:700;color:${fillColor}">${pct}%</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div></div>
                </div>
                <button class="btn btn-primary" style="width:100%" onclick="App.showStudentCourses(${p.id},'${p.title.replace(/'/g,"\\'")}')">
                    ${pct===100?'✓ Concluída — Revisar':'Continuar →'}
                </button>
            </div>`;
        }
        document.getElementById('sd-modules').textContent=totalModules;
        document.getElementById('sd-done').textContent=totalDone;
    },

    /* ════════════════════════════════════════
       ALUNO — TRILHAS / CURSOS / MÓDULOS
    ════════════════════════════════════════ */
    async renderStudentPaths() {
        this._resetContainerStyles(); this.currentPath=null; this.currentCourse=null;
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Minhas Trilhas',backLabel:'Início',backFn:'App.renderStudentDashboard()'})+
            `<div class="grid" id="student-paths"><div class="loader">Carregando</div></div>`;
        // Usa /my-paths — só trilhas matriculadas
        const res=await fetch('/my-paths',{headers:this.apiHeaders()});
        const paths=res.ok?await res.json():[];
        const grid=document.getElementById('student-paths'); grid.innerHTML='';
        if(!paths.length){
            grid.innerHTML=`<div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">📚</div>
                <p>Você não está matriculado em nenhuma trilha.</p>
                <p style="font-size:0.85rem;margin-top:0.5rem">Entre em contato com seu líder ou administrador.</p>
            </div>`;
            return;
        }
        for(const p of paths){
            let pct=0;
            try{const pr=await fetch(`/paths/${p.id}/progress`,{headers:this.apiHeaders()});if(pr.ok){const d=await pr.json();pct=d.percent||0;}}catch(e){}
            const fillColor=pct===100?'#22c55e':'var(--primary-light)';
            grid.innerHTML+=`<div class="path-card">
                <div class="path-icon">📚</div>
                <h3 style="margin:0 0 0.4rem;font-size:1rem;color:var(--primary)">${p.title}</h3>
                <p style="color:var(--text-dim);font-size:0.85rem;flex:1;margin:0 0 0.75rem;line-height:1.5">${p.description||''}</p>
                <div style="margin-bottom:0.75rem">
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-dim);margin-bottom:0.3rem">
                        <span>Progresso</span><span style="font-weight:700;color:${fillColor}">${pct}%</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div></div>
                </div>
                <button class="btn btn-primary" style="width:100%" onclick="App.showStudentCourses(${p.id},'${p.title.replace(/'/g,"\\'")}')">
                    ${pct===100?'✓ Concluída':'Acessar →'}
                </button>
            </div>`;
        }
    },

    async showStudentCourses(pathId, pathTitle) {
        this._resetContainerStyles(); this.currentPath={id:pathId,title:pathTitle};
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:pathTitle,
            backLabel:'Trilhas',backFn:'App.renderStudentPaths()',
            breadcrumbs:[{label:'Início',fn:'App.renderStudentDashboard()'},{label:'Trilhas',fn:'App.renderStudentPaths()'},{label:pathTitle}]
        })+`<div class="grid" id="student-courses"><div class="loader">Carregando</div></div>`;
        const res=await fetch(`/paths/${pathId}/courses`,{headers:this.apiHeaders()}); const courses=await res.json();
        const grid=document.getElementById('student-courses'); grid.innerHTML='';
        if(!courses.length){grid.innerHTML='<div class="empty-state"><div class="empty-icon">📖</div><p>Nenhum curso disponível.</p></div>';return;}
        // Buscar progresso de cada curso
        for(const c of courses){
            let done=0, total=(c.modules||[]).length;
            try{
                const pr=await fetch(`/courses/${c.id}/progress`,{headers:this.apiHeaders()});
                if(pr.ok){const d=await pr.json();done=d.filter(x=>x.completed).length;}
            }catch(e){}
            const pct=total>0?Math.round((done/total)*100):0;
            const fillColor=pct===100?'#22c55e':'var(--primary-light)';
            grid.innerHTML+=`<div class="path-card">
                <div class="path-icon" style="background:linear-gradient(135deg,#1e40af,#3b82f6)">🎓</div>
                <h3 style="margin:0 0 0.4rem;font-size:1rem;color:var(--primary)">${c.order?c.order+'. ':''}${c.title}</h3>
                <p style="color:var(--text-dim);font-size:0.85rem;flex:1;margin:0 0 0.75rem;line-height:1.5">${c.description||''}</p>
                <div style="margin-bottom:0.75rem">
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-dim);margin-bottom:0.3rem">
                        <span>${done} de ${total} módulos</span><span style="font-weight:700;color:${fillColor}">${pct}%</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div></div>
                </div>
                <button class="btn btn-primary" style="width:100%" onclick="App.showStudentModules(${c.id},'${c.title.replace(/'/g,"\\'")}')">Ver módulos →</button>
            </div>`;
        }
    },

    async showStudentModules(courseId, courseTitle) {
        this._resetContainerStyles(); this.currentCourse={id:courseId,title:courseTitle};
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:courseTitle,
            backLabel:this.currentPath.title,backFn:`App.showStudentCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')`,
            breadcrumbs:[
                {label:'Início',fn:'App.renderStudentDashboard()'},
                {label:'Trilhas',fn:'App.renderStudentPaths()'},
                {label:this.currentPath.title,fn:`App.showStudentCourses(${this.currentPath.id},'${this.currentPath.title.replace(/'/g,"\\'")}')` },
                {label:courseTitle}
            ]
        })+`<div id="student-modules"><div class="loader">Carregando</div></div>`;
        const [modulesRes, progressRes] = await Promise.all([
            fetch(`/courses/${courseId}/modules`,  {headers:this.apiHeaders()}),
            fetch(`/courses/${courseId}/progress`, {headers:this.apiHeaders()})
        ]);
        const modules  = await modulesRes.json();
        const progress = progressRes.ok ? await progressRes.json() : [];
        const doneIds  = new Set(progress.filter(p=>p.completed).map(p=>p.module_id));

        const grid=document.getElementById('student-modules'); grid.innerHTML='';
        if(!modules.length){grid.innerHTML='<div class="empty-state"><div class="empty-icon">🎬</div><p>Nenhum módulo disponível.</p></div>';return;}

        modules.forEach(m=>{
            const isDone=doneIds.has(m.id);
            grid.innerHTML+=`<div class="module-card" onclick="App.playModule(${m.id},${courseId},${isDone})">
                <div class="module-play-icon" style="${isDone?'background:linear-gradient(135deg,#16a34a,#22c55e)':''}">
                    ${isDone
                        ? `<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:white"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`
                        : `<svg viewBox="0 0 24 24" style="width:18px;height:18px;fill:white;margin-left:2px"><path d="M8 5v14l11-7z"/></svg>`
                    }
                </div>
                <div class="module-info">
                    <h4 style="${isDone?'color:var(--text-dim);text-decoration:line-through':''}">${m.title}</h4>
                    <p>Módulo ${m.order||''} ${isDone?'· <span style="color:#22c55e;font-weight:600">Concluído ✓</span>':''}</p>
                </div>
                <div class="module-status">
                    ${isDone
                        ? `<span style="font-size:1.1rem">✅</span>`
                        : `<span style="font-size:0.75rem;color:var(--text-light)">▶</span>`
                    }
                </div>
            </div>`;
        });
    },

    async playModule(moduleId, courseId, alreadyDone=false) {
        const res=await fetch(`/courses/${courseId}/modules`,{headers:this.apiHeaders()}); const modules=await res.json();
        const target=modules.find(m=>m.id===moduleId);
        if(!target) return alert('Módulo não encontrado.');
        const inlineQuizzes=(target.questions||[]).filter(q=>!q.is_final_exam);
        const finalQuizzes =(target.questions||[]).filter(q=> q.is_final_exam);
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        modal.classList.remove('hidden');
        body.className='modal-player';
        body.innerHTML=`
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">
                <h3 style="margin:0;font-size:1rem;color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:88%">${target.title}</h3>
                <button onclick="App.closeModal()" style="background:rgba(255,255,255,.12);border:none;cursor:pointer;width:30px;height:30px;border-radius:50%;color:white;font-size:1.1rem;display:flex;align-items:center;justify-content:center;flex-shrink:0" onmouseover="this.style.background='rgba(255,255,255,.22)'" onmouseout="this.style.background='rgba(255,255,255,.12)'">×</button>
            </div>
            <div style="position:relative;background:#000;border-radius:10px;overflow:hidden">
                <video id="st-video" src="${target.video_url}" controls autoplay style="width:100%;display:block;max-height:68vh"></video>
                <div id="quiz-overlay" style="display:none;position:absolute;top:0;left:0;width:100%;height:100%;background:rgba(7,19,38,.95);align-items:center;justify-content:center;padding:2rem;box-sizing:border-box;pointer-events:all;z-index:10">
                    <div style="width:100%;max-width:520px">
                        <div style="display:inline-block;padding:3px 10px;background:rgba(59,130,246,.2);border:1px solid rgba(59,130,246,.4);border-radius:20px;font-size:0.7rem;font-weight:700;text-transform:uppercase;letter-spacing:0.08em;color:#93c5fd;margin-bottom:0.75rem">Quiz</div>
                        <h3 id="q-text-display" style="color:white;margin-bottom:1.25rem;line-height:1.45;font-size:1.05rem"></h3>
                        <div id="q-opts" style="display:flex;flex-direction:column;gap:0.5rem"></div>
                    </div>
                </div>
            </div>
            <div id="final-exam-section" style="display:none;margin-top:1.25rem;padding-top:1.25rem;border-top:1px solid rgba(255,255,255,.1);text-align:center">
                <h4 style="margin-bottom:0.4rem;color:white">🎉 Vídeo concluído!</h4>
                <p style="color:rgba(255,255,255,.6);font-size:0.88rem;margin-bottom:1rem">Responda à prova final para completar este módulo.</p>
                <button class="btn btn-primary" id="btn-final-exam">Iniciar Prova Final</button>
            </div>
            ${alreadyDone&&!finalQuizzes.length?'<div style="margin-top:1rem;text-align:center;padding:0.75rem;background:rgba(34,197,94,.15);border-radius:8px;color:#86efac;font-size:0.88rem">✓ Módulo já concluído — você está revisando o conteúdo</div>':''}`;

        const video=document.getElementById('st-video'), asked=new Set();
        video.ontimeupdate=()=>{
            if(video.paused) return;
            inlineQuizzes.forEach(q=>{
                if(Math.abs(video.currentTime-q.timestamp)<0.5&&!asked.has(q.id)){asked.add(q.id);video.pause();video.controls=false;this.showQuizOverlay(q);}
            });
            // Marcar como concluído ao chegar no fim (sem prova final)
            if(video.duration>0&&video.currentTime>=video.duration-1){
                if(finalQuizzes.length>0){
                    document.getElementById('final-exam-section').style.display='block';
                } else if(!alreadyDone){
                    this.markModuleComplete(moduleId, 100);
                }
            }
        };
        if(finalQuizzes.length>0) document.getElementById('btn-final-exam').onclick=()=>this.startFinalExam(finalQuizzes, moduleId);
    },

    // NOVO: Registrar conclusão do módulo
    async markModuleComplete(moduleId, score) {
        try{
            const fd=new FormData(); fd.append('score', score);
            await fetch(`/modules/${moduleId}/complete`,{method:'POST',headers:this.apiHeaders(),body:fd});
            // Emitir certificado automaticamente
            await fetch(`/modules/${moduleId}/certificate`,{method:'POST',headers:this.apiHeaders()});
        }catch(e){ console.error('Erro ao registrar progresso:', e); }
    },

    showQuizOverlay(q) {
        const overlay=document.getElementById('quiz-overlay'); overlay.style.display='flex';
        document.getElementById('q-text-display').textContent=q.text;
        const opts=document.getElementById('q-opts'); opts.innerHTML='';
        ['A','B','C','D'].forEach(l=>{
            const btn=document.createElement('button');
            btn.textContent=`${l})  ${q['option_'+l.toLowerCase()]}`;
            btn.style.cssText='text-align:left;padding:0.8rem 1.1rem;border-radius:10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.15);color:white;cursor:pointer;font-size:0.88rem;font-family:Outfit,sans-serif;transition:all .15s';
            btn.onmouseover=()=>{if(!btn.disabled)btn.style.background='rgba(255,255,255,.12)';};
            btn.onmouseout =()=>{if(!btn.disabled)btn.style.background='rgba(255,255,255,.06)';};
            btn.onclick=()=>{
                if(l===q.correct_option){overlay.style.display='none';const v=document.getElementById('st-video');v.controls=true;v.play();}
                else{btn.style.background='rgba(239,68,68,.2)';btn.style.borderColor='rgba(239,68,68,.45)';btn.style.color='#fca5a5';btn.disabled=true;}
            };
            opts.appendChild(btn);
        });
    },

    // ATUALIZADO: recebe moduleId para registrar conclusão
    startFinalExam(questions, moduleId) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        let current=0, correct=0;
        const renderQ=()=>{
            const q=questions[current];
            body.innerHTML=`
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:1rem">
                    <h3 style="margin:0;color:var(--primary)">Prova Final</h3>
                    <span style="font-size:0.8rem;color:var(--text-dim);background:var(--bg-main);padding:4px 12px;border-radius:20px">${current+1} / ${questions.length}</span>
                </div>
                <div style="background:var(--bg-main);border-radius:10px;padding:1.25rem;margin-bottom:1.25rem;border-left:4px solid var(--primary-light)">
                    <p style="font-weight:600;margin:0;line-height:1.55">${q.text}</p>
                </div>
                <div id="exam-opts" style="display:flex;flex-direction:column;gap:0.5rem"></div>`;
            const opts=document.getElementById('exam-opts');
            ['A','B','C','D'].forEach(l=>{
                const btn=document.createElement('button');
                btn.textContent=`${l})  ${q['option_'+l.toLowerCase()]}`;
                btn.style.cssText='text-align:left;padding:0.8rem 1.1rem;border-radius:10px;background:var(--bg-main);border:1px solid var(--border);cursor:pointer;font-size:0.88rem;font-family:Outfit,sans-serif;transition:all .15s';
                btn.onmouseover=()=>{if(!btn.disabled)btn.style.borderColor='var(--primary-light)';};
                btn.onmouseout =()=>{if(!btn.disabled)btn.style.borderColor='var(--border)';};
                btn.onclick=()=>{
                    opts.querySelectorAll('button').forEach(b=>b.disabled=true);
                    if(l===q.correct_option){btn.style.background='#22c55e18';btn.style.borderColor='#22c55e50';btn.style.color='#16a34a';correct++;}
                    else{btn.style.background='#ef444418';btn.style.borderColor='#ef444450';btn.style.color='#dc2626';opts.querySelectorAll('button').forEach(b=>{if(b.textContent.trim().startsWith(q.correct_option+')')){b.style.background='#22c55e18';b.style.borderColor='#22c55e50';b.style.color='#16a34a';}});}
                    setTimeout(()=>{current++;if(current<questions.length)renderQ();else showResult();},1200);
                };
                opts.appendChild(btn);
            });
        };
        const showResult=()=>{
            const score=Math.round((correct/questions.length)*100), passed=score>=80;
            // Registrar conclusão se aprovado
            if(passed && moduleId) this.markModuleComplete(moduleId, score);
            body.innerHTML=`<div style="text-align:center;padding:1.5rem 0">
                <div style="font-size:3.5rem;margin-bottom:0.75rem">${passed?'🎉':'📚'}</div>
                <h2 style="margin-bottom:0.25rem;color:${passed?'#16a34a':'#f59e0b'}">${passed?'Aprovado!':'Tente novamente'}</h2>
                <p style="font-size:2.5rem;font-weight:800;color:${passed?'#22c55e':'#f59e0b'};margin:0.5rem 0;line-height:1">${score}%</p>
                <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1.5rem">${correct} de ${questions.length} corretas — mínimo 80%</p>
                ${passed?`<p style="color:#16a34a;font-size:0.88rem;margin-bottom:1rem">✓ Progresso salvo!</p>`:''}
                <button class="btn ${passed?'btn-primary':'btn-outline'}" style="padding:0.65rem 2rem" onclick="App.closeModal();App.showStudentModules(${this.currentCourse?.id||0},'${(this.currentCourse?.title||'').replace(/'/g,"\\'")}')">
                    ${passed?'✓ Concluir módulo':'Fechar e rever o conteúdo'}
                </button>
            </div>`;
        };
        renderQ();
    },

    async renderStudentCertificates() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Meus Certificados',backLabel:'Início',backFn:'App.renderStudentDashboard()'})+
            `<div id="certs-wrapper"><div class="loader">Carregando</div></div>`;
        const res=await fetch('/my-certificates',{headers:this.apiHeaders()});
        const certs=res.ok?await res.json():[];
        const wrapper=document.getElementById('certs-wrapper');
        if(!certs.length){
            wrapper.innerHTML=`<div class="empty-state">
                <div class="empty-icon">🏆</div>
                <p>Você ainda não possui certificados.</p>
                <p style="font-size:0.85rem;margin-top:0.5rem">Conclua módulos para ganhar certificados!</p>
                <button class="btn btn-primary" style="margin-top:1rem" onclick="App.renderStudentPaths()">Ver Trilhas →</button>
            </div>`;
            return;
        }
        wrapper.innerHTML=`<div class="grid">` + certs.map(c=>{
            const issued=c.issued_at?new Date(c.issued_at).toLocaleDateString('pt-BR'):'—';
            const expires=c.expires_at?new Date(c.expires_at).toLocaleDateString('pt-BR'):null;
            const expired=c.expires_at&&new Date(c.expires_at)<new Date();
            return `<div class="card" style="display:flex;flex-direction:column;gap:0.75rem">
                <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:1.5rem">🏆</div>
                <div>
                    <h3 style="margin:0 0 0.25rem;font-size:1rem;color:var(--primary)">${c.module_title}</h3>
                    <p style="font-size:0.82rem;color:var(--text-dim);margin:0">Emitido em ${issued}</p>
                    ${expires?`<p style="font-size:0.78rem;margin:0.2rem 0 0;color:${expired?'#ef4444':'var(--text-dim)'}">
                        ${expired?'⚠️ Expirado em':'Válido até'} ${expires}
                    </p>`:'<p style="font-size:0.78rem;color:var(--text-dim);margin:0.2rem 0 0">Sem validade definida</p>'}
                </div>
                ${expired
                    ? `<span style="padding:4px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;color:#ef4444;background:#ef444418;border:1px solid #ef444435;align-self:flex-start">Expirado</span>`
                    : `<span style="padding:4px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;color:#22c55e;background:#22c55e18;border:1px solid #22c55e35;align-self:flex-start">✓ Válido</span>`
                }
            </div>`;
        }).join('') + `</div>`;
    },

    closeModal() {
        const video=document.getElementById('st-video');
        if(video){video.pause();video.src='';}
        document.getElementById('modal-container').classList.add('hidden');
        document.getElementById('modal-body').innerHTML='';
        document.getElementById('modal-body').className='';
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
