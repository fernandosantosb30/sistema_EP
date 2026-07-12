# --- BIBLIOTECAS PADRÃO ---
import csv
import io
import os
import unicodedata
import json
import re

# --- BIBLIOTECAS DE TERCEIROS ---
import pandas as pd
from difflib import get_close_matches
import difflib
import logging
logger = logging.getLogger(__name__)

# --- BIBLIOTECAS DJANGO ---
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import connection 
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.forms import modelform_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView

# --- IMPORTAÇÃO DA FUNÇÃO NORMALIZAR_TEXTO ---
from .utils import normalizar_texto 

# --- MODELOS E FORMULÁRIOS LOCAIS ---
from .forms import ProvedorForm, ContatoForm, CidadeForm
from .models import InboxContrato, ContratoCusto, Provedor, Contato, CidadeAtendida

def buscar_custo(row):
    """
    Busca o custo médio usando o ORM do Django de forma segura.
    Atualizado para a nova estrutura do modelo ContratoCusto.
    """
    try:
        # Usamos ContratoCusto (Classe) e os novos nomes dos campos
        custo = ContratoCusto.objects.filter(
            cidade__iexact=row.get('cidade_norm'),
            uf__iexact=row.get('uf'),
            tipo_servico__iexact=row.get('servico'),
            velocidade=row.get('capacidade_mb')
        ).first()
        
        # Verificação de segurança utilizando o campo 'mensal'
        if custo and custo.mensal:
            return float(custo.mensal)
        return 0.0
        
    except Exception as e:
        logger.error(f"Erro ao buscar custo para {row.get('cidade')}: {e}")
        return 0.0

#Paginator 
class ListaProvedoresView(ListView):
    model = Provedor
    template_name = 'providers/lista_provedores.html'
    context_object_name = 'provedores'
    paginate_by = 10

# --- UTILS / CONFIGURAÇÕES ---

def get_form(model):
    return modelform_factory(model, fields="__all__")

# --- GESTÃO DE ACESSO (ADMIN) ---
def e_admin(user):
    return user.is_superuser

@user_passes_test(e_admin)
def gestao_usuarios(request):
    return render(request, 'registration/gestao_usuarios.html', {'usuarios': User.objects.all()})

