import os
import requests
import json
from datetime import datetime, timedelta
import sqlite3
from dotenv import load_dotenv

load_dotenv()

# Variável separada de BASE_URL (que no .env é a URL pública de produção,
# usada para montar links de convite/reset) — este script cria e apaga
# dados de verdade, então não deve rodar contra produção por acidente.
BASE_URL = os.getenv("API_TEST_BASE_URL", "http://localhost:8000")

results = []

def add_result(id, desc, status, result):
    results.append(f"| **{id}** | {desc} | {status} | {result} |")

def login(username, password):
    r = requests.post(f"{BASE_URL}/login", json={"username": username, "password": password})
    if r.status_code == 200 and 'access_token' in r.json():
        return r.json()['access_token'], r.json()
    return None, r.json()

print("Pegando admin_token...")
# Desde que a senha padrão do admin passou a ser gerada aleatoriamente no
# seed (ver database.py), este script não pode mais assumir "admin"/"admin"
# — use TEST_ADMIN_USERNAME/TEST_ADMIN_PASSWORD no .env para apontar para
# um admin de teste já existente no ambiente onde o script vai rodar.
admin_token, _ = login(os.getenv("TEST_ADMIN_USERNAME", "admin"), os.getenv("TEST_ADMIN_PASSWORD", "admin123"))
admin_headers = {"Authorization": f"Bearer {admin_token}"} if admin_token else {}

if not admin_token:
    print("Erro ao logar como admin.")
    exit(1)

# Curso é o nível de topo do catálogo (não existe mais Trilha por cima) —
# um líder/admin matricula o usuário direto no curso, que é feito por
# módulos; o certificado é emitido automaticamente quando todos os módulos
# do curso são concluídos.

print("Iniciando TC-027...")
r_course = requests.post(f"{BASE_URL}/courses", headers=admin_headers, data={"title": "Curso Teste API", "description": "Desc"})
if r_course.status_code == 200:
    course_id = r_course.json()["id"]
    add_result("TC-027", "Criar curso", "✅ Passou", "Curso criado com sucesso via API.")
else:
    course_id = None
    add_result("TC-027", "Criar curso", "❌ Falhou", f"Erro: {r_course.text}")

print("Iniciando TC-028...")
r_course2 = requests.post(f"{BASE_URL}/courses", headers=admin_headers, data={"title": "Curso Padrao API", "is_standard_training": True})
if r_course2.status_code == 200 and r_course2.json().get("is_standard_training"):
    add_result("TC-028", "Marcar curso como padrão obrigatório", "✅ Passou", "Curso marcado como obrigatório com sucesso.")
else:
    add_result("TC-028", "Marcar curso como padrão obrigatório", "❌ Falhou", "Não foi possível criar curso padrão.")

# TC-029: Criar modulo com upload de video
print("Iniciando TC-029...")
if course_id:
    files = {'video': ('test.mp4', b'dummy video content', 'video/mp4')}
    data = {"title": "Modulo API", "description": "Desc", "order": 1}
    r_mod = requests.post(f"{BASE_URL}/courses/{course_id}/modules", headers=admin_headers, data=data, files=files)
    if r_mod.status_code == 200:
        mod_id = r_mod.json()["id"]
        add_result("TC-029", "Criar módulo com upload de vídeo", "✅ Passou", "Módulo criado e vídeo aceito pela API.")
    else:
        mod_id = None
        add_result("TC-029", "Criar módulo com upload de vídeo", "❌ Falhou", f"Erro: {r_mod.text}")
else:
    mod_id = None
    add_result("TC-029", "Criar módulo com upload de vídeo", "⚠️ Bloqueado", "Depende do TC-027.")

# TC-030: Adicionar questao de quiz ao modulo
print("Iniciando TC-030...")
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
        add_result("TC-030", "Adicionar questão de quiz ao módulo", "✅ Passou", "Questão adicionada.")
    else:
        add_result("TC-030", "Adicionar questão de quiz ao módulo", "❌ Falhou", f"Erro: {r_quiz.text}")
else:
    add_result("TC-030", "Adicionar questão de quiz ao módulo", "⚠️ Bloqueado", "Depende do TC-029.")

# TC-031: Matricular usuario em curso
print("Iniciando TC-031...")
r_users = requests.get(f"{BASE_URL}/admin/users", headers=admin_headers)
user_id = next((u["id"] for u in r_users.json() if u["username"] == "colaborador_teste"), None)
if user_id and course_id:
    r_enroll = requests.post(
        f"{BASE_URL}/enrollments",
        headers=admin_headers,
        data={"user_id": user_id, "course_id": course_id}
    )
    if r_enroll.status_code == 200:
        add_result("TC-031", "Matricular usuário em curso", "✅ Passou", "Usuário matriculado com sucesso.")
    else:
        add_result("TC-031", "Matricular usuário em curso", "❌ Falhou", f"Erro: {r_enroll.text}")
