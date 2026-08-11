/* ════════════════════════════════════════
   DASHBOARDS — telas iniciais de cada papel (admin, liderança, aluno)
════════════════════════════════════════ */
Object.assign(App, {
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
                    <thead><tr><th>Colaborador</th><th>E-mail</th><th>Cargo</th><th>Módulos</th><th>Progresso</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="6" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        try {
            // Usa /team/progress que já filtra por equipe corretamente
            const res=await fetch('/team/progress',{headers:this.apiHeaders()});
            const members=await res.json();
            const tbody=document.querySelector('#team-table tbody'); tbody.innerHTML='';
            if(!members.length){
                tbody.innerHTML='<tr><td colspan="6"><div class="empty-state"><div class="empty-icon">👥</div><p>Nenhum colaborador na equipe ainda.</p></div></td></tr>';
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
                    <td>${this.actionBtn('🎯 Atribuir Trilha',`App.showAssignPathModal(${u.user_id},'${u.username}')`)}</td>
                </tr>`;
            });
        } catch(e) { console.error('Erro ao carregar equipe:', e); }
    },

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

        // Busca o progresso de todas as trilhas em paralelo em vez de uma de cada vez.
        const progDataList = await Promise.all(paths.map(async p => {
            try{
                const pRes=await fetch(`/paths/${p.id}/progress`,{headers:this.apiHeaders()});
                if(pRes.ok) return await pRes.json();
            }catch(e){}
            return {total:0,completed:0,percent:0};
        }));
        grid.innerHTML = paths.map((p,i) => {
            const progData=progDataList[i];
            totalModules+=progData.total;
            totalDone+=progData.completed;
            const pct=progData.percent||0;
            const fillColor=pct===100?'#22c55e':'var(--primary-light)';
            return `<div class="path-card">
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
        }).join('');
        document.getElementById('sd-modules').textContent=totalModules;
        document.getElementById('sd-done').textContent=totalDone;
    },
});
