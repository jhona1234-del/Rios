"""
Extrator e Validador Oficial da API Defesa Civil RS.
Lê a documentação contando chaves {} para extrair as queries perfeitamente intactas.
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

def extrair_queries_com_chaves_balanceadas():
    print(f"📖 Lendo o manual oficial em: {DOC_URL}")
    try:
        html = requests.get(DOC_URL, verify=False, timeout=15).text
    except Exception as e:
        print(f"❌ Erro ao acessar o manual: {e}")
        return []
    
    queries = []
    indice_atual = 0
    
    while True:
        # Encontra a próxima ocorrência de 'query '
        inicio = html.find('query ', indice_atual)
        if inicio == -1:
            break
            
        nivel_chaves = 0
        abriu_chaves = False
        fim = inicio
        
        # Percorre letra por letra para balancear as chaves {}
        for i in range(inicio, len(html)):
            char = html[i]
            if char == '{':
                nivel_chaves += 1
                abriu_chaves = True
            elif char == '}':
                nivel_chaves -= 1
                
            if abriu_chaves and nivel_chaves == 0:
                fim = i + 1
                break
                
        # Extrai e limpa qualquer sujeira de HTML (tags span, code, etc)
        query_suja = html[inicio:fim]
        query_limpa = re.sub(r'<[^>]+>', '', query_suja)
        query_limpa = query_limpa.replace('&quot;', '"').replace('&lt;', '<').replace('&gt;', '>')
        query_limpa = query_limpa.replace('&nbsp;', ' ').strip()
        
        if len(query_limpa) > 30:  # Ignora falsos positivos muito curtos
            queries.append(query_limpa)
            
        indice_atual = fim
        
    return list(set(queries))

def testar_queries(queries):
    print(f"\n🔍 Encontradas {len(queries)} consultas no manual. Iniciando testes...\n")
    
    sucessos = 0
    for i, q in enumerate(queries, 1):
        nome = q.split('{')[0].replace('query', '').strip()
        print(f"▶️ Teste {i}: Query '{nome}'")
        print("-" * 40)
        print(q)
        print("-" * 40)
        
        payload = {"query": q}
        
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
        print("\n🚨 Nenhuma consulta oficial funcionou. O bloqueio é de IP ou requer token.")

if __name__ == "__main__":
    queries_oficiais = extrair_queries_com_chaves_balanceadas()
    if queries_oficiais:
        testar_queries(queries_oficiais)