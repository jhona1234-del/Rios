"""
Validador e Explorador da API GraphQL da Defesa Civil RS.
Este script testa diferentes formatos e tenta extrair o esquema do servidor.
"""
import json
import urllib3
import requests

# Desativa os avisos de certificado SSL vencido
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

API_URL = "https://redehidrometeorologica.defesacivil.rs.gov.br/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

# Bateria de testes com diferentes formatações e tentativas de introspecção
QUERIES_PARA_TESTAR = {
    "1_Introspeccao_Completa": """
query {
  __schema {
    types {
      name
      kind
    }
  }
}
    """,
    "2_Introspeccao_Campos": """
query {
  __type(name: "Query") {
    name
    fields {
      name
    }
  }
}
    """,
    "3_Tags_Data_Linha_Unica": """query Tags_data { tags_data(clients: ["casa-militar-defesa-civil-rs"]) { qualle_meteorologia { codigo name { prefix general local } } } }""",
    "4_Tags_Data_Identada": """
query Tags_data {
  tags_data(clients: ["casa-militar-defesa-civil-rs"]) {
    qualle_meteorologia {
      codigo
    }
  }
}
    """,
    "5_Historic_Linha_Unica": """query Historic { historic(system: Qualle_Hidrometeorologia, client: "casa-militar-defesa-civil-rs", stationCode: "430040602G", startDate: "2024-05-01 00:00:00", endDate: "2024-05-02 00:00:00", interval: HOUR_1) }"""
}

def testar_api():
    print("🔍 INICIANDO VALIDAÇÃO DA API DA DEFESA CIVIL RS...\n")
    print("O objetivo é descobrir qual formato exato o firewall deles aprova.\n")
    
    for nome, query in QUERIES_PARA_TESTAR.items():
        print(f"▶️ Testando: {nome}")
        
        # O strip() remove espaços vazios antes e depois da query
        payload = {"query": query.strip()}
        
        try:
            resposta = requests.post(
                API_URL, 
                json=payload, 
                headers=HEADERS, 
                verify=False,
                timeout=15
            )
            print(f"Status HTTP: {resposta.status_code}")
            
            try:
                dados = resposta.json()
                saida_json = json.dumps(dados, indent=2, ensure_ascii=False)
                
                # Se a resposta for um erro do WAF deles
                if "errors" in dados:
                    print("❌ REJEITADO:")
                    print(saida_json[:500]) # Mostra o motivo do erro
                else:
                    print("✅ SUCESSO! O servidor aceitou este formato:")
                    # Resumir a saída se for muito grande
                    if len(saida_json) > 800:
                        print(saida_json[:800] + "\n... [RESULTADO TRUNCADO]")
                    else:
                        print(saida_json)
                        
            except ValueError:
                print("❌ Erro: A resposta não é um JSON válido.")
                print(resposta.text[:500])
                
        except Exception as e:
            print(f"❌ Erro de conexão/timeout: {e}")
        
        print("-" * 70)

if __name__ == "__main__":
    testar_api()