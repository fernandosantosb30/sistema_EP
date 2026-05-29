import os
import pandas as pd
from sqlalchemy import create_engine, text
from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# --- CONFIGURAÇÃO DE AMBIENTE ---
# No Render, BASE_DIR será a raiz do seu projeto
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app = FastAPI(title="API Custo Médio - Ep Conexões")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- CONEXÃO COM BANCO DE DADOS ---
# O Render injeta a DATABASE_URL. Se não achar, usamos uma string vazia para evitar crash
DATABASE_URL = os.environ.get("DATABASE_URL") 
engine = create_engine(DATABASE_URL) if DATABASE_URL else None

def carregar_dados_do_banco():
    if not engine: return None
    try:
        query = "SELECT cidade, uf, servico, ip_fixo, valor_mensal, capacidade_mb, vigencia_meses, interface FROM public.providers_contratocusto"
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
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
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- ROTAS DE NAVEGAÇÃO (LOGIN/HOME) ---
@app.get("/")
async def root():
    return RedirectResponse(url="/login")

@app.get("/login")
async def login_page(request: Request):
    return templates.TemplateResponse("registration/login.html", {"request": request})

@app.get("/home")
async def home_page(request: Request):
    # Aqui entraria a verificação de sessão/token futuramente
    return templates.TemplateResponse("providers/home.html", {"request": request})

# --- ROTAS DE API ---
@app.get("/api/custo-medio/")
async def get_custo_medio(
    cidade: str = None, uf: str = None, servico: str = None, 
    interface: str = None, ip_fixo: str = None, capacidade: int = None, 
    vigencia: int = None
):
    global DADOS_FIXOS
    if DADOS_FIXOS is None: DADOS_FIXOS = carregar_dados_do_banco()
    
    df = DADOS_FIXOS
    if df is None or df.empty:
        return {"custo_medio": 0, "quantidade_contratos": 0, "tipo_resultado": "erro"}

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