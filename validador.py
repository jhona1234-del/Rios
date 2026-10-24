"""
Extrator e Validador Oficial da API Defesa Civil RS.
Este script raspa a documentação oficial para encontrar as strings exatas (whitelisted)
que o firewall permite e testa-as contra a API.
"""
import urllib3
import requests
import re
import json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

DOC_URL = "https://sistemas.defesacivil.rs.gov.br/api-redehidrometeorologica"
API_URL = "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def extrair_queries_do_guia():
    print(f"📖 Lendo o manual oficial em: {DOC_URL}")
    try:
        html = requests.get(DOC_URL, verify=False, timeout=15).text
    except Exception as e:
        print(f"❌ Erro ao acessar o manual: {e}")
        return []
    
    # Busca blocos de código que começam com query
    padrao = re.compile(r'query\s+[A-Za-z0-9_]+\s*\{.*?\}', re.DOTALL)
    queries = padrao.findall(html)
    
    if not queries:
        print("⚠️ Não encontrei consultas no formato esperado no manual.")
        return []
    
    # Limpa tags HTML se vieram agarradas (caso existam spans de formatação)
    queries_limpas = []
    for q in queries:
        q_clean = re.sub(r'<[^>]+>', '', q)
        # Substitui entidades HTML
        q_clean = q_clean.replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
        queries_limpas.append(q_clean)
        
    return list(set(queries_limpas)) # Remove duplicados

def testar_queries(queries):
    print(f"\n🔍 Encontradas {len(queries)} consultas no manual. Iniciando testes...\n")
    
    sucessos = 0
    for i, q in enumerate(queries, 1):
        # Descobre o nome da query (Tags_data, Historic, etc)
        nome = q.split('{')[0].replace('query', '').strip()
        print(f"▶️ Teste {i}: Query '{nome}'")
        print("-" * 40)
        print(q.strip())
        print("-" * 40)
        
        payload = {"query": q.strip()}
        
        try:
            resp = requests.post(API_URL, json=payload, headers=HEADERS, verify=False, timeout=15)
            dados = resp.json()
            
            if "errors" in dados:
                erro_msg = dados["errors"][0].get("message", "Erro desconhecido")
                print(f"❌ REJEITADO pelo servidor: {erro_msg}\n")
            else:
                print("✅ SUCESSO! A API aceitou esta string perfeitamente!\n")
                sucessos += 1
                
        except Exception as e:
            print(f"❌ Erro HTTP ou JSON inválido: {e}\n")
            
    if sucessos == 0:
        print("\n🚨 Nenhuma consulta oficial funcionou. O bloqueio pode ser mais profundo (ex: bloqueio de IP do GitHub).")

if __name__ == "__main__":
    queries_oficiais = extrair_queries_do_guia()
    if queries_oficiais:
        testar_queries(queries_oficiais)
