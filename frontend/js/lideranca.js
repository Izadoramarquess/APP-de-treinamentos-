/* ════════════════════════════════════════
   VISÃO LIDERANÇA — gestão da equipe
════════════════════════════════════════ */
Object.assign(App, {
    async showAddMemberModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const ledIds = this.user.led_team_ids || [];
        // Só mostra o seletor de equipe se o líder lidera mais de uma — no
        // caso comum (uma equipe só), o backend já resolve sozinho.
        let teamSelectHtml = '';
        if(ledIds.length > 1){
            const teamsRes = await fetch('/teams', {headers: this.apiHeaders()});
            const teams = (await teamsRes.json()).filter(t => ledIds.includes(t.id));
            teamSelectHtml = `<div class="form-group"><label>Equipe</label>
                <select id="m-team" class="form-control">
                    ${teams.map(t=>`<option value="${t.id}">${t.name}</option>`).join('')}
                </select>
            </div>`;
        }
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Novo Colaborador</h3>
            <form id="add-member-form">
                <div class="form-group"><label>Usuário</label><input type="text" id="m-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail</label><input type="email" id="m-email" class="form-control" required></div>
                <div class="form-group"><label>Departamento</label><input type="text" id="m-dept" class="form-control" required></div>
                ${teamSelectHtml}
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Gerar convite</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('add-member-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Gerando...';
            const fd=new FormData();
            fd.append('username',document.getElementById('m-user').value);
            fd.append('email',document.getElementById('m-email').value);
            fd.append('department',document.getElementById('m-dept').value);
            // Time é atribuído automaticamente pelo backend quando o líder só
            // lidera uma equipe; com mais de uma, manda a escolhida acima.
            const teamEl=document.getElementById('m-team'); if(teamEl) fd.append('team_id', teamEl.value);
            const res=await fetch('/admin/users/invite',{method:'POST',headers:this.apiHeaders(),body:fd});
            const data=await res.json();
            if(res.ok){this.closeModal();this.renderLeaderDashboard();this.showCopyLinkModal('Convite Gerado ✓','Envie este link para o novo colaborador:',data.invite_link);}
            else{alert(data.detail||'Erro ao gerar convite.');btn.disabled=false;btn.textContent='Gerar convite';}
        };
        modal.classList.remove('hidden');
    },

    async showAssignCourseModal(userId, username) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        const coursesRes=await fetch('/courses',{headers:this.apiHeaders()}); const courses=await coursesRes.json();
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Atribuir Curso — ${username}</h3>
            <form id="assign-form">
                <div class="form-group"><label>Curso</label>
                    <select id="a-course" class="form-control">${courses.map(c=>`<option value="${c.id}">${c.title}</option>`).join('')}</select>
                </div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">Atribuir</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('assign-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Atribuindo...';
            const fd=new FormData();
            fd.append('user_id',userId); fd.append('course_id',document.getElementById('a-course').value);
            const res=await fetch('/enrollments',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){
                this.closeModal();
                alert('Curso atribuído com sucesso!');
                // Recarregar a visão atual
                if(this.user.role==='lideranca') this.renderLeaderDashboard();
                else this.renderAdminUsers();
            } else {
                const d=await res.json();
                alert(d.detail||'Erro ao atribuir curso.');
                btn.disabled=false; btn.textContent='Atribuir';
            }
        };
        modal.classList.remove('hidden');
    },
});