else:
    add_result("TC-031", "Matricular usuário em curso", "⚠️ Bloqueado", "Usuário não encontrado.")

print("Iniciando TC-032...")
r_del_course = requests.delete(f"{BASE_URL}/courses/{course_id}", headers=admin_headers)
if r_del_course.status_code == 200:
    add_result("TC-032", "Excluir curso", "✅ Passou", "Curso excluído com sucesso.")
else:
    add_result("TC-032", "Excluir curso", "❌ Falhou", f"Erro: {r_del_course.text}")

print("Recriando curso...")
# --- Recria um curso para os testes do aluno ---
video_url = None  # será preenchido quando o módulo for criado
r_course = requests.post(f"{BASE_URL}/courses", headers=admin_headers, data={"title": "Curso Aluno API", "description": "Curso para teste do aluno"})
course_id = r_course.json().get("id")

if course_id:
    print("Recriando modulo...")
    files = {'video': ('test_aluno.mp4', b'dummy video content', 'video/mp4')}
    r_mod = requests.post(f"{BASE_URL}/courses/{course_id}/modules", headers=admin_headers, data={"title": "Modulo Aluno", "description": "Modulo de teste", "order": 1}, files=files)
    if r_mod.status_code != 200:
        print(f"ERRO ao recriar modulo: {r_mod.status_code} {r_mod.text}")
    mod_id = r_mod.json().get("id")
    video_url = r_mod.json().get("video_url")  # URL real do vídeo
    print(f"Modulo recriado: id={mod_id}, video_url={video_url}")

    # Matrícula feita independente do módulo (usuário precisa estar no curso)
    print("Matriculando...")
    r_enroll2 = requests.post(f"{BASE_URL}/enrollments", headers=admin_headers, data={"user_id": user_id, "course_id": course_id})
    if r_enroll2.status_code != 200:
        print(f"ERRO ao matricular: {r_enroll2.status_code} {r_enroll2.text}")
else:
    mod_id = None

print("Resetando senha...")
# Reset senha para gerar must_change_password=True
requests.post(f"{BASE_URL}/admin/users/{user_id}/reset-password", headers=admin_headers)

print("Logando como colaborador...")
# Login colaborador
colab_token, login_res = login("colaborador_teste", "Mudar@123")
colab_headers = {"Authorization": f"Bearer {colab_token}"}

print("Iniciando TC-033...")
if login_res.get("user", {}).get("must_change_password"):
    add_result("TC-033", "Troca de senha obrigatória no 1º login", "✅ Passou", "API retornou must_change_password: true.")
else:
    add_result("TC-033", "Troca de senha obrigatória no 1º login", "❌ Falhou", "Flag não retornada.")

print("Iniciando TC-034...")
r_pass1 = requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "Mudar@123"})
if r_pass1.status_code == 400 and "diferente" in r_pass1.text:
    add_result("TC-034", "Não pode salvar Mudar@123 como nova senha", "✅ Passou", "API bloqueou a senha temporária.")
else:
    add_result("TC-034", "Não pode salvar Mudar@123 como nova senha", "❌ Falhou", f"Esperava 400, obteve {r_pass1.status_code}.")

print("Iniciando TC-035...")
r_pass2 = requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "123"})
if r_pass2.status_code == 400 and "caracteres" in r_pass2.text:
    add_result("TC-035", "Senha com menos de 6 caracteres", "✅ Passou", "API bloqueou senha muito curta.")
else:
    add_result("TC-035", "Senha com menos de 6 caracteres", "❌ Falhou", f"Esperava 400, obteve {r_pass2.status_code}.")

print("Voltando a senha para valido...")
# Set valid password
requests.post(f"{BASE_URL}/auth/change-password", headers=colab_headers, data={"new_password": "colaborador123"})
print("Relogando...")
colab_token, _ = login("colaborador_teste", "colaborador123")
colab_headers = {"Authorization": f"Bearer {colab_token}"}

add_result("TC-036", "Confirmar senha com valores diferentes", "⚠️ Teste Front-end", "Validação de igualdade já coberta pelo frontend.")

