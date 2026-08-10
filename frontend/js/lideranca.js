/* ════════════════════════════════════════
   VISÃO LIDERANÇA — gestão da equipe
════════════════════════════════════════ */
Object.assign(App, {
    showAddMemberModal() {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">Novo Colaborador</h3>
            <form id="add-member-form">
                <div class="form-group"><label>Usuário</label><input type="text" id="m-user" class="form-control" required></div>
                <div class="form-group"><label>E-mail</label><input type="email" id="m-email" class="form-control" required></div>
                <div class="form-group"><label>Departamento</label><input type="text" id="m-dept" class="form-control" required></div>
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
            // Time é atribuído automaticamente pelo backend (equipe do próprio líder).
            const res=await fetch('/admin/users/invite',{method:'POST',headers:this.apiHeaders(),body:fd});
            const data=await res.json();
            if(res.ok){this.closeModal();this.renderLeaderDashboard();this.showCopyLinkModal('Convite Gerado ✓','Envie este link para o novo colaborador:',data.invite_link);}
            else{alert(data.detail||'Erro ao gerar convite.');btn.disabled=false;btn.textContent='Gerar convite';}
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
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Atribuindo...';
            const fd=new FormData();
            fd.append('user_id',userId); fd.append('path_id',document.getElementById('a-path').value);
            const res=await fetch('/enrollments',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){
                this.closeModal();
                alert('Trilha atribuída com sucesso!');
                // Recarregar a visão atual
                if(this.user.role==='lideranca') this.renderLeaderDashboard();
                else this.renderAdminUsers();
            } else {
                const d=await res.json();
                alert(d.detail||'Erro ao atribuir trilha.');
                btn.disabled=false; btn.textContent='Atribuir';
            }
        };
        modal.classList.remove('hidden');
    },
});
