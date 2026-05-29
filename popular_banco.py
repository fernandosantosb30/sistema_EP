import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = "postgresql+psycopg2://sistema_isp_db_user:SxkbvZIJ8fg7eY2bv521KRyTNc5lcoCS@dpg-d8ccmm6gvqtc7383jfh0-a.oregon-postgres.render.com:5432/sistema_isp_db"
engine = create_engine(DATABASE_URL)

def importar_cidades():
    try:
        # 1. Carrega o CSV e limpa espaços extras
        df_cide = pd.read_csv(r'D:\Cidades.csv', encoding='latin1', sep=';', on_bad_lines='skip')
        df_cide['PROVEDOR'] = df_cide['PROVEDOR'].astype(str).str.strip()
        df_cide['CIDADE'] = df_cide['CIDADE'].astype(str).str.strip()
        df_cide['UF'] = df_cide['UF'].astype(str).str.strip()
        
        # 2. Busca os Provedores no banco
        provedores_db = pd.read_sql('SELECT id, nome FROM providers_provedor', engine)
        provedores_db['nome'] = provedores_db['nome'].str.strip()
        
        # 3. Cruzamento
        df_merge = df_cide.merge(provedores_db, left_on='PROVEDOR', right_on='nome', how='inner')
        
        # 4. Prepara os dados com limpeza de UF
        data = []
        for _, row in df_merge.iterrows():
            uf_limpa = str(row['UF'])[:2] # Garante no máximo 2 caracteres
            tupla = (
                int(row['id']),
                str(row['CIDADE']),
                uf_limpa
            )
            data.append(tupla)
        
        # 5. Inserção em lotes com cálculo de porcentagem
        conn = engine.raw_connection()
        try:
            cur = conn.cursor()
            query = """
            INSERT INTO providers_cidadeatendida (provedor_id, nome, uf) 
            VALUES (%s, %s, %s) 
            ON CONFLICT (provedor_id, nome, uf) DO NOTHING;
            """
            
            batch_size = 100
            total = len(data)
            for i in range(0, total, batch_size):
                batch = data[i:i + batch_size]
                cur.executemany(query, batch)
                conn.commit()
                
                progresso = i + len(batch)
                porcentagem = (progresso / total) * 100
                print(f"Progresso: {progresso} de {total} ({porcentagem:.1f}%) concluído.")
            
            cur.close()
            print("Sucesso! Processamento finalizado.")
        finally:
            conn.close()

    except Exception as e:
        print(f"Erro ao processar cidades: {e}")

if __name__ == "__main__":
    importar_cidades()