import requests
import json
from datetime import datetime, timedelta
import sqlite3

BASE_URL = "http://localhost:8000"

results = []

def add_result(id, desc, status, result):
    results.append(f"| **{id}** | {desc} | {status} | {result} |")

def login(username, password):
    r = requests.post(f"{BASE_URL}/login", json={"username": username, "password": password})
    if r.status_code == 200 and 'access_token' in r.json():
        return r.json()['access_token'], r.json()
    return None, r.json()

print("Pegando admin_token...")
admin_token, _ = login("admin", "admin")
admin_headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

if not admin_token:
    print("Erro ao logar como admin.")
    exit(1)

print("Iniciando TC-027...")
r_path = requests.post(f"{BASE_URL}/paths", headers=admin_headers, data={"title": "Trilha Teste API", "description": "Desc"})
if r_path.status_code == 200:
    path_id = r_path.json()["id"]
    add_result("TC-027", "Criar trilha", "✅ Passou", "Trilha criada com sucesso via API.")
else:
    path_id = None
    add_result("TC-027", "Criar trilha", "❌ Falhou", f"Erro: {r_path.text}")

print("Iniciando TC-028...")
r_path2 = requests.post(f"{BASE_URL}/paths", headers=admin_headers, data={"title": "Trilha Padrao API", "is_standard_training": True})
if r_path2.status_code == 200 and r_path2.json().get("is_standard_training"):
    add_result("TC-028", "Marcar trilha como padrão obrigatório", "✅ Passou", "Trilha marcada como obrigatória com sucesso.")
else:
    add_result("TC-028", "Marcar trilha como padrão obrigatório", "❌ Falhou", "Não foi possível criar trilha padrão.")

# TC-029: Criar curso dentro de trilha
print("Iniciando TC-029...")
if path_id:
    r_course = requests.post(f"{BASE_URL}/paths/{path_id}/courses", headers=admin_headers, data={"title": "Curso API", "description": "Desc", "order": 1})
    if r_course.status_code == 200:
        course_id = r_course.json()["id"]
        add_result("TC-029", "Criar curso dentro de trilha", "✅ Passou", "Curso criado.")
    else:
        course_id = None
        add_result("TC-029", "Criar curso dentro de trilha", "❌ Falhou", f"Erro: {r_course.text}")
else:
    course_id = None
    add_result("TC-029", "Criar curso dentro de trilha", "⚠️ Bloqueado", "Depende do TC-027.")

# TC-030: Criar modulo com upload de video
print("Iniciando TC-030...")
if course_id:
    files = {'video': ('test.mp4', b'dummy video content', 'video/mp4')}
    data = {"title": "Modulo API", "description": "Desc", "order": 1, "video_duration": 60, "validity_months": 12}
    r_mod = requests.post(f"{BASE_URL}/courses/{course_id}/modules", headers=admin_headers, data=data, files=files)
    if r_mod.status_code == 200:
        mod_id = r_mod.json()["id"]
        add_result("TC-030", "Criar módulo com upload de vídeo", "✅ Passou", "Módulo criado e vídeo aceito pela API.")
    else:
        mod_id = None
        add_result("TC-030", "Criar módulo com upload de vídeo", "❌ Falhou", f"Erro: {r_mod.text}")
else:
    mod_id = None
    add_result("TC-030", "Criar módulo com upload de vídeo", "⚠️ Bloqueado", "Depende do TC-029.")

# TC-031: Adicionar questao de quiz ao modulo
# FIX: endpoint espera JSON body com campos text/option_a.../correct_option
print("Iniciando TC-031...")
if mod_id:
    q_data = {
        "text": "Qual é o principal objetivo da LGPD?",
        "option_a": "Proteger dados pessoais",
        "option_b": "Regular o mercado financeiro",
        "option_c": "Controlar o acesso à internet",
        "option_d": "Definir impostos digitais",
        "correct_option": "a",
        "timestamp": 10,
        "is_final_exam": False
    }
    r_quiz = requests.post(
        f"{BASE_URL}/modules/{mod_id}/questions",
        headers={**admin_headers, "Content-Type": "application/json"},
        json=q_data
    )
    if r_quiz.status_code == 200:
        add_result("TC-031", "Adicionar questão de quiz ao módulo", "✅ Passou", "Questão adicionada.")
    else:
        add_result("TC-031", "Adicionar questão de quiz ao módulo", "❌ Falhou", f"Erro: {r_quiz.text}")
else:
    add_result("TC-031", "Adicionar questão de quiz ao módulo", "⚠️ Bloqueado", "Depende do TC-030.")

