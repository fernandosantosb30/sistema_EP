import gspread
from oauth2client.service_account import ServiceAccountCredentials
from sistema_isp.projeto_django_backup.providers.models import Provedor

def sincronizar_dados_google_sheets():
    # Definição de escopo para a API
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # IMPORTANTE: O arquivo credentials.json deve estar na raiz do projeto
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)

        # Abre a planilha pelo seu ID exclusivo
        planilha = client.open_by_key('111075979586424983903')
        # Aqui você pode usar .sheet1 ou o nome exato: .worksheet("Contratações EP CONEXÕES")
        aba = planilha.get_worksheet(0) 
        
        dados = aba.get_all_records()

        for linha in dados:
            # Faz o 'Upsert' (Atualiza se existir pelo CNPJ, se não, cria)
            Provedor.objects.update_or_create(
                cnpj=linha.get('CNPJ'),
                defaults={
                    'nome_fantasia': linha.get('Nome ISP'),
                    'tecnologia': linha.get('Tecnologia'),
                    'cidade': linha.get('Cidade'),
                    'uf': linha.get('UF'),
                    'latitude': linha.get('Latitude'),
                    'longitude': linha.get('Longitude'),
                }
            )
        return True, len(dados)
    except Exception as e:
        return False, str(e)