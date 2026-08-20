/* ════════════════════════════════════════
   VISÃO ALUNO — cursos, módulos, player, quiz, certificados
════════════════════════════════════════ */
Object.assign(App, {
    async renderStudentCourses() {
        this._resetContainerStyles(); this.currentCourse=null;
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({title:'Meus Cursos',backLabel:'Início',backFn:'App.renderStudentDashboard()'})+
            `<div class="grid" id="student-courses"><div class="loader">Carregando</div></div>`;
        const res=await fetch('/my-courses',{headers:this.apiHeaders()});
        const courses=res.ok?await res.json():[];
        const grid=document.getElementById('student-courses'); grid.innerHTML='';
        if(!courses.length){
            grid.innerHTML=`<div class="empty-state" style="grid-column:1/-1">
                <div class="empty-icon">📚</div>
                <p>Você não está matriculado em nenhum curso.</p>
                <p style="font-size:0.85rem;margin-top:0.5rem">Entre em contato com seu líder ou administrador.</p>
            </div>`;
            return;
        }
        // Busca o progresso de todos os cursos em paralelo em vez de um de cada vez.
        const summaries = await Promise.all(courses.map(async c => {
            try{const pr=await fetch(`/courses/${c.id}/progress-summary`,{headers:this.apiHeaders()});if(pr.ok)return await pr.json();}catch(e){}
            return {total:0, completed:0, percent:0};
        }));
        grid.innerHTML = courses.map((c,i) => {
            const {completed,total,percent}=summaries[i];
            const fillColor=percent===100?'#22c55e':'var(--primary-light)';
            const courseStatus = completed===0 ? 'matriculado' : (percent===100 ? 'finalizado' : 'em_andamento');
            const st=this._courseStatusBadge(courseStatus);
            return `<div class="path-card">
                <div class="path-icon" style="background:linear-gradient(135deg,#1e40af,#3b82f6)">🎓</div>
                <span style="align-self:flex-start;padding:2px 9px;border-radius:12px;font-size:0.7rem;font-weight:700;color:${st.color};background:${st.color}18;margin-bottom:0.4rem">${st.label}</span>
                <h3 style="margin:0 0 0.4rem;font-size:1rem;color:var(--primary)">${c.title}</h3>
                <p style="color:var(--text-dim);font-size:0.85rem;flex:1;margin:0 0 0.75rem;line-height:1.5">${c.description||''}</p>
                <div style="margin-bottom:0.75rem">
                    <div style="display:flex;justify-content:space-between;font-size:0.75rem;color:var(--text-dim);margin-bottom:0.3rem">
                        <span>${completed} de ${total} módulos</span><span style="font-weight:700;color:${fillColor}">${percent}%</span>
                    </div>
                    <div class="progress-track"><div class="progress-fill" style="width:${percent}%;background:${fillColor}"></div></div>
                </div>
                <button class="btn btn-primary" style="width:100%" onclick="App.showStudentModules(${c.id},'${c.title.replace(/'/g,"\\'")}')">
                    ${percent===100?'✓ Concluído':'Acessar →'}
                </button>
            </div>`;
        }).join('');
    },

    async showStudentModules(courseId, courseTitle) {
        this._resetContainerStyles(); this.currentCourse={id:courseId,title:courseTitle};
        const container=document.getElementById('app-container');
        container.innerHTML=this.sectionHeader({
            title:courseTitle,
            backLabel:'Meus Cursos',backFn:'App.renderStudentCourses()',
            breadcrumbs:[
                {label:'Início',fn:'App.renderStudentDashboard()'},
                {label:'Meus Cursos',fn:'App.renderStudentCourses()'},
                {label:courseTitle}
            ]
        })+`<div id="student-modules"><div class="loader">Carregando</div></div>`;
        const [modulesRes, progressRes, examRes] = await Promise.all([
            fetch(`/courses/${courseId}/modules`,  {headers:this.apiHeaders()}),
            fetch(`/courses/${courseId}/progress`, {headers:this.apiHeaders()}),
            fetch(`/courses/${courseId}/exam-questions`, {headers:this.apiHeaders()})
        ]);
        const modules  = await modulesRes.json();
        const progress = progressRes.ok ? await progressRes.json() : [];
        const examQuestions = examRes.ok ? await examRes.json() : [];
        const doneIds  = new Set(progress.filter(p=>p.completed).map(p=>p.module_id));
        const allModulesDone = modules.length>0 && modules.every(m=>doneIds.has(m.id));

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

        if(examQuestions.length){
            grid.innerHTML+=`<div class="path-card" style="align-items:center;text-align:center;gap:0.5rem">
                <div style="font-size:1.8rem">📝</div>
                <h4 style="margin:0">Prova Final</h4>
                <p style="color:var(--text-dim);font-size:0.85rem;margin:0">Cobre todos os módulos deste curso.</p>
                ${allModulesDone
                    ? `<button class="btn btn-primary" style="margin-top:0.5rem" onclick="App.startFinalExam(${courseId})">Iniciar Prova Final</button>`
                    : `<span style="font-size:0.8rem;color:var(--text-light);margin-top:0.5rem">🔒 Conclua todos os módulos para liberar</span>`
                }
            </div>`;
        }
    },

    async playModule(moduleId, courseId, alreadyDone=false) {
        const res=await fetch(`/courses/${courseId}/modules`,{headers:this.apiHeaders()}); const modules=await res.json();
        const target=modules.find(m=>m.id===moduleId);
        if(!target) return alert('Módulo não encontrado.');
        const inlineQuizzes=target.questions||[];
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
            ${alreadyDone?'<div style="margin-top:1rem;text-align:center;padding:0.75rem;background:rgba(34,197,94,.15);border-radius:8px;color:#86efac;font-size:0.88rem">✓ Módulo já concluído — você está revisando o conteúdo</div>':''}`;

        const video=document.getElementById('st-video'), asked=new Set();
        let moduleCompleted=false; // Flag para evitar duplo registro
        video.ontimeupdate=()=>{
            if(video.paused) return;
            inlineQuizzes.forEach(q=>{
                if(Math.abs(video.currentTime-q.timestamp)<0.5&&!asked.has(q.id)){asked.add(q.id);video.pause();video.controls=false;this.showQuizOverlay(q);}
            });
            if(video.duration>0&&video.currentTime>=video.duration-1&&!alreadyDone&&!moduleCompleted){
                moduleCompleted=true; // Previne chamadas múltiplas
                this.markModuleComplete(moduleId).then(ok=>{ if(!ok) moduleCompleted=false; });
            }
        };
    },

    // Módulo sem prova final: só "assistiu o vídeo" — sem nota a apurar. A
    // emissão do certificado é automática no backend quando o curso inteiro
    // é concluído — aqui só avisamos o aluno se foi esse o caso.
    async markModuleComplete(moduleId) {
        try{
            const res=await fetch(`/modules/${moduleId}/complete`,{method:'POST',headers:this.apiHeaders()});
            if(!res.ok){
                const data=await res.json().catch(()=>({}));
                this._showToast(data.detail||'Não foi possível concluir o módulo.', '#dc2626');
                return false;
            }
            const data=await res.json();
            if(data.certificate_issued) this._showCertificateToast();
            return true;
        }catch(e){ console.error('Erro ao registrar progresso:', e); return false; }
    },

    _showToast(message, bg='#16a34a') {
        const el=document.createElement('div');
        el.textContent=message;
        el.style.cssText=`position:fixed;bottom:24px;left:50%;transform:translateX(-50%);background:${bg};color:white;padding:0.8rem 1.4rem;border-radius:10px;font-size:0.88rem;font-weight:600;z-index:9999;box-shadow:0 8px 24px rgba(0,0,0,.25);max-width:90vw;text-align:center`;
        document.body.appendChild(el);
        setTimeout(()=>el.remove(),4500);
    },

    _showCertificateToast() {
        this._showToast('🎉 Certificado emitido! Confira em "Meus Certificados".', '#16a34a');
    },

    // A resposta certa nunca vem do servidor para o aluno — cada clique é
    // corrigido no back-end via /questions/{id}/check, que só devolve
    // certo/errado, nunca o gabarito.
    async showQuizOverlay(q) {
        const overlay=document.getElementById('quiz-overlay'); overlay.style.display='flex';
        document.getElementById('q-text-display').textContent=q.text;
        const opts=document.getElementById('q-opts'); opts.innerHTML='';
        ['A','B','C','D'].forEach(l=>{
            const btn=document.createElement('button');
            btn.textContent=`${l})  ${q['option_'+l.toLowerCase()]}`;
            btn.style.cssText='text-align:left;padding:0.8rem 1.1rem;border-radius:10px;background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.15);color:white;cursor:pointer;font-size:0.88rem;font-family:Outfit,sans-serif;transition:all .15s';
            btn.onmouseover=()=>{if(!btn.disabled)btn.style.background='rgba(255,255,255,.12)';};
            btn.onmouseout =()=>{if(!btn.disabled)btn.style.background='rgba(255,255,255,.06)';};
            btn.onclick=async ()=>{
                if(btn.disabled) return;
                const fd=new FormData(); fd.append('selected_option', l);
                const res=await fetch(`/questions/${q.id}/check`,{method:'POST',headers:this.apiHeaders(),body:fd});
                const data=res.ok?await res.json():{correct:false};
                if(data.correct){overlay.style.display='none';const v=document.getElementById('st-video');v.controls=true;v.play();}
                else{btn.style.background='rgba(239,68,68,.2)';btn.style.borderColor='rgba(239,68,68,.45)';btn.style.color='#fca5a5';btn.disabled=true;}
            };
            opts.appendChild(btn);
        });
    },

    // Prova final: cobre o curso inteiro, não um módulo — cada resposta
    // acumula {question_id, selected_option} e só é corrigida de verdade no
    // servidor, todas de uma vez, em /courses/{id}/exam-submit — a nota
    // exibida é sempre a que o servidor calculou, nunca uma contagem feita
    // no navegador.
    async startFinalExam(courseId) {
        const modal=document.getElementById('modal-container'), body=document.getElementById('modal-body');
        modal.classList.remove('hidden');
        body.className='';
        body.innerHTML='<div style="text-align:center;padding:2.5rem 0"><div class="loader">Carregando prova</div></div>';
        const res=await fetch(`/courses/${courseId}/exam-questions`,{headers:this.apiHeaders()});
        const questions=res.ok?await res.json():[];
        if(!questions.length){ body.innerHTML='<p style="text-align:center;color:var(--text-dim)">Não foi possível carregar a prova.</p>'; return; }
        let current=0;
        const answers=[];
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
                btn.onclick=async ()=>{
                    opts.querySelectorAll('button').forEach(b=>b.disabled=true);
                    answers.push({question_id:q.id, selected_option:l});
                    // Feedback visual imediato só da opção clicada — o servidor
                    // não devolve qual era a certa, então não dá pra destacá-la aqui.
                    const fd=new FormData(); fd.append('selected_option', l);
                    const res=await fetch(`/questions/${q.id}/check`,{method:'POST',headers:this.apiHeaders(),body:fd});
                    const data=res.ok?await res.json():{correct:false};
                    if(data.correct){btn.style.background='#22c55e18';btn.style.borderColor='#22c55e50';btn.style.color='#16a34a';}
                    else{btn.style.background='#ef444418';btn.style.borderColor='#ef444450';btn.style.color='#dc2626';}
                    setTimeout(()=>{current++;if(current<questions.length)renderQ();else finish();},1000);
                };
                opts.appendChild(btn);
            });
        };
        const finish=async ()=>{
            body.innerHTML=`<div style="text-align:center;padding:2.5rem 0"><div class="loader">Corrigindo prova</div></div>`;
            let result={score:0,passed:false,correct_count:0,total:questions.length,certificate_issued:false};
            try{
                const res=await fetch(`/courses/${courseId}/exam-submit`,{method:'POST',headers:this.apiJsonHeaders(),body:JSON.stringify(answers)});
                if(res.ok) result=await res.json();
            }catch(e){}
            if(result.certificate_issued) this._showCertificateToast();
            showResult(result);
        };
        const showResult=({score,passed,correct_count,total})=>{
            body.innerHTML=`<div style="text-align:center;padding:1.5rem 0">
                <div style="font-size:3.5rem;margin-bottom:0.75rem">${passed?'🎉':'📚'}</div>
                <h2 style="margin-bottom:0.25rem;color:${passed?'#16a34a':'#f59e0b'}">${passed?'Aprovado!':'Tente novamente'}</h2>
                <p style="font-size:2.5rem;font-weight:800;color:${passed?'#22c55e':'#f59e0b'};margin:0.5rem 0;line-height:1">${score}%</p>
                <p style="color:var(--text-dim);font-size:0.88rem;margin-bottom:1.5rem">${correct_count} de ${total} corretas — mínimo 80%</p>
                ${passed?`<p style="color:#16a34a;font-size:0.88rem;margin-bottom:1rem">✓ Certificado emitido!</p>`:''}
                <button class="btn ${passed?'btn-primary':'btn-outline'}" style="padding:0.65rem 2rem" onclick="App._afterExam()">
                    ${passed?'✓ Concluir':'Fechar e rever o conteúdo'}
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
                <p style="font-size:0.85rem;margin-top:0.5rem">Conclua todos os módulos de um curso para ganhar o certificado!</p>
                <button class="btn btn-primary" style="margin-top:1rem" onclick="App.renderStudentCourses()">Ver Cursos →</button>
            </div>`;
            return;
        }
        wrapper.innerHTML=`<div class="grid">` + certs.map(c=>{
            const issued=c.issued_at?new Date(c.issued_at).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):'—';
            const expires=c.expires_at?new Date(c.expires_at).toLocaleDateString('pt-BR',{timeZone:'America/Sao_Paulo'}):null;
            const info=this._certificateStatusInfo(c.expires_at);
            return `<div class="card" style="display:flex;flex-direction:column;gap:0.75rem">
                <div style="width:48px;height:48px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#fbbf24);display:flex;align-items:center;justify-content:center;font-size:1.5rem">🏆</div>
                <div>
                    <h3 style="margin:0 0 0.25rem;font-size:1rem;color:var(--primary)">${c.course_title}</h3>
                    <p style="font-size:0.82rem;color:var(--text-dim);margin:0">Emitido em ${issued}</p>
                    <p style="font-size:0.78rem;margin:0.2rem 0 0;color:${info?info.color:'var(--text-dim)'}">
                        ${info&&info.state==='vencido'?'⚠️ Expirado em':'Válido até'} ${expires}
                    </p>
                </div>
                <div style="display:flex;align-items:center;justify-content:space-between;gap:0.5rem">
                    ${info
                        ? `<span style="padding:4px 10px;border-radius:20px;font-size:0.72rem;font-weight:700;color:${info.color};background:${info.color}18;border:1px solid ${info.color}35">${info.label}</span>`
                        : `<span></span>`
                    }
                    <button onclick="App._downloadCertificate(${c.certificate_id}, this)" style="padding:5px 12px;border-radius:6px;font-size:0.78rem;cursor:pointer;background:var(--primary-light);border:none;color:white;font-family:Outfit,sans-serif;font-weight:600">⬇ Baixar PDF</button>
                </div>
            </div>`;
        }).join('') + `</div>`;
    },

    _afterExam() {
        this.closeModal();
        if (this.currentCourse && this.currentCourse.id) {
            this.showStudentModules(this.currentCourse.id, this.currentCourse.title);
        } else {
            this.renderStudentDashboard();
        }
    },
});