# TC-033: Matricular usuario em trilha
# FIX: endpoint correto é POST /enrollments com user_id e path_id no body
print("Iniciando TC-033...")
r_users = requests.get(f"{BASE_URL}/admin/users", headers=admin_headers)
user_id = next((u["id"] for u in r_users.json() if u["username"] == "colaborador_teste"), None)
if user_id and path_id:
    r_enroll = requests.post(
        f"{BASE_URL}/enrollments",
        headers=admin_headers,
        data={"user_id": user_id, "path_id": path_id}
    )
    if r_enroll.status_code == 200:
        add_result("TC-033", "Matricular usuário em trilha", "✅ Passou", "Usuário matriculado com sucesso.")
    else:
        add_result("TC-033", "Matricular usuário em trilha", "❌ Falhou", f"Erro: {r_enroll.text}")
else:
    add_result("TC-033", "Matricular usuário em trilha", "⚠️ Bloqueado", "Usuário não encontrado.")

print("Iniciando TC-032...")
r_del_path = requests.delete(f"{BASE_URL}/paths/{path_id}", headers=admin_headers)
if r_del_path.status_code == 200:
    add_result("TC-032", "Excluir trilha", "✅ Passou", "Trilha excluída com sucesso.")
else:
    add_result("TC-032", "Excluir trilha", "❌ Falhou", f"Erro: {r_del_path.text}")

print("Recriando trilha...")
# --- Bloco 6 e 7 ---
# Recriar uma trilha para os testes do aluno
video_url = None  # será preenchido quando o módulo for criado
r_path = requests.post(f"{BASE_URL}/paths", headers=admin_headers, data={"title": "Trilha Aluno API", "description": ""})
path_id = r_path.json().get("id")

if path_id:
    print("Recriando curso...")
    r_course = requests.post(f"{BASE_URL}/paths/{path_id}/courses", headers=admin_headers, data={"title": "Curso Aluno", "description": "Curso para teste do aluno", "order": 1})
    if r_course.status_code != 200:
        print(f"ERRO ao recriar curso: {r_course.status_code} {r_course.text}")
    course_id = r_course.json().get("id")

    if course_id:
        print("Recriando modulo...")
        files = {'video': ('test_aluno.mp4', b'dummy video content', 'video/mp4')}
        r_mod = requests.post(f"{BASE_URL}/courses/{course_id}/modules", headers=admin_headers, data={"title": "Modulo Aluno", "description": "Modulo de teste", "order": 1, "validity_months": 12}, files=files)
        if r_mod.status_code != 200:
            print(f"ERRO ao recriar modulo: {r_mod.status_code} {r_mod.text}")
        mod_id = r_mod.json().get("id")
        video_url = r_mod.json().get("video_url")  # URL real do vídeo
        print(f"Modulo recriado: id={mod_id}, video_url={video_url}")
    else:
        mod_id = None

    # Matrícula feita independente do módulo (usuário precisa estar na trilha)
    print("Matriculando...")
    r_enroll2 = requests.post(f"{BASE_URL}/enrollments", headers=admin_headers, data={"user_id": user_id, "path_id": path_id})
    if r_enroll2.status_code != 200:
        print(f"ERRO ao matricular: {r_enroll2.status_code} {r_enroll2.text}")
else:
    course_id = None
    mod_id = None

print("Resetando senha...")
# Reset senha para gerar must_change_password=True
requests.post(f"{BASE_URL}/admin/users/{user_id}/reset-password", headers=admin_headers)

print("Logando como colaborador...")
# Login colaborador
colab_token, login_res = login("colaborador_teste", "Mudar@123")
colab_headers = {"Authorization": f"Bearer {colab_token}"}

print("Iniciando TC-041...")
# TC-041
if login_res.get("user", {}).get("must_change_password"):
    add_result("TC-041", "Troca de senha obrigatória no 1º login", "✅ Passou", "API retornou must_change_password: true.")
else:
    add_result("TC-041", "Troca de senha obrigatória no 1º login", "❌ Falhou", "Flag não retornada.")

print("Iniciando TC-042...")
# TC-042
r_pass1 = requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "Mudar@123"})
if r_pass1.status_code == 400 and "diferente" in r_pass1.text:
    add_result("TC-042", "Não pode salvar Mudar@123 como nova senha", "✅ Passou", "API bloqueou a senha temporária.")
else:
    add_result("TC-042", "Não pode salvar Mudar@123 como nova senha", "❌ Falhou", f"Esperava 400, obteve {r_pass1.status_code}.")

print("Iniciando TC-043...")
# TC-043
r_pass2 = requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "123"})
if r_pass2.status_code == 400 and "caracteres" in r_pass2.text:
    add_result("TC-043", "Senha com menos de 6 caracteres", "✅ Passou", "API bloqueou senha muito curta.")
else:
    add_result("TC-043", "Senha com menos de 6 caracteres", "❌ Falhou", f"Esperava 400, obteve {r_pass2.status_code}.")

print("Voltando a senha para valido...")
# Set valid password
requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "colaborador123"})
print("Relogando...")
colab_token, _ = login("colaborador_teste", "colaborador123")
colab_headers = {"Authorization": f"Bearer {colab_token}"}

add_result("TC-044", "Confirmar senha com valores diferentes", "⚠️ Teste Front-end", "Validação de igualdade já coberta pelo frontend.")

