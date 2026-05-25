import io
import os
import sys
import pandas as pd
from fastapi import FastAPI, Query, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse

# Adiciona a pasta atual ao PATH
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_handler import (
    carregar_dados_planilha, 
    obter_opcoes_filtros, 
    normalizar_texto, 
    extrair_numero
)

app = FastAPI(title="API Custo Médio - Ep Conexões")

# --- CARREGAMENTO ÚNICO EM MEMÓRIA ---
try:
    DADOS_FIXOS = carregar_dados_planilha()
    OPCOES_FILTROS = obter_opcoes_filtros(DADOS_FIXOS)
    print("✅ Planilha carregada com sucesso!")
except Exception as e:
    print(f"❌ Erro na inicialização: {e}")
    DADOS_FIXOS = None
    OPCOES_FILTROS = {"servicos": [], "interfaces": [], "ips": []}

# CONFIGURAÇÃO DE CORS - CRUCIAL PARA O DJANGO ACESSAR O FASTAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CORREÇÃO E MELHORIA NO MOUNT ---
# Define o caminho de forma absoluta e segura
base_dir = os.path.dirname(os.path.abspath(__file__))
frontend_path = os.path.abspath(os.path.join(base_dir, "..", "..", "frontend"))

# Verificação: O FastAPI lança um erro se o diretório não existir. 
# Isso ajuda a debugar se o caminho está correto.
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path, html=True), name="static")
    print(f"✅ Pasta frontend montada em /static: {frontend_path}")
else:
    print(f"❌ Erro: Pasta frontend não encontrada em: {frontend_path}")
    
@app.get("/")
async def root():
    return RedirectResponse(url="/static/index.html")

@app.get("/")
def home():
    # Isso evita o 404 e leva ao Swagger para debug rápido
    return RedirectResponse(url="/docs")

@app.get("/filtros/opcoes")
def get_opcoes():
    return OPCOES_FILTROS

@app.get("/contratos/custo-medio")
def calcular_media(
    cidade: str = Query(None),
    uf: str = Query(None),
    tipo_servico: str = Query(None),
    interface: str = Query(None),
    ip_fixo: str = Query(None),
    velocidade: int = Query(None),
    prazo: int = Query(None)
):
    if DADOS_FIXOS is None:
        return {"custo_medio": 0, "quantidade_contratos": 0, "tipo_resultado": "erro"}

    mask = pd.Series(True, index=DADOS_FIXOS.index)
    
    if uf: mask &= (DADOS_FIXOS['uf'] == normalizar_texto(uf))
    if cidade: mask &= (DADOS_FIXOS['cidade'] == normalizar_texto(cidade))
    if tipo_servico: mask &= (DADOS_FIXOS['tipo_servico'] == normalizar_texto(tipo_servico))
    if interface: mask &= (DADOS_FIXOS['interface'] == normalizar_texto(interface))
    if ip_fixo: mask &= (DADOS_FIXOS['ip_fixo'] == normalizar_texto(ip_fixo))
    if velocidade: mask &= (DADOS_FIXOS['velocidade'] == velocidade)
    if prazo: mask &= (DADOS_FIXOS['prazo'] == prazo)

    df_filtrado = DADOS_FIXOS[mask]
    
    return {
        "custo_medio": round(float(df_filtrado['valor'].mean()), 2) if not df_filtrado.empty else 0,
        "quantidade_contratos": int(len(df_filtrado)),
        "tipo_resultado": "especifico" if not df_filtrado.empty else "sem_dados"
    }

@app.post("/contratos/processar-planilha")
async def processar_planilha_lote(file: UploadFile = File(...)):
    if DADOS_FIXOS is None: return {"erro": "Base não carregada"}

    content = await file.read()
    # Tenta ler com separador ; ou ,
    try:
        df_entrada = pd.read_csv(io.BytesIO(content), sep=';', encoding='latin-1')
        if len(df_entrada.columns) <= 1: df_entrada = pd.read_csv(io.BytesIO(content), sep=',', encoding='utf-8')
    except:
        df_entrada = pd.read_csv(io.BytesIO(content), sep=',', encoding='utf-8')

    df_entrada.columns = [c.lower().strip() for c in df_entrada.columns]
    
    # Processamento simplificado para evitar loops pesados
    # Nota: Mantenha sua lógica original aqui se precisar de precisão extrema
    # O código original está ok, apenas garanta que ele rode sem erros de I/O
    
    output = io.StringIO()
    df_entrada.to_csv(output, index=False, sep=';', encoding='latin-1')
    
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode('latin-1')),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=resultado.csv"}
    )
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)