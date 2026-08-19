/* ════════════════════════════════════════
   VISÃO SUPER_ADMIN — gestão de empresas (multi-tenant)
════════════════════════════════════════ */
Object.assign(App, {
    async renderCompanies() {
        this._resetContainerStyles();
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Empresas',actionLabel:'+ Nova Empresa',actionFn:'App.showCreateCompanyModal()'})+
            `<div id="companies-wrapper"><div class="loader">Carregando</div></div>`;
        const res=await fetch('/companies',{headers:this.apiHeaders()});
        const companies=res.ok?await res.json():[];
        const wrapper=document.getElementById('companies-wrapper'); wrapper.innerHTML='';
        if(!companies.length){wrapper.innerHTML='<div class="empty-state"><div class="empty-icon">🏢</div><p>Nenhuma empresa cadastrada ainda.</p></div>';return;}
        companies.forEach(c=>{
            wrapper.innerHTML+=`<div class="card" style="margin-bottom:0.75rem;display:flex;justify-content:space-between;align-items:center;gap:1rem">
                <div style="display:flex;align-items:center;gap:1rem;flex:1;min-width:0">
                    ${c.logo_url
                        ? `<img src="${c.logo_url}" alt="${c.name}" style="height:40px;max-width:100px;object-fit:contain">`
                        : `<div style="width:40px;height:40px;border-radius:8px;background:var(--bg-main);display:flex;align-items:center;justify-content:center;font-size:1.1rem;color:var(--text-dim)">🏢</div>`
                    }
                    <h3 style="margin:0;font-size:1rem;color:var(--primary)">${c.name}</h3>
                </div>
                <div style="display:flex;gap:6px;flex-shrink:0">
                    ${this.actionBtn('✏️ Editar',`App.showEditCompanyModal(${c.id},'${c.name.replace(/'/g,"\\'")}')`, 'primary')}
                </div>
            </div>`;
        });
    },

    _companyModal(id, name, isEdit) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        body.className='';
        body.innerHTML=`<h3 style="margin-bottom:1rem;color:var(--primary)">${isEdit?'Editar':'Nova'} Empresa</h3>
            <form id="company-form">
                <div class="form-group"><label>Nome</label><input type="text" id="co-name" class="form-control" value="${name||''}" required></div>
                <div class="form-group"><label>Logo${isEdit?' (deixe em branco pra manter a atual)':' (opcional)'}</label><input type="file" id="co-logo" class="form-control" accept="image/*"></div>
                <div style="display:flex;gap:0.5rem;margin-top:1rem">
                    <button type="submit" class="btn btn-primary" style="flex:1">${isEdit?'Salvar':'Criar'}</button>
                    <button type="button" class="btn btn-secondary" style="flex:1" onclick="App.closeModal()">Cancelar</button>
                </div>
            </form>`;
        document.getElementById('company-form').onsubmit=async(e)=>{
            e.preventDefault();
            const btn=e.target.querySelector('button[type="submit"]'); btn.disabled=true; btn.textContent='Salvando...';
            const fd=new FormData();
            fd.append('name',document.getElementById('co-name').value);
            const logoFile=document.getElementById('co-logo').files[0]; if(logoFile) fd.append('logo',logoFile);
            const res=await fetch(isEdit?`/companies/${id}`:'/companies',{method:isEdit?'PUT':'POST',headers:this.apiHeaders(),body:fd});
            if(res.ok){this.closeModal();this.renderCompanies();}
            else{alert((await res.json()).detail||'Erro ao salvar empresa.');btn.disabled=false;btn.textContent='Salvar';}
        };
        modal.classList.remove('hidden');
    },
    showCreateCompanyModal()       { this._companyModal(null,'',false); },
    showEditCompanyModal(id,name)  { this._companyModal(id,name,true); },

    // Cache simples pra não refazer o fetch toda hora que um seletor de
    // empresa aparece em algum modal — a lista muda raramente.
    async _fetchCompanies() {
        if (this._companiesCache) return this._companiesCache;
        const res = await fetch('/companies', {headers: this.apiHeaders()});
        this._companiesCache = res.ok ? await res.json() : [];
        return this._companiesCache;
    },

    // <select> de empresa reutilizado nos modais de convite/equipe/curso —
    // só super_admin vê isso (admin comum já tem a empresa implícita).
    async _companySelectHtml(selectId) {
        if (this.user.role !== 'super_admin') return '';
        const companies = await this._fetchCompanies();
        return `<div class="form-group"><label>Empresa</label>
            <select id="${selectId}" class="form-control" required>
                ${companies.map(c=>`<option value="${c.id}">${c.name}</option>`).join('')}
            </select></div>`;
    },
});