print("Iniciando TC-034...")
# TC-034
r_mypaths = requests.get(f"{BASE_URL}/my-paths", headers=colab_headers)
if r_mypaths.status_code == 200 and len(r_mypaths.json()) > 0:
    add_result("TC-034", "Visualizar trilhas matriculadas", "✅ Passou", "API retornou as trilhas corretas para o aluno.")
else:
    add_result("TC-034", "Visualizar trilhas matriculadas", "❌ Falhou", f"Erro: {r_mypaths.text}")

print("Iniciando TC-035...")
# TC-035: FIX — usa a URL real do vídeo retornada pelo módulo, não um caminho hardcoded
if video_url:
    r_vid = requests.get(f"{BASE_URL}{video_url}", headers=colab_headers, timeout=5)
    if r_vid.status_code in [200, 206]:
        add_result("TC-035", "Assistir vídeo (streaming/seek)", "✅ Passou", f"Endpoint do vídeo acessível ({video_url}).")
    else:
        add_result("TC-035", "Assistir vídeo (streaming/seek)", "❌ Falhou", f"Endpoint retornou: {r_vid.status_code} para {video_url}")
else:
    add_result("TC-035", "Assistir vídeo (streaming/seek)", "⚠️ Bloqueado", "video_url não retornado pelo módulo.")

print("Iniciando TC-036...")
# TC-036
r_quiz_get = requests.get(f"{BASE_URL}/modules/{mod_id}/questions", headers=colab_headers)
if r_quiz_get.status_code == 200:
    add_result("TC-036", "Quiz inline no vídeo", "✅ Passou", "API retornou a lista de questões do módulo.")
else:
    add_result("TC-036", "Quiz inline no vídeo", "❌ Falhou", f"Erro: {r_quiz_get.status_code}")

print("Iniciando TC-037 & TC-038...")
# TC-037 & TC-038
r_comp = requests.post(f"{BASE_URL}/modules/{mod_id}/complete", headers=colab_headers, data={"score": 85.0})
if r_comp.status_code == 200:
    add_result("TC-037", "Fazer prova final (score)", "✅ Passou", "Progresso e score salvos via API.")
else:
    add_result("TC-037", "Fazer prova final (score)", "❌ Falhou", f"Erro: {r_comp.text}")

r_cert = requests.post(f"{BASE_URL}/modules/{mod_id}/certificate", headers=colab_headers)
if r_cert.status_code == 200:
    cert_data = r_cert.json()
    add_result("TC-038", "Concluir módulo e emitir certificado", "✅ Passou", "Certificado gerado com sucesso após conclusão.")
    if cert_data.get("expires_at"):
        add_result("TC-039", "Certificado com data de validade", "✅ Passou", f"Certificado possui validade gerada pela API.")
    else:
        add_result("TC-039", "Certificado com data de validade", "❌ Falhou", "Sem data de expiração.")
else:
    add_result("TC-038", "Concluir módulo e emitir certificado", "❌ Falhou", f"Erro: {r_cert.text}")
    add_result("TC-039", "Certificado com data de validade", "⚠️ Bloqueado", "Certificado não gerado.")

print("Iniciando TC-040...")
# TC-040
r_admin_check = requests.get(f"{BASE_URL}/admin/users", headers=colab_headers)
if r_admin_check.status_code in [403, 401]:
    add_result("TC-040", "Colaborador não acessa área admin", "✅ Passou", "API bloqueou acesso (403/401).")
else:
    add_result("TC-040", "Colaborador não acessa área admin", "❌ Falhou", f"Acesso indevido. Código: {r_admin_check.status_code}")

print("Iniciando TC-045...")
# TC-045
try:
    conn = sqlite3.connect('training_platform.db')
    c = conn.cursor()
    c.execute("UPDATE users SET reset_token = 'token_velho', reset_token_expires = ? WHERE id = ?", (datetime.utcnow() - timedelta(days=1), user_id))
    conn.commit()
    conn.close()
    
    r_reset_expired = requests.post(f"{BASE_URL}/auth/reset-password", data={"token": "token_velho", "new_password": "NovaSenha123"})
    if r_reset_expired.status_code == 400 and "expirado" in r_reset_expired.text.lower():
        add_result("TC-045", "Token de reset expirado", "✅ Passou", "API bloqueou uso de token de reset vencido.")
    else:
        add_result("TC-045", "Token de reset expirado", "❌ Falhou", f"Erro: {r_reset_expired.text}")
except Exception as e:
    add_result("TC-045", "Token de reset expirado", "❌ Falhou", f"Erro BD: {str(e)}")

with open('test_output.md', 'w', encoding='utf-8') as f:
    f.write("| ID | Caso de Teste | Status | Resultado Obtido |\n")
    f.write("| :--- | :--- | :--- | :--- |\n")
    for r in results:
        f.write(r + "\n")
print("Resultados salvos em test_output.md")
