/* ════════════════════════════════════════
   VISÃO ALUNO — trilhas, cursos, módulos, player, quiz, certificados
════════════════════════════════════════ */
Object.assign(App, {
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
            let done=0, total=0;
            try{
                // Buscar módulos reais do curso
                const modRes=await fetch(`/courses/${c.id}/modules`,{headers:this.apiHeaders()});
                const mods=modRes.ok?await modRes.json():[];
                total=mods.length;
                // Buscar progresso
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
        let moduleCompleted=false; // Flag para evitar duplo registro
        video.ontimeupdate=()=>{
            if(video.paused) return;
            inlineQuizzes.forEach(q=>{
                if(Math.abs(video.currentTime-q.timestamp)<0.5&&!asked.has(q.id)){asked.add(q.id);video.pause();video.controls=false;this.showQuizOverlay(q);}
            });
            if(video.duration>0&&video.currentTime>=video.duration-1){
                if(finalQuizzes.length>0){
                    document.getElementById('final-exam-section').style.display='block';
                } else if(!alreadyDone&&!moduleCompleted){
                    moduleCompleted=true; // Previne chamadas múltiplas
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
                <button class="btn ${passed?'btn-primary':'btn-outline'}" style="padding:0.65rem 2rem" onclick="App._afterExam(${passed},${moduleId})">
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
            const issued=c.issued_at?new Date(c.issued_at).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):'—';
            const expires=c.expires_at?new Date(c.expires_at).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):null;
            const expired=expires&&new Date(c.expires_at)<new Date();
            return `<div class="card" style="display:flex;flex-direction:column;gap:0.75rem">
                <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:1.5rem">🏆</div>
                <div>
                    <h3 style="margin:0 0 0.25rem;font-size:1rem;color:var(--primary)">${c.module_title}</h3>
                    <p style="font-size:0.82rem;color:var(--text-dim);margin:0">Emitido em ${issued}</p>
                    <p style="font-size:0.78rem;margin:0.2rem 0 0;color:${expired?'#ef4444':'var(--text-dim)'}">
                        ${expired?'⚠️ Expirado em':'Válido até'} ${expires}
                    </p>
                </div>
                ${expired
                    ? `<span style="padding:4px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;color:#ef4444;background:#ef444418;border:1px solid #ef444435;align-self:flex-start">Expirado</span>`
                    : `<span style="padding:4px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;color:#22c55e;background:#22c55e18;border:1px solid #22c55e35;align-self:flex-start">✓ Válido</span>`
                }
            </div>`;
        }).join('') + `</div>`;
    },

    _afterExam(passed, moduleId) {
        this.closeModal();
        if (this.currentCourse && this.currentCourse.id) {
            this.showStudentModules(this.currentCourse.id, this.currentCourse.title);
        } else {
            this.renderStudentDashboard();
        }
    },
});
