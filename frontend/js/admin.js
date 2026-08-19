/* ════════════════════════════════════════
   VISÃO ADMIN — usuários, convites, equipes, cursos/módulos, quiz
════════════════════════════════════════ */
Object.assign(App, {
    async renderAdminUsers() {
        this._resetContainerStyles();
        const isSuper = this.user.role === 'super_admin';
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Gestão de Usuários',actionLabel:'+ Convidar Usuário',actionFn:'App.showInviteUserModal()'})+`
            <div style="display:flex;gap:0.75rem;align-items:center;margin-bottom:1rem;flex-wrap:wrap">
                <input type="text" id="u-search" class="form-control" placeholder="🔍 Buscar por nome ou e-mail..." style="max-width:320px">
                <button onclick="App.showBulkImportModal()" style="margin-left:auto;padding:7px 14px;border-radius:8px;font-size:0.85rem;cursor:pointer;background:var(--bg-main);border:1px solid var(--border);color:var(--text-main);font-family:Outfit,sans-serif;font-weight:600">⬆ Importar CSV</button>
            </div>
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="u-table">
                    <thead><tr><th>Usuário</th><th>E-mail</th>${isSuper?'<th>Empresa</th>':''}<th>Depto</th><th>Cargo</th><th>Status</th><th>Ações</th></tr></thead>
                    <tbody><tr><td colspan="${isSuper?7:6}" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        const [res, companies] = await Promise.all([
            fetch('/admin/users',{headers:this.apiHeaders()}),
            isSuper ? this._fetchCompanies() : Promise.resolve([])
        ]);
        const users=await res.json();
        const companyName = id => (companies.find(c=>c.id===id)||{}).name || '—';
        const tbody=document.querySelector('#u-table tbody'); tbody.innerHTML='';
        if(!users.length){tbody.innerHTML=`<tr><td colspan="${isSuper?7:6}"><div class="empty-state"><div class="empty-icon">👥</div><p>Nenhum usuário.</p></div></td></tr>`;return;}
        document.getElementById('u-search').oninput=(e)=>{
            const q=e.target.value.trim().toLowerCase();
            document.querySelectorAll('#u-table tbody tr[data-search]').forEach(tr=>{
                tr.style.display = tr.dataset.search.includes(q) ? '' : 'none';
            });
        };
        users.forEach(u=>{
            tbody.innerHTML+=`<tr data-search="${(u.username+' '+u.email).toLowerCase()}">
                <td><strong>${u.username}</strong></td>
                <td style="font-size:0.82rem;color:var(--text-dim)">${u.email}</td>
                ${isSuper?`<td style="font-size:0.82rem;color:var(--text-dim)">${companyName(u.company_id)}</td>`:''}
                <td style="font-size:0.82rem;color:var(--text-dim)">${u.department||'—'}</td>
                <td style="font-size:0.82rem">${u.role}</td>
                <td>${this.statusBadge(u.status)}</td>
                <td><div style="display:flex;gap:4px;flex-wrap:wrap;padding:4px 0">
                    ${u.status==='pending'?this.actionBtn('✓ Aprovar',`App.changeUserStatus(${u.id},'ativo')`,'success'):''}
                    ${u.status==='pending'?this.actionBtn('✕ Rejeitar',`App.changeUserStatus(${u.id},'rejected')`,'danger'):''}
                    ${this.actionBtn('Cargo',`App.editUserRole(${u.id},'${u.role}',${u.team_id||0})`)}
                    ${this.actionBtn('🎯 Curso',`App.showAssignCourseModal(${u.id},'${u.username.replace(/'/g,"\\'")}')`)}
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
        const companySelect = await this._companySelectHtml('iu-company');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Convidar Novo Usuário</h3>
            <form id="invite-user-form">
                <div class="form-group"><label>Nome de usuário</label><input type="text" id="iu-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail corporativo</label><input type="email" id="iu-email" class="form-control" required></div>
                ${companySelect}
                <div class="form-group"><label>Departamento</label><input type="text" id="iu-dept" class="form-control" required></div>
                <div class="form-group"><label>Cargo</label>
                    <select id="iu-role" class="form-control">
                        <option value="colaborador">Colaborador</option>
                        <option value="lideranca">Liderança</option>
                        <option value="admin">Administrador</option>
                    </select>
                </div>
                <div class="form-group"><label>Equipe</label>
                    <select id="iu-team" class="form-control">
                        <option value="">Sem Equipe (padrão)</option>
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
            fd.append('department',document.getElementById('iu-dept').value);
            fd.append('role',document.getElementById('iu-role').value);
            const tid=document.getElementById('iu-team').value; if(tid) fd.append('team_id',tid);
            const companyEl=document.getElementById('iu-company'); if(companyEl) fd.append('company_id',companyEl.value);
            const res=await fetch('/admin/users/invite',{method:'POST',headers:this.apiHeaders(),body:fd});
            const data=await res.json();
            if(res.ok){this.renderAdminUsers();this.showCopyLinkModal('Convite Gerado ✓','Envie este link para o novo usuário:',data.invite_link);}
            else{alert(data.detail||'Erro ao gerar convite.');btn.disabled=false;btn.textContent='Gerar convite';}
        };
        modal.classList.remove('hidden');
    },

    async showBulkImportModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        const companySelect = await this._companySelectHtml('bi-company');
        const templateCsv='username,email,department,role,team\r\njoao.silva,joao.silva@geobiogas.tech,Operações,usuario,\r\n';
        body.innerHTML=`<h3 style="margin-bottom:0.5rem;color:var(--primary)">Importar Usuários (CSV)</h3>
            <p style="color:var(--text-dim);font-size:0.83rem;margin-bottom:1rem">
                Colunas: <code>username,email,department,role,team</code> — só <code>username</code> e <code>email</code> são obrigatórias.
                <a href="#" id="bi-template-link" style="color:var(--primary-light)">Baixar modelo</a>
            </p>
            <form id="bulk-import-form">
                ${companySelect}
                <div class="form-group"><input type="file" id="bi-file" class="form-control" accept=".csv" required></div>
                <div style="display:flex;gap:0.5rem;margin-top:0.5rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Importar</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>
            <div id="bi-results" style="margin-top:1rem;max-height:260px;overflow-y:auto"></div>`;
        document.getElementById('bi-template-link').onclick=(e)=>{
            e.preventDefault();
            const blob=new Blob(['﻿'+templateCsv], {type:'text/csv;charset=utf-8;'});
            const url=URL.createObjectURL(blob);
            const a=document.createElement('a'); a.href=url; a.download='modelo_importacao_usuarios.csv';
            document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
        };
        document.getElementById('bulk-import-form').onsubmit=async(e)=>{
            e.preventDefault();
            const fileInput=document.getElementById('bi-file');
            if(!fileInput.files[0]) return;
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Importando...';
            const fd=new FormData(); fd.append('file', fileInput.files[0]);
            const companyEl=document.getElementById('bi-company'); if(companyEl) fd.append('company_id',companyEl.value);
            const res=await fetch('/admin/users/bulk-invite',{method:'POST',headers:this.apiHeaders(),body:fd});
            const data=await res.json();
            const resultsEl=document.getElementById('bi-results');
            if(!res.ok){
                resultsEl.innerHTML=`<p style="color:#ef4444;font-size:0.85rem">${data.detail||'Erro ao importar.'}</p>`;
                btn.disabled=false; btn.textContent='Importar';
                return;
            }
            resultsEl.innerHTML=`<p style="font-weight:600;margin-bottom:0.5rem">${data.created} criado(s), ${data.errors} erro(s) de ${data.total} linha(s)</p>` +
                data.results.map(r=>`<div style="padding:5px 8px;border-radius:6px;font-size:0.78rem;margin-bottom:3px;background:${r.status==='ok'?'#22c55e18':'#ef444418'};color:${r.status==='ok'?'#16a34a':'#dc2626'}">
                    Linha ${r.line} — ${r.email}: ${r.status==='ok'?'✓ convite criado':'✗ '+r.detail}
                </div>`).join('');
            btn.textContent='Importar novamente'; btn.disabled=false;
            if(data.created>0) this.renderAdminUsers();
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
                        <option value="">Sem Equipe (padrão)</option>
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
            const fd=new FormData();
            fd.append('role',document.getElementById('e-role').value);
            fd.append('team_id',document.getElementById('e-team').value);
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
        if(res.ok) this.showCopyLinkModal('Senha Resetada ✓',`A senha de ${username} já virou <strong>Mudar@123*</strong> — pode avisar direto por essa. Se preferir mandar um link em vez disso, aqui está:`,data.reset_link);
        else alert(data.detail||'Erro ao resetar.');
    },

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
            const expira=i.invite_date?new Date(new Date(i.invite_date).getTime()+7*24*60*60*1000).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):'—';
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

    async renderAdminTeams() {
        this._resetContainerStyles();
        const isSuper = this.user.role === 'super_admin';
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Gestão de Equipes',actionLabel:'+ Nova Equipe',actionFn:'App.showCreateTeamModal()'})+`
            <div class="card" style="overflow-x:auto;padding:0">
                <table id="t-table">
                    <thead><tr><th>Nome</th>${isSuper?'<th>Empresa</th>':''}<th>Descrição</th><th>Membros</th></tr></thead>
                    <tbody><tr><td colspan="${isSuper?4:3}" class="loader">Carregando</td></tr></tbody>
                </table>
            </div>`;
        const [res, companies] = await Promise.all([
            fetch('/teams',{headers:this.apiHeaders()}),
            isSuper ? this._fetchCompanies() : Promise.resolve([])
        ]);
        const teams=await res.json();
        const companyName = id => (companies.find(c=>c.id===id)||{}).name || '—';
        const tbody=document.querySelector('#t-table tbody'); tbody.innerHTML='';
        if(!teams.length){tbody.innerHTML=`<tr><td colspan="${isSuper?4:3}"><div class="empty-state"><div class="empty-icon">🏢</div><p>Nenhuma equipe criada.</p></div></td></tr>`;return;}
        teams.forEach(t=>{
            const members=t.members||[];
            tbody.innerHTML+=`<tr>
                <td style="vertical-align:top"><strong>${t.name}</strong></td>
                ${isSuper?`<td style="font-size:0.82rem;color:var(--text-dim);vertical-align:top">${companyName(t.company_id)}</td>`:''}
                <td style="font-size:0.85rem;color:var(--text-dim);vertical-align:top">${t.description||'—'}</td>
                <td style="font-size:0.85rem">
                    <div style="font-weight:600;margin-bottom:${members.length?'6px':'0'}">${members.length} membro${members.length!==1?'s':''}</div>
                    ${members.length?`<div style="display:flex;flex-wrap:wrap;gap:4px">${members.map(m=>`<span title="${m.email}" style="padding:2px 9px;background:var(--bg-main);border:1px solid var(--border);border-radius:20px;font-size:0.75rem;white-space:nowrap">${m.username}${m.role==='lideranca'?' 👑':''}</span>`).join('')}</div>`:''}
                </td>
            </tr>`;
        });
    },

    async showCreateTeamModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const companySelect = await this._companySelectHtml('t-company');
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
                ${companySelect}
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
            const companyEl=document.getElementById('t-company'); if(companyEl) fd.append('company_id',companyEl.value);
            const res=await fetch('/teams',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){this.closeModal();this.renderAdminTeams();}
            else{alert((await res.json()).detail||'Erro ao criar equipe.');btn.disabled=false;btn.textContent='Criar equipe';}
        };
        modal.classList.remove('hidden');
    },

    /* ════════════════════════════════════════
       CURSOS — nível de topo (sem Trilha por cima)
    ════════════════════════════════════════ */
    async renderAdminCourses() {
        this._resetContainerStyles(); this.currentCourse=null;
        const isSuper = this.user.role === 'super_admin';
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Cursos',actionLabel:'+ Novo Curso',actionFn:'App.showCreateCourseModal()'})+
            `<div style="margin-bottom:1rem"><input type="text" id="c-search" class="form-control" placeholder="🔍 Buscar por título..." style="max-width:320px"></div>
            <div id="courses-wrapper"><div class="loader">Carregando</div></div>`;
        const [res, companies] = await Promise.all([
            fetch('/courses',{headers:this.apiHeaders()}),
            isSuper ? this._fetchCompanies() : Promise.resolve([])
        ]);
        const courses=await res.json();
        const companyName = id => (companies.find(c=>c.id===id)||{}).name || '—';
        const wrapper=document.getElementById('courses-wrapper'); wrapper.innerHTML='';
        if(!courses.length){wrapper.innerHTML='<div class="empty-state"><div class="empty-icon">📖</div><p>Nenhum curso criado ainda.</p></div>';return;}
        document.getElementById('c-search').oninput=(e)=>{
            const q=e.target.value.trim().toLowerCase();
            document.querySelectorAll('#courses-wrapper [data-search]').forEach(el=>{
                el.style.display = el.dataset.search.includes(q) ? '' : 'none';
            });
        };
        courses.forEach(c=>{
            wrapper.innerHTML+=`<div class="card" data-search="${c.title.toLowerCase()}" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="flex:1;min-width:0">
                    <h3 style="margin:0 0 0.2rem;font-size:1rem;color:var(--primary)">${c.title}${c.is_standard_training?' <span style="font-size:0.65rem;font-weight:700;color:var(--primary-light);background:rgba(37,99,235,.1);padding:2px 8px;border-radius:20px;vertical-align:middle">PADRÃO</span>':''}${isSuper?` <span style="font-size:0.7rem;color:var(--text-dim)">· ${companyName(c.company_id)}</span>`:''}</h3>
                    <p style="color:var(--text-dim);font-size:0.83rem;margin:0">${c.description||'Sem descrição.'}</p>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditCourseModal(${c.id},'${c.title.replace(/'/g,"\\'")}','${(c.description||'').replace(/'/g,"\\'")}',${!!c.is_standard_training},${c.validity_months||0})`)}
                    ${this.actionBtn('🗑',`App.deleteCourse(${c.id},'${c.title.replace(/'/g,"\\'")}')`, 'danger')}
                    ${this.actionBtn('Módulos →',`App.renderAdminModules(${c.id},'${c.title.replace(/'/g,"\\'")}')`, 'primary')}
                </div>
            </div>`;
        });
    },

    async _courseModal(id, title, desc, is_std, valMonths, isEdit) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const companySelect = isEdit ? '' : await this._companySelectHtml('c-company');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">${isEdit?'Editar':'Novo'} Curso</h3>
            <form id="cform">
                <div class="form-group"><label>Título</label><input type="text" id="c-title" class="form-control" value="${title||''}" required></div>
                ${companySelect}
                <div class="form-group"><label>Descrição</label><textarea id="c-desc" class="form-control" rows="3">${desc||''}</textarea></div>
                <div class="form-group" style="display:flex;gap:8px;align-items:center">
                    <input type="checkbox" id="c-std" ${is_std?'checked':''} style="width:16px;height:16px;accent-color:var(--primary-light)">
                    <label style="margin:0;font-size:0.88rem">Treinamento obrigatório padronizado</label>
                </div>
                <div class="form-group"><label>Validade do certificado (meses)</label><input type="number" id="c-val" class="form-control" value="${valMonths||''}" placeholder="Padrão: 12"></div>
                <div class="form-group"><label>Template de certificado (opcional)</label><input type="file" id="c-cert" class="form-control" accept="image/*"></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">${isEdit?'Salvar':'Criar'}</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('cform').onsubmit=async(e)=>{
            e.preventDefault(); const fd=new FormData();
            fd.append('title',document.getElementById('c-title').value);
            fd.append('description',document.getElementById('c-desc').value);
            fd.append('is_standard_training',document.getElementById('c-std').checked);
            const val=document.getElementById('c-val').value; if(val) fd.append('validity_months',val);
            const certFile=document.getElementById('c-cert').files[0]; if(certFile) fd.append('certificate_template',certFile);
            const companyEl=document.getElementById('c-company'); if(companyEl) fd.append('company_id',companyEl.value);
            await fetch(isEdit?`/courses/${id}`:'/courses',{method:isEdit?'PUT':'POST',headers:this.apiHeaders(),body:fd});
            this.closeModal(); this.renderAdminCourses();
        };
        modal.classList.remove('hidden');
    },
    showCreateCourseModal()                            { this._courseModal(null,'','',false,null,false); },
    showEditCourseModal(id,title,desc,is_std,valMonths) { this._courseModal(id,title,desc,is_std,valMonths,true); },
    async deleteCourse(id, title) {
        if(!confirm(`Excluir o curso "${title}"?\nTodos os módulos serão removidos.`)) return;
        await fetch(`/courses/${id}`,{method:'DELETE',headers:this.apiHeaders()});
        this.renderAdminCourses();
    },

    async renderAdminModules(courseId, courseTitle) {
        this._resetContainerStyles(); this.currentCourse={id:courseId,title:courseTitle};
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:`Módulos — ${courseTitle}`,
            backLabel:'Cursos',backFn:'App.renderAdminCourses()',
            actionLabel:'+ Novo Módulo',actionFn:`App.showModuleUpload(${courseId},'${courseTitle.replace(/'/g,"\\'")}')`,
            breadcrumbs:[{label:'Cursos',fn:'App.renderAdminCourses()'},{label:courseTitle}]
        })+`
        <div id="modules-wrapper"><div class="loader">Carregando</div></div>
        <div class="card hidden" id="module-upload-card" style="margin-top:2rem;border-top:3px solid var(--primary-light)">
            <h3 id="module-upload-title" style="margin-bottom:1.5rem;color:var(--primary)">Novo Módulo</h3>
            <form id="module-upload-form">
                <input type="hidden" id="m-course-id">
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem">
                    <div>
                        <div class="form-group"><label>Título (opcional)</label><input type="text" id="m-title" class="form-control" placeholder="Em branco vira &quot;Módulo N&quot;"></div>
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
                    ${m.video_url?this.actionBtn('▶ Testar vídeo',`App.previewModuleVideo('${m.video_url}','${m.title.replace(/'/g,"\\'")}')`,'primary'):'<span style="font-size:0.75rem;color:#ef4444">sem vídeo</span>'}
                    ${this.actionBtn('✏️',`App.showEditModuleModal(${m.id},'${m.title.replace(/'/g,"\\'")}','${(m.description||'').replace(/'/g,"\\'")}',${m.order||1})`)}
                    ${this.actionBtn('🗑',`App.deleteModule(${m.id},'${m.title.replace(/'/g,"\\'")}',${courseId})`,'danger')}
                    ${this.actionBtn('🎮 Quiz',`App.openQuizEditor(${m.id},'${m.video_url}')`)}
                </div>
            </div>`;
        });
        this.bindModuleForm();
    },

    showEditModuleModal(id, title, desc, order) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:0.5rem;color:var(--primary)">Editar Módulo</h3>
            <form id="emod-form">
                <div class="form-group"><label>Título (opcional)</label><input type="text" id="em-title" class="form-control" value="${title}" placeholder="Em branco vira &quot;Módulo N&quot;"></div>
                <div class="form-group"><label>Descrição</label><textarea id="em-desc" class="form-control" rows="3">${desc}</textarea></div>
                <div class="form-group"><label>Ordem</label><input type="number" id="em-order" class="form-control" value="${order}"></div>
                <div class="form-group"><label>Trocar vídeo (opcional)</label><input type="file" id="em-video" class="form-control" accept="video/*">
                    <small style="color:var(--text-dim);font-size:0.76rem">Deixe em branco pra manter o vídeo atual. Enviando um novo, ele substitui o de agora — quiz e progresso dos alunos nesse módulo continuam intactos.</small>
                </div>
                <div class="progress-track" id="em-prog-wrap" style="display:none;margin-top:0.5rem"><div class="progress-fill" id="em-prog-bar" style="width:0%"></div></div>
                <p id="em-status" style="font-size:0.83rem;color:var(--text-dim);text-align:center;margin-top:0.4rem;min-height:1.2em"></p>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" id="btn-save-module" class="btn btn-primary" style="flex:1">Salvar</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('emod-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=document.getElementById('btn-save-module'), status=document.getElementById('em-status');
            const file=document.getElementById('em-video').files[0];
            btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData();
            fd.append('title',document.getElementById('em-title').value);
            fd.append('description',document.getElementById('em-desc').value);
            fd.append('order',document.getElementById('em-order').value);
            try{
                if(file){
                    document.getElementById('em-prog-wrap').style.display='block';
                    status.textContent='Enviando vídeo novo...';
                    status.style.color='';
                    const initRes=await fetch('/modules/upload/init?filename='+encodeURIComponent(file.name),{method:'POST',headers:this.apiHeaders()});
                    if(!initRes.ok) throw new Error(await this._errorDetail(initRes,'Não foi possível iniciar o upload.'));
                    const{upload_id}=await initRes.json();
                    const chunkSize=5*1024*1024, totalChunks=Math.ceil(file.size/chunkSize);
                    for(let i=0;i<totalChunks;i++){
                        const chunk=file.slice(i*chunkSize,Math.min((i+1)*chunkSize,file.size));
                        const cfd=new FormData(); cfd.append('upload_id',upload_id); cfd.append('filename',file.name); cfd.append('chunk_index',i); cfd.append('chunk',chunk);
                        const chunkRes=await fetch('/modules/upload/chunk',{method:'POST',headers:this.apiHeaders(),body:cfd});
                        if(!chunkRes.ok) throw new Error(await this._errorDetail(chunkRes,'Falha ao enviar parte do vídeo.'));
                        const pct=Math.round(((i+1)/totalChunks)*100);
                        document.getElementById('em-prog-bar').style.width=pct+'%';
                        status.textContent=`Enviando vídeo novo... ${pct}%`;
                    }
                    fd.append('upload_id',upload_id); fd.append('filename',file.name);
                    status.textContent='Finalizando...';
                }
                const saveRes=await fetch(`/modules/${id}`,{method:'PUT',headers:this.apiHeaders(),body:fd});
                if(!saveRes.ok) throw new Error(await this._errorDetail(saveRes,'Não foi possível salvar o módulo.'));
                const saved=await saveRes.json();
                if(file && !saved.video_url) throw new Error('O módulo foi salvo, mas o vídeo novo não chegou a ser gravado. Tente enviar de novo.');
                this.closeModal(); this.renderAdminModules(this.currentCourse.id,this.currentCourse.title);
            }catch(err){
                status.textContent='⚠️ '+(err.message||'Erro ao salvar. Tente novamente.');
                status.style.color='#ef4444';
                btn.disabled=false; btn.textContent='Salvar';
            }
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

    // Extrai a mensagem de erro do backend (ou um texto genérico) de uma
    // resposta não-2xx — usado em todo upload em pedaços, pra nunca deixar
    // um chunk falhar em silêncio e o módulo terminar sem vídeo nenhum.
    async _errorDetail(res, fallback) {
        try{ const d=await res.json(); return d.detail || fallback; }catch(e){ return fallback; }
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
            status.style.color='';
            try{
                const initRes=await fetch('/modules/upload/init?filename='+encodeURIComponent(file.name),{method:'POST',headers:this.apiHeaders()});
                if(!initRes.ok) throw new Error(await this._errorDetail(initRes,'Não foi possível iniciar o upload.'));
                const{upload_id}=await initRes.json();
                const chunkSize=5*1024*1024, totalChunks=Math.ceil(file.size/chunkSize);
                for(let i=0;i<totalChunks;i++){
                    const chunk=file.slice(i*chunkSize,Math.min((i+1)*chunkSize,file.size));
                    const fd=new FormData(); fd.append('upload_id',upload_id); fd.append('filename',file.name); fd.append('chunk_index',i); fd.append('chunk',chunk);
                    const chunkRes=await fetch('/modules/upload/chunk',{method:'POST',headers:this.apiHeaders(),body:fd});
                    // Sem checar isso, um chunk rejeitado (ex.: estourou o limite de
                    // tamanho, e o servidor já apagou o arquivo temporário) passava
                    // batido — a barra ia até 100% e o módulo era criado sem vídeo.
                    if(!chunkRes.ok) throw new Error(await this._errorDetail(chunkRes,'Falha ao enviar parte do vídeo.'));
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
                const finalRes=await fetch(`/courses/${courseId}/modules`,{method:'POST',headers:this.apiHeaders(),body:finalFd});
                if(!finalRes.ok) throw new Error(await this._errorDetail(finalRes,'Não foi possível criar o módulo.'));
                const created=await finalRes.json();
                if(!created.video_url) throw new Error('O módulo foi criado, mas o vídeo não chegou a ser salvo. Edite o módulo e tente enviar de novo.');
                status.textContent='✓ Upload concluído!';
                setTimeout(()=>this.renderAdminModules(courseId,this.currentCourse.title),1000);
            }catch(err){
                status.textContent='⚠️ '+(err.message||'Erro no upload. Tente novamente.');
                status.style.color='#ef4444';
                btn.disabled=false; btn.textContent='Fazer upload';
            }
        };
    },

    // Deixa o admin conferir se o vídeo enviado realmente toca no navegador
    // — sem isso, um upload com problema (codec incompatível, arquivo
    // incompleto) só é descoberto quando um aluno reclamar dias depois.
    previewModuleVideo(videoUrl, title) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        modal.classList.remove('hidden');
        body.className='modal-player';
        body.innerHTML=`
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.75rem">
                <h3 style="margin:0;font-size:1rem;color:white;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:80%">🔍 Testando: ${title}</h3>
                <button onclick="App.closeModal()" style="background:rgba(255,255,255,.12);border:none;cursor:pointer;width:30px;height:30px;border-radius:50%;color:white;font-size:1.1rem;display:flex;align-items:center;justify-content:center;flex-shrink:0">×</button>
            </div>
            <video id="preview-video" src="${videoUrl}" controls autoplay style="width:100%;display:block;max-height:68vh;background:#000;border-radius:10px"></video>
            <p id="preview-status" style="color:rgba(255,255,255,.6);font-size:0.82rem;text-align:center;margin-top:0.75rem">Carregando vídeo...</p>`;
        const video=document.getElementById('preview-video'), status=document.getElementById('preview-status');
        video.onloadeddata=()=>{ status.textContent='✓ Vídeo carregou e está tocando normalmente.'; status.style.color='#86efac'; };
        video.onerror=()=>{ status.textContent='⚠️ O navegador não conseguiu tocar esse vídeo — provavelmente o formato/codec não é compatível (ex.: .mkv ou .mov com codec incomum). Reenvie em .mp4 (H.264).'; status.style.color='#fca5a5'; };
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
});
