import pandas as pd
from sqlalchemy import create_engine

# URL do banco
DATABASE_URL = "postgresql://postgres:GGwaopq%401@localhost:5432/sistema_isp_db"
engine = create_engine(DATABASE_URL)

def importar():
    caminho = r"C:\Users\luisf\OneDrive\Desktop\Sistema_EP\sistema_isp\Custo_medio\backend\contratos.csv"
    df = pd.read_csv(caminho, sep=',')

    # Renomear colunas
    df = df.rename(columns={
        'Cidade A': 'cidade', 'UF A': 'uf', 'Serviço': 'servico',
        'IP Fixo': 'ip_fixo', 'Valor Mensal (C/IMP) (R$)': 'valor_mensal',
        'Capacidade (MB)': 'capacidade_mb', 'Vigência em (Meses)': 'vigencia_meses',
        'Interface': 'interface'
    })

def importar():
    caminho = r"C:\Users\luisf\OneDrive\Desktop\Sistema_EP\sistema_isp\Custo_medio\backend\contratos.csv"
    df = pd.read_csv(caminho, sep=',')

    # Renomear colunas
    df = df.rename(columns={
        'Cidade A': 'cidade', 'UF A': 'uf', 'Serviço': 'servico',
        'IP Fixo': 'ip_fixo', 'Valor Mensal (C/IMP) (R$)': 'valor_mensal',
        'Capacidade (MB)': 'capacidade_mb', 'Vigência em (Meses)': 'vigencia_meses',
        'Interface': 'interface'
    })

    # Função de formatação robusta
    def formatar_valor(valor):
        s = str(valor).strip()
        # Se contiver vírgula (formato 2.642,64), remove ponto de milhar e troca vírgula por ponto
        if ',' in s:
            s = s.replace('.', '').replace(',', '.')
        # Se não tiver vírgula, mas tiver múltiplos pontos (formato 2.642.64), remove os pontos
        elif s.count('.') > 1:
            s = s.replace('.', '')
        
        try:
            val = float(s)
            # Regra de negócio: se for um valor astronômico (>10.000), 
            # assume que era para ser um valor decimal (ex: 264264 -> 264.26)
            return val / 1000 if val > 10000 else val
        except:
            return 0.0

    # Aplicação da limpeza
    df['valor_mensal'] = df['valor_mensal'].apply(formatar_valor)
    
    # Selecionar colunas
    colunas = ['cidade', 'uf', 'servico', 'ip_fixo', 'valor_mensal', 'capacidade_mb', 'vigencia_meses', 'interface']
    df = df[colunas]

    print("Tentando criar a tabela no banco com valores corrigidos...")
    try:
        # IMPORTANTE: A tabela será sobrescrita com os valores limpos
        df.to_sql('providers_contratocusto', engine, if_exists='replace', index=False)
        print("✅ SUCESSO: Tabela recriada. Valores processados.")
    except Exception as e:
        print(f"❌ ERRO ao salvar no banco: {e}")

if __name__ == "__main__":
    importar()