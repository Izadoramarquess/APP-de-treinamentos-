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
