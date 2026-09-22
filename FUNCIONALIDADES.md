# Funcionalidades — GeoTrilha

Documento de referência das funcionalidades do sistema, principalmente as
que não são óbvias só de olhar a tela. Não é changelog (isso já fica no
histórico do `git log`) — é "como isso funciona hoje e onde configurar".

---

## Empresas (multi-tenant)

O GeoTrilha atende mais de uma empresa a partir do mesmo sistema/banco.
Cada usuário (exceto `super_admin`) pertence a exatamente uma empresa.

Tela: **Empresas** (menu, só `super_admin` vê).

Campos de cada empresa:

| Campo | Uso | Obrigatório? |
|---|---|---|
| Nome | Aparece em toda a tela admin, seletor de empresa, etc. | Sim |
| Logo | Aparece no certificado de quem é dessa empresa. | Não — sem logo, certificado sai sem logo. |
| Nome de quem assina | Rodapé do certificado. | Não — sem preencher, essa linha não aparece. |
| Cargo de quem assina | Rodapé do certificado, junto do nome. | Não |
| Cidade | Usada na data de emissão do certificado ("Londrina, sexta-feira, ..."). | Não — sem cidade, sai só a data. |

**Importante:** esses dados são por empresa — cada uma tem o próprio logo,
assinante e cidade, e não afetam as outras.

Papéis do sistema: `super_admin` (enxerga todas as empresas, não pertence
a nenhuma), `admin` (gerencia usuários/equipes da própria empresa),
`lideranca` (gerencia a(s) própria(s) equipe(s)), `colaborador`/`usuario`
(aluno).

---

## Curso é global (não pertence a uma empresa)

Curso deixou de pertencer a uma empresa (commit `9a7c465`). O mesmo
curso (vídeo + perguntas) é o mesmo
catálogo pra todas as empresas — não precisa duplicar conteúdo pra cada
empresa ter acesso.

- **Criar/editar/excluir curso, módulo e pergunta de quiz**: só
  `super_admin`. `admin`/`lideranca` só visualizam o catálogo (pra saber o
  que matricular na própria gente).
- **Matrícula**: `admin` só matricula gente da própria empresa;
  `lideranca` só matricula gente da própria equipe. O curso em si é
  livre — qualquer empresa pode usar qualquer curso.
- **Certificado**: usa a logo/nome/assinante/cidade da empresa **do
  aluno**, não do curso (que agora não tem empresa). Duas pessoas de
  empresas diferentes que fizeram o mesmo curso recebem certificados com
  a identidade visual de cada empresa.

Isso resolveu o caso de treinamento único (ex.: Segurança da Informação)
que precisa valer pra Geo, Cri Geo, Geo bio gas&carbon e Geo Elétrica
Tamboara (TBA) ao mesmo tempo, sem duplicar o vídeo/perguntas quatro
vezes.

---

## Líder pode liderar mais de uma equipe

Antes, liderança de equipe era o mesmo campo que a equipe-base da pessoa
(`User.team_id`) — só dava pra liderar uma. Agora existe uma tabela
separada (`TeamLeader`) só pra isso, então um líder pode liderar duas ou
mais equipes ao mesmo tempo sem perder a própria equipe-base.

- Editar papel de alguém pra "Liderança" agora mostra uma lista de
  checkboxes com as equipes que essa pessoa vai liderar.
- Dashboard do líder ganhou um filtro de equipe (só aparece se a pessoa
  lidera mais de uma).
- Dashboard do admin ganhou filtro por líder, além do filtro por equipe
  que já existia.

---

## Certificado

### Carga horária e conteúdo programático

Curso ganhou um campo **Carga horária (horas)**, opcional, no formulário
de criar/editar curso. Se preenchido, aparece no certificado.

O **conteúdo programático** do certificado usa a própria **descrição**
do curso (não é um campo novo) — evita preencher a mesma informação duas
vezes. Limitado a 3 linhas no certificado (corta com "…" se passar disso).

### Modelo visual

O certificado padrão (quando o curso não tem um "template de certificado"
próprio enviado por upload) foi refeito copiando um modelo de referência
que a Iza forneceu: fundo com faixas onduladas em degradê lilás, texto
alinhado à esquerda, fonte Outfit (mesma do resto do app), parágrafo único
com o nome do curso em negrito no meio da frase, sombra suave e brilho
sutil na borda da onda pra dar profundidade.

O contorno da onda e as posições do texto foram medidos pixel a pixel na
imagem de referência (não é uma curva desenhada "de olho") — ver
`backend/certificate_pdf.py`, constantes `TOP_WAVE_TRACE` e
`BOTTOM_WAVE_TRACE`.

Se um curso tiver um template de certificado próprio (upload de imagem no
formulário do curso), esse template continua tendo prioridade sobre esse
fundo padrão — o texto é sobreposto do mesmo jeito.

### Nome completo do usuário

Usuário ganhou o campo **Nome completo**, separado do "nome de usuário"
(login). O certificado usa o nome completo quando existe; se não tiver
(conta antiga, ou convite em que quem convidou não sabia o nome), cai no
nome de usuário mesmo.

- **Autocadastro** ("Solicitar acesso"): nome completo é obrigatório.
- **Convite** (admin/líder convida): nome completo é opcional — quem
  convida pode não saber o nome completo da pessoa na hora.
- **Ainda não existe** uma tela pra corrigir/preencher o nome completo de
  alguém que já está cadastrado — só dá pra definir na hora do
  cadastro/convite. Se precisar corrigir depois, hoje só editando direto
  no banco.

---

## Domínios de e-mail permitidos

Configurado via `ALLOWED_EMAIL_DOMAINS` no `.env` (lista separada por
vírgula). Gate geral de "esse e-mail pode se cadastrar/logar no sistema"
— **não define de qual empresa a pessoa é** (isso é escolhido explicitamente
no cadastro/convite, num seletor de empresa). Duas empresas podem
compartilhar o mesmo domínio de e-mail sem problema (ex.: Geo, Geo bio
gas&carbon e Geo Elétrica Tamboara todas usam `@geobiogas.tech`).

Toda empresa nova precisa que o próprio domínio de e-mail esteja nessa
lista, senão convite/cadastro/login de quem usa esse domínio é recusado.
**O `.env` não vai pelo git** — em produção, essa variável precisa ser
adicionada manualmente no servidor.

---

## Convites — copiar link

O botão "Copiar link" (convite, reset de senha) usa
`navigator.clipboard`, que só funciona em conexão segura (HTTPS, ou
`localhost`). Em produção servida por HTTP puro (sem certificado), esse
botão falhava sem nenhum aviso. Corrigido com um
fallback (`document.execCommand('copy')`) que funciona em qualquer
contexto — ver `frontend/js/core.js`, função `_copyLinkToClipboard`.

---

## Removido: "Prova Final" como conceito separado do curso

Existiu uma versão em que o curso tinha uma prova final própria (5
perguntas, gate separado das perguntas inline do vídeo, exigindo 80% pra
emitir certificado). Foi **revertida** — hoje o certificado é emitido
assim que todos os módulos são concluídos (cada módulo já pode ter
perguntas inline durante o vídeo, sem separação "prova final" vs
"pergunta do vídeo"). Motivo: a Iza decidiu que, na prática, o
treinamento é sempre um vídeo único com perguntas ao longo dele — separar
"prova final" só confundia quem cadastra as perguntas.
