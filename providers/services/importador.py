from django.conf import settings
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from providers.models import Provedor

def sincronizar_dados_google_sheets():
    # Definição de escopo para a API
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    if not settings.GOOGLE_SHEETS_ID or not settings.GOOGLE_APPLICATION_CREDENTIALS:
        return False, 'Integração não configurada no ambiente.'
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(settings.GOOGLE_APPLICATION_CREDENTIALS, scope)
        client = gspread.authorize(creds)

        # Abre a planilha pelo seu ID exclusivo
        planilha = client.open_by_key(settings.GOOGLE_SHEETS_ID)
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
    except Exception:
        return False, 'Não foi possível sincronizar a planilha. Verifique a configuração privada e as permissões.'