@user_passes_test(e_admin)
def criar_usuario(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário criado!")
            return redirect('gestao_usuarios')
    return render(request, 'registration/usuario_form.html', {'form': UserCreationForm(), 'titulo': 'Novo Usuário'})

@user_passes_test(e_admin)
def alterar_senha(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        form = SetPasswordForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Senha alterada!")
            return redirect('gestao_usuarios')
    return render(request, 'registration/usuario_form.html', {'form': SetPasswordForm(usuario), 'titulo': 'Alterar Senha'})

@user_passes_test(e_admin)
def excluir_usuario(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario.username != request.user.username:
        usuario.delete()
    return redirect('gestao_usuarios')

# --- NAVEGAÇÃO E LISTAGENS ---

@login_required
def home_view(request):
    return render(request, 'providers/home.html')

@login_required
def lista_provedores(request):
    # 1. Pega o termo de busca da URL
    query = request.GET.get('q')
    
    # 2. Inicia o queryset com todos os objetos
    queryset = Provedor.objects.all()
    
    # 3. Se houver algo na busca, filtra o queryset
    if query:
        # Filtra pelo nome (ajuste o campo se necessário, ex: nome__icontains)
        queryset = queryset.filter(nome__icontains=query)
    
    # 4. Ordena após filtrar
    queryset = queryset.order_by('-id')
    
    # 5. Aplica a paginação no queryset JÁ FILTRADO
    paginator = Paginator(queryset, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    return render(request, 'providers/lista.html', {
        'page_obj': page_obj,
        'total_registros': queryset.count() # Agora mostra o total da busca
    })

@login_required
def consulta_provedores(request):
    # Otimização: carregamos também 'cidades' para evitar consultas extras ao banco
    provedores = Provedor.objects.prefetch_related('contatos', 'cidades').all().distinct()
    
    # Captura e normalização das entradas
    fornecedor = request.GET.get('fornecedor')
    uf = request.GET.get('uf', '').strip().upper()
    cidade1 = normalizar_texto(request.GET.get('cidade1'))
    cidade2 = normalizar_texto(request.GET.get('cidade2'))
    cidade3 = normalizar_texto(request.GET.get('cidade3'))
    
    # Filtros
    if fornecedor:
        provedores = provedores.filter(Q(nome__icontains=fornecedor) | Q(razao_social__icontains=fornecedor))
    
    if uf:
        provedores = provedores.filter(cidades__uf__iexact=uf)
        
    # As consultas de cidade agora usam o termo normalizado
    if cidade1:
        provedores = provedores.filter(cidades__nome__icontains=cidade1)
    if cidade2:
        provedores = provedores.filter(cidades__nome__icontains=cidade2)
    if cidade3:
        provedores = provedores.filter(cidades__nome__icontains=cidade3)
    
    context = {
        'mapeamento': provedores
    }
    
    return render(request, 'providers/consulta.html', context)



@login_required
def processar_custo_medio(request):
    try:

        # ==========================================================
        # CARREGA DADOS DO BANCO
        # ==========================================================
        queryset = ContratoCusto.objects.values(
            "cidade",
            "uf",
            "tipo_servico",
            "mensal",
            "velocidade",
            "meio_fisico"
        )

        df = pd.DataFrame(queryset)

        if df.empty:

            dados = {
                "custo_medio": 0,
                "quantidade_contratos": 0,
                "nivel": "Sem dados"
            }

            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse(dados)

            return render(
                request,
                "providers/custo_medio_integrado.html",
                {
                    "dados": dados,
                    "servicos": [],
                    "velocidades": [],
                    "meios_fisicos": []
                }
            )

        # ==========================================================
        # NORMALIZAÇÃO DOS DADOS
        # ==========================================================

        df["cidade"] = (
            df["cidade"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["uf"] = (
            df["uf"]
            .fillna("")
            .astype(str)
            .str.upper()
            .str.strip()
        )

        df["tipo_servico"] = (
            df["tipo_servico"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["meio_fisico"] = (
            df["meio_fisico"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["velocidade"] = (
            df["velocidade"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        df["mensal"] = pd.to_numeric(
            df["mensal"],
            errors="coerce"
        ).fillna(0)

        # ==========================================================
        # COLUNAS NORMALIZADAS
        # ==========================================================

        df["cidade_norm"] = df["cidade"].apply(normalizar_texto)

        df["tipo_servico_norm"] = df["tipo_servico"].apply(normalizar_texto)

        df["meio_fisico_norm"] = df["meio_fisico"].apply(normalizar_texto)

        # pega apenas o número da velocidade
        def limpar_velocidade(valor):

            numeros = re.findall(r"\d+", str(valor))

            if numeros:
                return numeros[0]

            return ""

        df["velocidade_norm"] = df["velocidade"].apply(limpar_velocidade)

        # ==========================================================
        # LOGS
        # ==========================================================

        print("=" * 60)
        print("TOTAL REGISTROS:", len(df))
        print("GET:", request.GET)
        print("=" * 60)

        # ==========================================================
        # FILTROS
        # ==========================================================

        mask = pd.Series(True, index=df.index)

        servico = request.GET.get("servico", "").strip()

        if servico:
            mask &= (
                df["tipo_servico_norm"] ==
                normalizar_texto(servico)
            )

        meio = request.GET.get("meio_fisico", "").strip()

        if meio:
            mask &= (
                df["meio_fisico_norm"] ==
                normalizar_texto(meio)
            )

        velocidade = request.GET.get("velocidade", "").strip()

        if velocidade:
            mask &= (
                df["velocidade_norm"] ==
                limpar_velocidade(velocidade)
            )

        df_base = df[mask]

        print("Após filtros:", len(df_base))

        # ==========================================================
        # FILTRO GEOGRÁFICO
        # ==========================================================

        cidade = request.GET.get("cidade", "").strip()

        uf = request.GET.get("uf", "").strip().upper()

        df_final = df_base.copy()

        nivel = "Geral"

        if cidade:

            cidade_normalizada = normalizar_texto(cidade)

            lista = df_base["cidade_norm"].unique().tolist()

            match = difflib.get_close_matches(
                cidade_normalizada,
                lista,
                n=1,
                cutoff=0.75
            )

            if match:

                df_final = df_base[
                    df_base["cidade_norm"] == match[0]
                ]

                nivel = "Cidade"

        elif uf:

            df_final = df_base[
                df_base["uf"] == uf
            ]

            nivel = "Estado"

        print("Após geografia:", len(df_final))

        # ==========================================================
        # RESULTADO
        # ==========================================================

        media = 0

        if not df_final.empty:
            media = float(df_final["mensal"].mean())

        dados = {
            "custo_medio": round(media, 2),
            "quantidade_contratos": int(len(df_final)),
            "nivel": nivel
        }

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse(dados)

        context = {
            "dados": dados,
            "servicos": sorted(df["tipo_servico"].dropna().unique()),
            "velocidades": sorted(df["velocidade"].dropna().unique()),
            "meios_fisicos": sorted(df["meio_fisico"].dropna().unique())
        }

        return render(
            request,
            "providers/custo_medio_integrado.html",
            context
        )

    except Exception as e:

        import traceback

        traceback.print_exc()

        return JsonResponse(
            {"error": str(e)},
            status=500
        )

# --- Nova Função de Processamento em Lote (CSV) ---
@login_required
def processar_lote_csv(request):
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        arquivo = request.FILES['arquivo_csv']
        try:
            # 1. LEITURA ROBUSTA
            raw_data = arquivo.read()
            conteudo = None
            for encoding in ['utf-8-sig', 'latin-1', 'cp1252', 'cp850']:
                try:
                    conteudo = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if conteudo is None:
                raise ValueError("Formato de arquivo incompatível. Tente salvar como UTF-8.")

            # 2. CARREGA O CSV DO USUÁRIO
            df_input = pd.read_csv(io.StringIO(conteudo), sep=None, engine='python', on_bad_lines='skip')
            df_input.columns = [c.lower().strip() for c in df_input.columns]
            
            # 3. CARREGA BASE DE DADOS DO DJANGO
            # Atualizado para ContratoCusto e novos nomes de colunas
            contratos_db = ContratoCusto.objects.all().values(
                'cidade', 'uf', 'tipo_servico', 'mensal', 'velocidade', 'meio_fisico'
            )
            df_db = pd.DataFrame(list(contratos_db))
            
            # Normalização do Banco
            df_db['cidade_norm'] = df_db['cidade'].apply(lambda x: normalizar_texto(x) if x else "")
            df_db['servico_norm'] = df_db['tipo_servico'].apply(lambda x: normalizar_texto(x) if x else "")
            df_db['uf'] = df_db['uf'].astype(str).str.upper().str.strip()
            df_db['mensal'] = pd.to_numeric(df_db['mensal'], errors='coerce')

            # Prepara entrada do usuário (ajuste para os campos do CSV)
            df_input['cidade_norm'] = df_input['cidade'].apply(lambda x: normalizar_texto(x) if x else "")
            df_input['servico_norm'] = df_input['tipo_servico'].apply(lambda x: normalizar_texto(x) if x else "")
            df_input['uf'] = df_input['uf'].astype(str).str.upper().str.strip()
            
            # Garante que a velocidade seja tratada como string para comparação
            df_input['velocidade_str'] = df_input['velocidade'].astype(str).str.strip()
            df_db['velocidade_str'] = df_db['velocidade'].astype(str).str.strip()

            # 4. LÓGICA DE CÁLCULO
            def calcular_custo(row):
                # Filtro comum: Serviço e Velocidade
                mask = (df_db['servico_norm'] == row['servico_norm']) & \
                       (df_db['velocidade_str'] == row['velocidade_str'])
                
                # Nível 1: Cidade
                match_cidade = df_db[mask & (df_db['cidade_norm'] == row['cidade_norm'])]
                if not match_cidade.empty:
                    return match_cidade['mensal'].mean()
                
                # Nível 2: Estado
                match_estado = df_db[mask & (df_db['uf'] == row['uf'])]
                if not match_estado.empty:
                    return match_estado['mensal'].mean()
                
                return None

            df_input['custo_medio'] = df_input.apply(calcular_custo, axis=1)
            
            # Tratamento final
            df_input = df_input.dropna(subset=['cidade', 'tipo_servico'])
            df_input['custo_medio'] = df_input['custo_medio'].fillna('Não encontrado')
            
            # 5. EXPORTAÇÃO
            cols_export = ['cidade', 'uf', 'tipo_servico', 'velocidade', 'custo_medio']
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="resultado_precificacao.csv"'
            
            df_input[cols_export].to_csv(path_or_buf=response, index=False, encoding='utf-8-sig', sep=';')
            return response
            
        except Exception as e:
            logger.exception("Erro crítico no processamento de lote:")
            return HttpResponse(f"Erro ao processar arquivo: {str(e)}", status=500)
            
    return HttpResponse("Erro: Método inválido ou arquivo não enviado.", status=400)

def get_provedor_form(): return modelform_factory(Provedor, fields="__all__")
def get_contato_form(): return modelform_factory(Contato, fields="__all__")
def get_cidade_form(): return modelform_factory(CidadeAtendida, fields="__all__")

@user_passes_test(e_admin) # Apenas ADMIN pode excluir
@login_required
def excluir_provedor(request, pk):
    get_object_or_404(Provedor, pk=pk).delete()
    return redirect('lista_provedores')

# --- GESTÃO DE CONTATOS ---

@login_required
def adicionar_contato(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    if request.method == 'POST':
        form = ContatoForm(request.POST) # Usa a classe importada!
        if form.is_valid():
            contato = form.save(commit=False)
            contato.provedor = provedor
            contato.save()
    return redirect('editar_provedor', pk=provedor.id)

@login_required
def editar_provedor(request, pk=None):
    provedor = get_object_or_404(Provedor, pk=pk) if pk else None

    if request.method == 'POST':
        form = ProvedorForm(request.POST, instance=provedor)
        if form.is_valid():
            form.save()
            messages.success(request, "Provedor salvo com sucesso!")
            return redirect('lista_provedores')
        else:
            # ADICIONE ISTO para ver os erros no seu console ou terminal:
            print(form.errors) 
            messages.error(request, f"Erro ao salvar: {form.errors}")
    else:
        form = ProvedorForm(instance=provedor)

    form_cidade = CidadeForm() 
    form_contato = ContatoForm()
    
    return render(request, 'providers/cadastro_edit.html', {
        'form': form,
        'provedor': provedor,
        'form_cidade': form_cidade, # IMPORTANTE
        'form_contato': form_contato, # IMPORTANTE
    })

@user_passes_test(e_admin)
@login_required
def excluir_contato(request, contato_id):
    # Primeiro, recuperamos o contato para saber quem é o dono (o provedor)
    contato = get_object_or_404(Contato, id=contato_id)
    provedor_id = contato.provedor.id
    
    # Excluímos o contato
    contato.delete()
    
    # Redirecionamos para a tela de edição do provedor específico
    return redirect('editar_provedor', pk=provedor_id)

# --- GESTÃO DE CIDADES ---

@login_required
def adicionar_cidade(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    CidadeForm = modelform_factory(CidadeAtendida, fields=['nome', 'uf'])
    
    if request.method == 'POST':
        form = CidadeForm(request.POST)
        if form.is_valid():
            cidade = form.save(commit=False)
            cidade.provedor = provedor
            cidade.save()
            # Volta para a edição do mesmo provedor
            return redirect('editar_provedor', pk=provedor.id)
            
    return redirect('editar_provedor', pk=provedor.id)

@user_passes_test(e_admin)
@login_required
def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    provedor_id = cidade.provedor.id # Captura o ID do provedor dono da cidade
    cidade.delete()
    
    # Redireciona de volta para o cadastro do provedor
    return redirect('editar_provedor', pk=provedor_id)

@user_passes_test(e_admin)
@login_required
def excluir_todas_cidades(request, provedor_id):
    # Deleta apenas as cidades relacionadas ao provedor informado
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    
    # Redireciona de volta para o cadastro do provedor
    return redirect('editar_provedor', pk=provedor_id)

# --- IMPORTAÇÃO E MAPEAMENTO ---
@login_required
def importar_mapeamento(request):
    if request.method == 'POST' and request.FILES.get('arquivo_cidades'):
        try:
            arquivo = request.FILES['arquivo_cidades']
            raw_data = arquivo.read()
            
            # 1. Decodificação robusta
            conteudo = None
            for encoding in ['utf-8-sig', 'latin-1', 'cp850', 'cp1252']:
                try:
                    conteudo = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if conteudo is None:
                raise ValueError("Formato de arquivo não suportado. Tente salvar como UTF-8.")

            # 2. Carregar DataFrame
            df = pd.read_csv(io.StringIO(conteudo), sep=None, engine='python', on_bad_lines='skip')
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            if 'cidade' not in df.columns or 'uf' not in df.columns:
                raise ValueError("O arquivo deve conter as colunas 'cidade' e 'uf'.")

            # 3. Preparar dados do banco: Chave composta (cidade_norm, uf)
            todas_cidades = CidadeAtendida.objects.select_related('provedor').all()
            # Criamos um mapa usando tupla (cidade, uf) como chave
            mapa_cidades = {
                (normalizar_texto(c.nome), c.uf.strip().upper()): c 
                for c in todas_cidades
            }

            # 4. Preparar resposta
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="mapeamento_filtrado.csv"'
            writer = csv.writer(response, delimiter=';')
            writer.writerow(['Cidade', 'UF', 'Parceiro', 'Contato', 'Trunk'])
            
            encontrou_algum = False
            
            # 5. Processamento linha por linha
            for _, row in df.iterrows():
                cidade_input = normalizar_texto(str(row['cidade']))
                uf_input = str(row['uf']).strip().upper()[:2]
                
                if not cidade_input or not uf_input: 
                    continue
                
                # Busca exata usando a chave composta
                chave_busca = (cidade_input, uf_input)
                
                if chave_busca in mapa_cidades:
                    cidade_obj = mapa_cidades[chave_busca]
                    p = cidade_obj.provedor
                    contato = p.contatos.first()
                    
                    writer.writerow([
                        cidade_obj.nome,
                        cidade_obj.uf,
                        p.nome,
                        f"{contato.nome} ({contato.telefone})" if contato else "N/A",
                        'Sim' if getattr(p, 'parceiro_bst', False) else 'Não'
                    ])
                    encontrou_algum = True
            
            if not encontrou_algum:
                messages.warning(request, "Nenhum mapeamento encontrado para as cidades/UF informadas.")
                return redirect('consulta_provedores')

            return response
            
        except Exception as e:
            messages.error(request, f"Erro ao processar: {str(e)}")
            return redirect('consulta_provedores')
            
    return render(request, 'providers/consulta.html')

def exportar_mapeamento_csv(request, resultado):
    """
    Exporta uma lista de provedores para CSV, tratando corretamente 
    a codificação para leitura no Excel (UTF-8 com BOM).
    """
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="mapeamento_parceiros.csv"'

    writer = csv.writer(response, delimiter=';')
    
    # Cabeçalho
    writer.writerow(['Cidade', 'UF', 'Parceiro', 'Contato', 'Trunk'])

    # Otimização: prefetch_related evita múltiplas consultas ao banco (N+1 problema)
    # Certifique-se de passar o 'resultado' já com prefetch, ex: resultado.prefetch_related('cidades', 'contatos')
    
    for p in resultado:
        cidades = p.cidades.all()
        
        # Pula provedores sem cidades cadastradas
        if not cidades:
            continue
            
        # Otimização: busca o contato uma única vez por provedor
        contato_obj = p.contatos.first()
        nome_contato = f"{contato_obj.nome} ({contato_obj.telefone})" if contato_obj else "N/A"
        trunk_status = 'Sim' if getattr(p, 'parceiro_bst', False) else 'Não'
            
        for cidade in cidades:
            writer.writerow([
                cidade.nome,
                cidade.uf.upper() if cidade.uf else "XX", # Garante formato consistente
                p.nome,
                nome_contato,
                trunk_status
            ])
            
    return response

@login_required
def importar_cidades_csv(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        try:
            arquivo = request.FILES['arquivo_csv']
            
            # 1. LEITURA ROBUSTA (Tratamento de codificação para qualquer caractere)
            raw_data = arquivo.read()
            conteudo = None
            # Tenta decodificar usando encodings comuns de arquivos MS-DOS/Windows
            for encoding in ['utf-8-sig', 'latin-1', 'cp1252', 'cp850']:
                try:
                    conteudo = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if conteudo is None:
                raise ValueError("Formato de arquivo incompatível. Tente salvar como UTF-8 ou Latin-1.")

            # 2. CARREGA O CSV COM O PANDAS
            # O io.StringIO transforma a string decodificada em um arquivo virtual legível pelo Pandas
            df = pd.read_csv(
                io.StringIO(conteudo), 
                sep=None, 
                engine='python', 
                on_bad_lines='skip'
            )
            
            novos = 0
            existentes = 0
            
            for _, row in df.iterrows():
                # 3. NORMALIZAÇÃO DE DADOS
                # Garante que campos vazios ou nulos sejam tratados
                cidade_bruta = str(row.iloc[0]) if pd.notnull(row.iloc[0]) else ""
                nome_cidade = normalizar_texto(cidade_bruta)
                
                uf_raw = str(row.iloc[1]) if len(row) > 1 and pd.notnull(row.iloc[1]) else "XX"
                uf_cidade = uf_raw.strip().upper()[:2]
                
                if nome_cidade:
                    obj, criado = CidadeAtendida.objects.get_or_create(
                        provedor=provedor, 
                        nome=nome_cidade,
                        uf=uf_cidade
                    )
                    
                    if criado:
                        novos += 1
                    else:
                        existentes += 1
            
            messages.success(request, f"Importação concluída: {novos} novas cidades. ({existentes} já existiam).")
            
        except Exception as e:
            messages.error(request, f"Erro ao processar o arquivo: {str(e)}")
            
    return redirect('editar_provedor', pk=provedor.id)

@login_required
def interface_coleta(request):
    """
    Renderiza a interface para coleta de novos contratos.
    """
    context = {
        'titulo': 'Coleta de Dados de Contratos',
    }
    return render(request, 'providers/interface_coleta.html', context)

@login_required
def processar_item(request, inbox_id):
    """
    Processa um item da InboxContrato.
    """
    item = get_object_or_404(InboxContrato, id=inbox_id)
    
    # Adicione aqui sua lógica de processamento (ex: chamar a IA, salvar no ContratoCusto, etc.)
    # ...
    
    # Exemplo de redirecionamento após processar
    return redirect('coleta_dados') # Ajuste para a URL desejada