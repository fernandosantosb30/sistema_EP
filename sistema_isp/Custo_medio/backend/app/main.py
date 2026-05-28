import io
import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text
from fastapi import FastAPI, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- CONFIGURAÇÃO DE CAMINHOS CORRIGIDA ---
## --- CONFIGURAÇÃO DE CAMINHOS ---
BASE_DIR = r"C:\Users\luisf\OneDrive\Desktop\Sistema_EP\sistema_isp\Custo_medio"
# A pasta onde estão o CSS e o JS (mantenha como está)
STATIC_DIR = os.path.join(BASE_DIR, "backend", "static")
# A pasta onde está o seu HTML (se for a mesma, tudo bem, mas não monte a pasta inteira)
HTML_DIR = os.path.join(BASE_DIR, "backend", "static")

app = FastAPI(title="API Custo Médio - Ep Conexões")

@app.get("/teste")
async def teste():
    return {"status": "A rota funciona!"}

# --- CONEXÃO COM BANCO DE DADOS ---
DATABASE_URL = "postgresql://postgres:GGwaopq%401@localhost:5432/sistema_isp_db"
engine = create_engine(DATABASE_URL)

def carregar_dados_do_banco():
    try:
        # Primeiro, verificamos se a tabela existe
        check_query = "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'providers_contratocusto');"
        with engine.connect() as conn:
            exists = conn.execute(text(check_query)).scalar()
        
        if not exists:
            print("❌ ERRO CRÍTICO: A tabela 'providers_contratocusto' não existe no banco!")
            return None
            
        query = "SELECT cidade, uf, servico, ip_fixo, valor_mensal, capacidade_mb, vigencia_meses, interface FROM public.providers_contratocusto"
        return pd.read_sql(query, engine)
    except Exception as e:
        print(f"❌ Erro ao conectar no banco: {e}")
        return None

DADOS_FIXOS = carregar_dados_do_banco()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- SERVIDOR DE FRONTEND ---
# Montamos a pasta static (onde estão o index.html e a pasta CSS)
if os.path.exists(STATIC_DIR):
    # MUDE ISSO:
    app.mount("/static", StaticFiles(directory=r"C:\Users\luisf\OneDrive\Desktop\Sistema_EP\sistema_isp\Custo_medio\backend\static"), name="static")

@app.get("/")
async def root():
    file_path = os.path.join(HTML_DIR, "index.html")
    return FileResponse(file_path)

# ... (Mantenha o restante das suas rotas abaixo)

# --- AJUSTE NAS ROTAS DE API ---

@app.get("/api/custo-medio/")
async def get_custo_medio(
    cidade: str = None, uf: str = None, servico: str = None, 
    interface: str = None, ip_fixo: str = None, capacidade: int = None, 
    vigencia: int = None
):
    df = DADOS_FIXOS
    if df is None or df.empty:
        return {"custo_medio": 0, "quantidade_contratos": 0, "tipo_resultado": "erro"}

    # Usando a lógica de máscara que você confirmou que funciona
    mask = pd.Series(True, index=df.index)
    
    if uf: mask &= (df['uf'].str.upper() == uf.upper())
    if cidade: mask &= (df['cidade'].str.contains(cidade, case=False, na=False))
    if servico: mask &= (df['servico'] == servico)
    if interface: mask &= (df['interface'] == interface)
    if ip_fixo: mask &= (df['ip_fixo'] == ip_fixo)
    if capacidade: mask &= (df['capacidade_mb'] == capacidade)
    if vigencia: mask &= (df['vigencia_meses'] == vigencia)

    df_filtrado = df[mask]
    
    quantidade = int(len(df_filtrado))
    if quantidade == 0:
        return {"custo_medio": "Nenhuma opção localizada", "quantidade_contratos": 0, "tipo_resultado": "sem_dados"}
        
    return {
        "custo_medio": round(float(df_filtrado['valor_mensal'].mean()), 2),
        "quantidade_contratos": quantidade,
        "tipo_resultado": "especifico"
    }
    
@app.get("/filtros/opcoes")
async def get_opcoes():
    global DADOS_FIXOS
    if DADOS_FIXOS is None:
        DADOS_FIXOS = carregar_dados_do_banco()
    
    return {
        "servicos": DADOS_FIXOS['servico'].dropna().unique().tolist(),
        "interfaces": DADOS_FIXOS['interface'].dropna().unique().tolist(),
        "ips": DADOS_FIXOS['ip_fixo'].dropna().unique().tolist(),
        "cidades": DADOS_FIXOS['cidade'].dropna().unique().tolist()
    }