print("Iniciando TC-037...")
r_mycourses = requests.get(f"{BASE_URL}/my-courses", headers=colab_headers)
if r_mycourses.status_code == 200 and len(r_mycourses.json()) > 0:
    add_result("TC-037", "Visualizar cursos matriculados", "✅ Passou", "API retornou os cursos corretos para o aluno.")
else:
    add_result("TC-037", "Visualizar cursos matriculados", "❌ Falhou", f"Erro: {r_mycourses.text}")

print("Iniciando TC-038...")
# FIX — usa a URL real do vídeo retornada pelo módulo, não um caminho hardcoded
if video_url:
    r_vid = requests.get(f"{BASE_URL}{video_url}", headers=colab_headers, timeout=5)
    if r_vid.status_code in [200, 206]:
        add_result("TC-038", "Assistir vídeo (streaming/seek)", "✅ Passou", f"Endpoint do vídeo acessível ({video_url}).")
    else:
        add_result("TC-038", "Assistir vídeo (streaming/seek)", "❌ Falhou", f"Endpoint retornou: {r_vid.status_code} para {video_url}")
else:
    add_result("TC-038", "Assistir vídeo (streaming/seek)", "⚠️ Bloqueado", "video_url não retornado pelo módulo.")

print("Iniciando TC-039...")
r_quiz_get = requests.get(f"{BASE_URL}/modules/{mod_id}/questions", headers=colab_headers)
if r_quiz_get.status_code == 200:
    add_result("TC-039", "Quiz inline no vídeo", "✅ Passou", "API retornou a lista de questões do módulo.")
else:
    add_result("TC-039", "Quiz inline no vídeo", "❌ Falhou", f"Erro: {r_quiz_get.status_code}")

print("Iniciando TC-040 & TC-041...")
# Módulo sem prova final (só vídeo) — /complete marca como concluído com
# score fixo em 100 e, como é o único módulo do curso, já emite o
# certificado automaticamente na mesma chamada.
r_comp = requests.post(f"{BASE_URL}/modules/{mod_id}/complete", headers=colab_headers)
if r_comp.status_code == 200 and r_comp.json().get("certificate_issued"):
    add_result("TC-040", "Concluir módulo e emitir certificado automaticamente", "✅ Passou", "Progresso salvo e certificado emitido ao concluir o último (e único) módulo do curso.")
else:
    add_result("TC-040", "Concluir módulo e emitir certificado automaticamente", "❌ Falhou", f"Erro: {r_comp.text}")

r_certs = requests.get(f"{BASE_URL}/my-certificates", headers=colab_headers)
cert = next((c for c in r_certs.json() if c.get("course_id") == course_id), None) if r_certs.status_code == 200 else None
if cert and cert.get("expires_at"):
    add_result("TC-041", "Certificado com data de validade", "✅ Passou", "Certificado do curso possui validade gerada pela API.")
else:
    add_result("TC-041", "Certificado com data de validade", "❌ Falhou", "Certificado não encontrado ou sem data de expiração.")

print("Iniciando TC-042...")
r_admin_check = requests.get(f"{BASE_URL}/admin/users", headers=colab_headers)
if r_admin_check.status_code in [403, 401]:
    add_result("TC-042", "Colaborador não acessa área admin", "✅ Passou", "API bloqueou acesso (403/401).")
else:
    add_result("TC-042", "Colaborador não acessa área admin", "❌ Falhou", f"Acesso indevido. Código: {r_admin_check.status_code}")

print("Iniciando TC-043...")
try:
    conn = sqlite3.connect('training_platform.db')
    c = conn.cursor()
    c.execute("UPDATE users SET reset_token = 'token_velho', reset_token_expires = ? WHERE id = ?", (datetime.utcnow() - timedelta(days=1), user_id))
    conn.commit()
    conn.close()

    r_reset_expired = requests.post(f"{BASE_URL}/auth/reset-password", data={"token": "token_velho", "new_password": "NovaSenha123"})
    if r_reset_expired.status_code == 400 and "expirado" in r_reset_expired.text.lower():
        add_result("TC-043", "Token de reset expirado", "✅ Passou", "API bloqueou uso de token de reset vencido.")
    else:
        add_result("TC-043", "Token de reset expirado", "❌ Falhou", f"Erro: {r_reset_expired.text}")
except Exception as e:
    add_result("TC-043", "Token de reset expirado", "❌ Falhou", f"Erro BD: {str(e)}")

with open('test_output.md', 'w', encoding='utf-8') as f:
    f.write("| ID | Caso de Teste | Status | Resultado Obtido |\n")
    f.write("| :--- | :--- | :--- | :--- |\n")
    for r in results:
        f.write(r + "\n")
print("Resultados salvos em test_output.md")
