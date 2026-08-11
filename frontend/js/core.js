console.log("GeoTrilha LMS carregado.");

/* ════════════════════════════════════════
   NÚCLEO — estado, boot, navegação, helpers de UI
   Estendido pelos demais arquivos via Object.assign(App, {...})
════════════════════════════════════════ */
const App = {
    user: null,
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
                if (this.user.status !== 'ativo') return this.logoutPending();
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
                <a class="nav-link" onclick="App.renderAdminCourses()">Cursos</a>`;
        } else if (role === 'lideranca') {
            navHtml = `
                <a class="nav-link" onclick="App.renderLeaderDashboard()">Minha Equipe</a>
                <a class="nav-link" onclick="App.renderStudentCourses()">Meus Cursos</a>
                <a class="nav-link" onclick="App.renderStudentCertificates()">🏆 Certificados</a>`;
        } else {
            navHtml = `
                <a class="nav-link" onclick="App.renderStudentDashboard()">Início</a>
                <a class="nav-link" onclick="App.renderStudentCourses()">Meus Cursos</a>
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

    logout()        { localStorage.removeItem('token'); this.user=null; this._resetContainerStyles(); this.showView('login'); },
    logoutPending() { alert('Seu cadastro está pendente ou foi rejeitado.'); this.logout(); },

    closeModal() {
        const video=document.getElementById('st-video');
        if(video){video.pause();video.src='';}
        document.getElementById('modal-container').classList.add('hidden');
        document.getElementById('modal-body').innerHTML='';
        document.getElementById('modal-body').className='';
    }
};

document.addEventListener('DOMContentLoaded', () => App.init());
