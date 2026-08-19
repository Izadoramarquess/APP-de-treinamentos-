/* ════════════════════════════════════════
   AUTH — login, registro, convite, recuperação de senha
════════════════════════════════════════ */
Object.assign(App, {
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
            err.style.display='none';
            if(pass!==pass2){err.textContent='As senhas não coincidem.';err.style.display='block';return;}
            if(pass.length<6){err.textContent='A senha deve ter pelo menos 6 caracteres.';err.style.display='block';return;}
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Salvando...';
            try {
                const fd=new FormData();
                fd.append('token', document.getElementById('reset-token').value);
                fd.append('password', pass);
                fd.append('new_password', pass); // envia os dois por segurança
                const res=await fetch('/auth/reset-password',{method:'POST',body:fd});
                const data=await res.json();
                if(res.ok){
                    alert('Senha redefinida com sucesso! Faça login.');
                    window.location.href='/';
                } else {
                    err.textContent = data.detail || data.message || 'Token inválido ou expirado.';
                    err.style.display='block';
                    btn.disabled=false; btn.textContent='Redefinir senha';
                }
            } catch(e) {
                err.textContent='Erro de conexão. Tente novamente.';
                err.style.display='block';
                btn.disabled=false; btn.textContent='Redefinir senha';
            }
        };
    },

    renderInviteAccept(container, token) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:0.5rem;font-weight:700;color:var(--primary)">Ativar convite</h2>
            <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1rem">Clique abaixo para ativar sua conta na GeoTrilha.</p>
            <div style="padding:0.9rem 1rem;background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;color:#1e40af;font-size:0.85rem;margin-bottom:1.5rem">
                Sua senha temporária de acesso é <strong>Mudar@123*</strong> — você vai trocar por uma senha sua assim que entrar.
            </div>
            <form id="invite-form">
                <input type="hidden" id="i-token" value="${token}">
                <button type="submit" class="btn btn-primary" style="width:100%;padding:0.75rem">Ativar acesso</button>
            </form>`);
        document.getElementById('invite-form').onsubmit = async (e) => {
            e.preventDefault();
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Ativando...';
            const fd=new FormData(); fd.append('token',document.getElementById('i-token').value);
            const res=await fetch('/invite/accept',{method:'POST',body:fd});
            const data=await res.json();
            if(res.ok){alert('Conta ativada! Entre com a senha temporária Mudar@123* — você vai trocar por uma sua em seguida.');window.location.href='/';}
            else{alert(data.detail||'Erro ao ativar.');btn.disabled=false;btn.textContent='Ativar acesso';}
        };
    },

    async renderRegister(container) {
        container.style.maxWidth='100%'; container.style.margin='0'; container.style.padding='0';
        // Endpoint público (sem exigir login) — a pessoa escolhe a própria
        // empresa, já que ninguém está convidando ela nesse fluxo.
        let companies=[];
        try{ const r=await fetch('/companies/public'); if(r.ok) companies=await r.json(); }catch(e){}
        container.innerHTML = this._authWrap(`
            <h2 style="margin-bottom:1.5rem;font-weight:700;font-size:1.35rem;color:var(--primary)">Solicitar acesso</h2>
            <form id="reg-form">
                <div class="form-group"><label>Nome de usuário</label><input type="text" id="r-user" class="form-control" required></div>
                <div class="form-group"><label>Empresa</label>
                    <select id="r-company" class="form-control" required>
                        <option value="" disabled selected>Selecione...</option>
                        ${companies.map(c=>`<option value="${c.id}">${c.name}</option>`).join('')}
                    </select>
                </div>
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
            const payload={username:document.getElementById('r-user').value,email:document.getElementById('r-email').value,password:document.getElementById('r-pass').value,department:document.getElementById('r-dept').value,company_id:parseInt(document.getElementById('r-company').value,10)};
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
            if(p1==='Mudar@123*'){err.textContent='Escolha uma senha diferente da temporária.';err.style.display='block';return;}
            const btn=e.target.querySelector('button'); btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData(); fd.append('new_password',p1);
            const res=await fetch('/auth/change-password',{method:'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){this.user.must_change_password=false;if(closeBtn)closeBtn.style.display='';this.closeModal();this.showDashboard();}
            else{const d=await res.json();err.textContent=d.detail||'Erro ao trocar senha.';err.style.display='block';btn.disabled=false;btn.textContent='Salvar e continuar';}
        };
    },
});
