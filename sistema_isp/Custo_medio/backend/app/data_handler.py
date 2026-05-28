import pandas as pd
import os
import re
import unicodedata

def normalizar_texto(texto):
    """Remove acentos, espaços extras e coloca em maiúsculo"""
    if pd.isna(texto) or texto == '':
        return "NÃO INFORMADO"
    # Remove acentos (Ex: 'Caxias do Sul' -> 'Caxias do Sul')
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    texto_sem_acento = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    # Limpa espaços e sobe para MAIÚSCULO
    return texto_sem_acento.strip().upper()

def extrair_numero(valor):
    """Extrai apenas números (MB, R$, etc)"""
    if pd.isna(valor) or valor == '': return 0
    apenas_numeros = re.sub(r'[^0-9,.]', '', str(valor)).replace(',', '.')
    try:
        return float(apenas_numeros)
    except:
        return 0

def carregar_dados_planilha():
    caminho_csv = os.path.join(os.path.dirname(__file__), '..', 'contratos.csv')
    
    # Lista de encodings para tentar, caso o padrão falhe
    encodings = ['latin-1', 'utf-8', 'cp1252', 'utf-8-sig']
    # Lista de separadores prováveis
    separadores = [';', ',', '\t']
    
    df = None
    
    # Tenta carregar com diferentes combinações de encoding e separador
    for sep in separadores:
        for enc in encodings:
            try:
                df = pd.read_csv(caminho_csv, sep=sep, encoding=enc, low_memory=False)
                # Se o DataFrame não tiver pelo menos uma das colunas esperadas, 
                # assume que o separador/encoding está errado
                if 'Serviço' in df.columns or 'Cidade A' in df.columns:
                    break
            except:
                continue
        if df is not None and ('Serviço' in df.columns or 'Cidade A' in df.columns):
            break
            
    if df is None:
        print("❌ Erro: Não foi possível ler o arquivo. Verifique se o CSV está corrompido.")
        return pd.DataFrame()

    try:
        mapeamento = {
            'Cidade A': 'cidade',
            'UF A': 'uf',
            'Serviço': 'tipo_servico',
            'Interface': 'interface',
            'IP Fixo': 'ip_fixo',
            'Capacidade (MB)': 'velocidade',
            'Vigência em (Meses)': 'prazo',
            'Valor Mensal (C/IMP) (R$)': 'valor'
        }
        
        # Filtra apenas colunas que existem no CSV
        df = df.rename(columns=mapeamento)
        colunas_reais = [col for col in mapeamento.values() if col in df.columns]
        df = df[colunas_reais]

        # Limpeza de dados numéricos
        cols_numericas = ['velocidade', 'prazo', 'valor']
        for col in cols_numericas:
            if col in df.columns:
                df[col] = df[col].apply(extrair_numero)
        
        # Converte para tipos numéricos forçados (trata erros como NaN)
        df['velocidade'] = pd.to_numeric(df['velocidade'], errors='coerce').fillna(0).astype(int)
        df['prazo'] = pd.to_numeric(df['prazo'], errors='coerce').fillna(0).astype(int)
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce').fillna(0)

        # Normalização de TEXTO
        cols_texto = ['cidade', 'uf', 'tipo_servico', 'interface', 'ip_fixo']
        for col in cols_texto:
            if col in df.columns:
                df[col] = df[col].apply(normalizar_texto)

        return df[df['valor'] > 0]
    except Exception as e:
        print(f"Erro no processamento dos dados: {e}")
        return pd.DataFrame()

def obter_opcoes_filtros(df):
    if df is None or df.empty:
        return {"servicos": [], "interfaces": [], "ips": []}
    
    # Converte para string para evitar o erro de comparação float vs str
    return {
        "servicos": sorted([str(x) for x in df['tipo_servico'].unique() if x != "NÃO INFORMADO"]),
        "interfaces": sorted([str(x) for x in df['interface'].unique() if x != "NÃO INFORMADO"]),
        "ips": sorted([str(x) for x in df['ip_fixo'].unique() if x != "NÃO INFORMADO"])
    }