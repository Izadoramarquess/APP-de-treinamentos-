/* ════════════════════════════════════════
   DASHBOARDS — telas iniciais de cada papel (admin, liderança, aluno)
════════════════════════════════════════ */
Object.assign(App, {
    // Usado tanto pela tela de Progresso do admin quanto por Minha Equipe
    // (liderança) — ambas consomem o mesmo courses[] de /team/progress.
    _progressCoursesDetailHtml(courses) {
        if(!courses || !courses.length) return `<p style="margin:0;color:var(--text-dim);font-size:0.82rem">Nenhum curso matriculado.</p>`;
        return `<table style="width:100%;font-size:0.8rem;border-collapse:collapse">
            <thead><tr style="color:var(--text-dim);text-align:left">
                <th style="padding:4px 8px;font-weight:600">Curso</th>
                <th style="padding:4px 8px;font-weight:600">Progresso</th>
                <th style="padding:4px 8px;font-weight:600">Certificado</th>
            </tr></thead>
            <tbody>
            ${courses.map(c=>{
                const pct=c.percent||0;
                const barColor=pct===100?'#22c55e':pct>=50?'var(--primary-light)':'#f59e0b';
                const certHtml = c.certificate_issued
                    ? `<span style="color:#16a34a;font-weight:600">✓ Emitido${c.certificate_expires_at?' · até '+new Date(c.certificate_expires_at).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):''}</span>`
                    : `<span style="color:var(--text-dim)">—</span>`;
                return `<tr>
                    <td style="padding:4px 8px">${c.course_title}</td>
                    <td style="padding:4px 8px;min-width:140px">
                        <div style="display:flex;align-items:center;gap:0.5rem">
                            <div class="progress-track" style="flex:1;height:5px"><div class="progress-fill" style="width:${pct}%;background:${barColor}"></div></div>
                            <span style="font-weight:700;color:${barColor};width:30px;text-align:right">${pct}%</span>
                        </div>
                    </td>
                    <td style="padding:4px 8px">${certHtml}</td>
                </tr>`;
            }).join('')}
            </tbody>
        </table>`;
    },

    _toggleProgressDetail(rowId) {
        const row = document.getElementById(rowId);
        if(row) row.classList.toggle('hidden');
    },

    async renderAdminProgress() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Progresso'})+`
            <div class="card" style="margin-bottom:1rem;display:flex;align-items:center;gap:0.75rem;flex-wrap:wrap">
                <label style="font-size:0.85rem;color:var(--text-dim);font-weight:600">Equipe:</label>
                <select id="prog-team-filter" class="form-control" style="max-width:260px;width:auto">
                    <option value="">Todas as equipes</option>
                </select>
            </div>
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="progress-table">
                    <thead><tr><th>Pessoa</th><th>E-mail</th><th>Equipe</th><th>Cargo</th><th>Progresso Geral</th><th>Cursos</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;

        let allMembers = [];
        try {
            const res = await fetch('/team/progress', {headers:this.apiHeaders()});
            allMembers = res.ok ? await res.json() : [];
        } catch(e) { console.error('Erro ao carregar progresso:', e); }

        const filterSel = document.getElementById('prog-team-filter');
        const teamsSeen = new Map();
        allMembers.forEach(m=>{ if(m.team_id!=null) teamsSeen.set(m.team_id, m.team_name); });
        [...teamsSeen.entries()].sort((a,b)=>(a[1]||'').localeCompare(b[1]||'')).forEach(([id,name])=>{
            filterSel.innerHTML += `<option value="${id}">${name}</option>`;
        });

        const renderRows = (teamId) => {
            const tbody=document.querySelector('#progress-table tbody'); tbody.innerHTML='';
            const filtered = teamId ? allMembers.filter(m=>String(m.team_id)===String(teamId)) : allMembers;
            if(!filtered.length){
                tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">📊</div><p>Nenhuma pessoa encontrada.</p></div></td></tr>';
                return;
            }
            filtered.forEach(u=>{
                const pct=u.percent||0;
                const barColor=pct===100?'#22c55e':pct>=50?'var(--primary-light)':'#f59e0b';
                tbody.innerHTML+=`<tr>
                    <td><strong>${u.username}</strong></td>
                    <td style="font-size:0.82rem;color:var(--text-dim)">${u.email}</td>
                    <td style="font-size:0.82rem">${u.team_name||'—'}</td>
                    <td style="font-size:0.82rem">${u.role}</td>
                    <td style="min-width:140px">
                        <div style="display:flex;align-items:center;gap:0.5rem">
                            <div class="progress-track" style="flex:1;height:6px"><div class="progress-fill" style="width:${pct}%;background:${barColor}"></div></div>
                            <span style="font-size:0.75rem;font-weight:700;color:${barColor};width:32px;text-align:right">${pct}%</span>
                        </div>
                    </td>
                    <td>${this.actionBtn(`Cursos (${u.enrollments})`,`App._toggleProgressDetail('ap-row-${u.user_id}')`)}</td>
                </tr>
                <tr id="ap-row-${u.user_id}" class="hidden"><td colspan="6" style="background:var(--bg-main);padding:0.75rem 1rem">${this._progressCoursesDetailHtml(u.courses)}</td></tr>`;
            });
        };
        renderRows('');
        filterSel.onchange = () => renderRows(filterSel.value);
    },

    async renderAdminDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Dashboard'})+`
            <div class="grid-stats" id="stats-grid">
                <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-info"><div class="stat-value" id="s-users">—</div><div class="stat-label">Usuários Ativos</div></div></div>
                <div class="stat-card"><div class="stat-icon">📚</div><div class="stat-info"><div class="stat-value" id="s-courses">—</div><div class="stat-label">Cursos</div></div></div>
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
            document.getElementById('s-courses').textContent    = stats.total_courses    ?? '—';
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

    async renderLeaderDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Minha Equipe',actionLabel:'+ Convidar Colaborador',actionFn:'App.showInviteUserModal()'})+`
            <div class="grid-stats" id="team-stats" style="margin-bottom:1.5rem">
                <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-info"><div class="stat-value" id="ts-members">—</div><div class="stat-label">Membros Ativos</div></div></div>
                <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info"><div class="stat-value" id="ts-done">—</div><div class="stat-label">Módulos Concluídos</div></div></div>
                <div class="stat-card"><div class="stat-icon">📊</div><div class="stat-info"><div class="stat-value" id="ts-pct">—</div><div class="stat-label">Progresso Médio</div></div></div>
            </div>
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="team-table">
                    <thead><tr><th>Colaborador</th><th>E-mail</th><th>Cargo</th><th>Módulos</th><th>Progresso</th><th>Cursos</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="7" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        try {
            // Usa /team/progress que já filtra por equipe corretamente
            const res=await fetch('/team/progress',{headers:this.apiHeaders()});
            const members=await res.json();
            const tbody=document.querySelector('#team-table tbody'); tbody.innerHTML='';
            if(!members.length){
                tbody.innerHTML='<tr><td colspan="7"><div class="empty-state"><div class="empty-icon">👥</div><p>Nenhum colaborador na equipe ainda.</p></div></td></tr>';
                ['ts-members','ts-done','ts-pct'].forEach(id=>document.getElementById(id).textContent='0');
                return;
            }
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
                            <span style="font-size:0.75rem;font-weight:700;color:${barColor};width:32px;text-align:right">${pct}%</span>
                        </div>
                    </td>
                    <td>${this.actionBtn(`Cursos (${u.enrollments})`,`App._toggleProgressDetail('lp-row-${u.user_id}')`)}</td>
                    <td>${this.actionBtn('🎯 Atribuir Curso',`App.showAssignCourseModal(${u.user_id},'${u.username}')`)}</td>
                </tr>
                <tr id="lp-row-${u.user_id}" class="hidden"><td colspan="7" style="background:var(--bg-main);padding:0.75rem 1rem">${this._progressCoursesDetailHtml(u.courses)}</td></tr>`;
            });
        } catch(e) { console.error('Erro ao carregar equipe:', e); }
    },

    async renderStudentDashboard() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:`Olá, ${this.user.username}! 👋`})+`
            <div class="grid-stats">
                <div class="stat-card"><div class="stat-icon">📚</div><div class="stat-info"><div class="stat-value" id="sd-courses">—</div><div class="stat-label">Cursos Matriculados</div></div></div>
                <div class="stat-card"><div class="stat-icon">🎬</div><div class="stat-info"><div class="stat-value" id="sd-modules">—</div><div class="stat-label">Total de Módulos</div></div></div>
                <div class="stat-card"><div class="stat-icon">✅</div><div class="stat-info"><div class="stat-value" id="sd-done">—</div><div class="stat-label">Módulos Concluídos</div></div></div>
                <div class="stat-card"><div class="stat-icon">🏆</div><div class="stat-info"><div class="stat-value" id="sd-certs">—</div><div class="stat-label">Certificados</div></div></div>
            </div>
            <h3 style="margin-bottom:1rem;color:var(--primary);font-size:1.1rem">Meus Cursos</h3>
            <div class="grid" id="dash-courses"><div class="loader">Carregando</div></div>`;

        const [coursesRes, certsRes] = await Promise.all([
            fetch('/my-courses', {headers:this.apiHeaders()}),
            fetch('/my-certificates', {headers:this.apiHeaders()})
        ]);
        const courses = coursesRes.ok ? await coursesRes.json() : [];
        const certs = certsRes.ok ? await certsRes.json() : [];

        document.getElementById('sd-courses').textContent=courses.length;
        document.getElementById('sd-certs').textContent=certs.length;

        let totalModules=0, totalDone=0;
        const grid=document.getElementById('dash-courses'); grid.innerHTML='';

        if(!courses.length){
            grid.innerHTML=`<div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">📚</div>
                <p>Você ainda não está matriculado em nenhum curso.</p>
                <p style="font-size:0.85rem;margin-top:0.5rem">Entre em contato com seu líder ou administrador.</p>
            </div>`;
            document.getElementById('sd-modules').textContent='0';
            document.getElementById('sd-done').textContent='0';
            return;
        }

        // Busca o progresso de todos os cursos em paralelo em vez de um de cada vez.
        const progDataList = await Promise.all(courses.map(async c => {
            try{
                const pRes=await fetch(`/courses/${c.id}/progress-summary`,{headers:this.apiHeaders()});
                if(pRes.ok) return await pRes.json();
            }catch(e){}
            return {total:0,completed:0,percent:0};
        }));
        grid.innerHTML = courses.map((c,i) => {
            const progData=progDataList[i];
            totalModules+=progData.total;
            totalDone+=progData.completed;
            const pct=progData.percent||0;
            const fillColor=pct===100?'#22c55e':'var(--primary-light)';
            return `<div class="path-card">
                <div class="path-icon">📚</div>
                <h3 style="margin:0 0 0.4rem;font-size:1rem;color:var(--primary)">${c.title}</h3>
                <p style="color:var(--text-dim);font-size:0.85rem;flex:1;margin:0 0 1rem;line-height:1.5">${c.description||''}</p>
                <div style="margin-bottom:0.75rem">
                    <div style="display:flex;justify-content:space-between;font-size:0.78rem;color:var(--text-dim);margin-bottom:0.3rem">
                        <span>${progData.completed} de ${progData.total} módulos</span>
                        <span style="font-weight:700;color:${fillColor}">${pct}%</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" style="width:${pct}%;background:${fillColor}"></div></div>
                </div>
                <button class="btn btn-primary" style="width:100%" onclick="App.showStudentModules(${c.id},'${c.title.replace(/'/g,"\\'")}')">
                    ${pct===100?'✓ Concluído — Revisar':'Continuar →'}
                </button>
            </div>`;
        }).join('');
        document.getElementById('sd-modules').textContent=totalModules;
        document.getElementById('sd-done').textContent=totalDone;
    },
});
