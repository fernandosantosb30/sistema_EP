# --- BIBLIOTECAS PADRÃO ---
import csv
import os
import unicodedata
import io

# --- BIBLIOTECAS DE TERCEIROS ---
import pandas as pd
from sqlalchemy import create_engine

# --- BIBLIOTECAS DJANGO ---
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.forms import modelform_factory
from django.db.models.functions import Lower, Replace, Trim

# --- MODELOS E FORMULÁRIOS LOCAIS ---
from .models import Provedor, Contato, CidadeAtendida
from .forms import ProvedorForm, ContatoForm, CidadeForm
from django.views.generic import ListView
from .models import Provedor

#Paginator 
class ListaProvedoresView(ListView):
    model = Provedor
    template_name = 'providers/lista_provedores.html'
    context_object_name = 'provedores'
    paginate_by = 10

# --- UTILS / CONFIGURAÇÕES ---
def get_db_engine():
    return create_engine(os.environ.get('DATABASE_URL'))

def get_form(model):
    return modelform_factory(model, fields="__all__")

def normalizar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).lower().replace('-', ' ').strip()

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
    # Otimização: prefetch_related carrega os contatos de uma vez
    provedores = Provedor.objects.prefetch_related('contatos').all().distinct()
    
    fornecedor = request.GET.get('fornecedor')
    uf = request.GET.get('uf')
    cidade1 = request.GET.get('cidade1')
    cidade2 = request.GET.get('cidade2')
    cidade3 = request.GET.get('cidade3')
    
    if fornecedor:
        provedores = provedores.filter(Q(nome__icontains=fornecedor) | Q(razao_social__icontains=fornecedor))
    
    if uf:
        provedores = provedores.filter(cidades__uf__iexact=uf)
        
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

# --- GESTÃO DE CUSTO MÉDIO (INTEGRADA) ---
@login_required
def processar_custo_medio(request):
    engine = get_db_engine()
    # Query original sem a coluna 'interface' que não existe no banco
    query = "SELECT cidade, uf, servico, valor_mensal, capacidade_mb, vigencia_meses, ip_fixo FROM public.providers_contratocusto"
    df = pd.read_sql(query, engine)
    
    # CRIAÇÃO DO FILTRO VIRTUAL
    def extrair_interface(texto):
        # Tudo aqui dentro DEVE estar com o mesmo recuo (4 espaços)
        texto = str(texto).upper()
        # Removendo acentos
        texto = unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')
        
        if 'FIBRA' in texto: 
            return 'Fibra'
        if 'WIRELESS' in texto or 'RADIO' in texto: 
            return 'Rádio'
        return 'Misto'

    # Aplica a função para criar a coluna 'interface' em memória
    df['interface'] = df['servico'].apply(extrair_interface)

    # 1. Carregamento inicial (sem filtros)
    if not request.GET.get('cidade') and not request.GET.get('uf') and not request.GET.get('servico'):
        context = {
            'servicos': sorted([s for s in df['servico'].unique() if s]),
            'vigencias': sorted([v for v in df['vigencia_meses'].unique() if pd.notnull(v)]),
            'ips_fixos': sorted([str(ip) for ip in df['ip_fixo'].unique() if pd.notnull(ip)]),
            'interfaces': sorted(df['interface'].unique()) 
        }
        return render(request, 'providers/custo_medio_integrado.html', context)

    # 2. Requisição de filtro (via JavaScript)
    try:
        # Primeiro, filtramos pelos critérios fixos (serviço, interface, etc.)
        mask_base = pd.Series(True, index=df.index)
        if request.GET.get('servico'): 
            mask_base &= (df['servico'] == request.GET.get('servico'))
        if request.GET.get('interface'):
            mask_base &= (df['interface'] == request.GET.get('interface'))
        if request.GET.get('ip_fixo'):
            mask_base &= (df['ip_fixo'].astype(str) == request.GET.get('ip_fixo'))
        if request.GET.get('capacidade'): 
            mask_base &= (df['capacidade_mb'] == int(request.GET.get('capacidade')))
        if request.GET.get('vigencia'): 
            mask_base &= (df['vigencia_meses'] == int(request.GET.get('vigencia')))

        # Tenta filtrar por Cidade e UF
        mask_cidade = mask_base.copy()
        if request.GET.get('uf'): 
            mask_cidade &= (df['uf'].str.upper() == request.GET.get('uf').upper())
        if request.GET.get('cidade'): 
            mask_cidade &= (df['cidade'].str.contains(request.GET.get('cidade'), case=False, na=False))
        
        df_filtrado = df[mask_cidade]

        # HIERARQUIA: Se não encontrar na cidade, tenta apenas pelo UF
        if len(df_filtrado) == 0 and request.GET.get('uf'):
            mask_uf = mask_base.copy()
            mask_uf &= (df['uf'].str.upper() == request.GET.get('uf').upper())
            df_filtrado = df[mask_uf]
            
        # Opcional: Se ainda assim não encontrar nada, você poderia remover 
        # o filtro de UF para pegar a média nacional/geral:
        # if len(df_filtrado) == 0: df_filtrado = df[mask_base]

        resultado = {
            'custo_medio': round(float(df_filtrado['valor_mensal'].mean()), 2) if not df_filtrado.empty else 0.00,
            'quantidade_contratos': int(len(df_filtrado)),
            'nivel': 'Cidade' if len(df[mask_cidade]) > 0 else ('Estado' if len(df_filtrado) > 0 else 'Geral')
        }
        return JsonResponse(resultado)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# --- Nova Função de Processamento em Lote (CSV) ---
@login_required
def processar_lote_csv(request):
    if request.method == 'POST' and request.FILES.get('arquivo_cidades'):
        arquivo = request.FILES['arquivo_cidades']
        try:
            # Leitura e normalização básica
            conteudo = arquivo.read().decode('utf-8', errors='ignore').replace('\r\n', '\n')
            df_input = pd.read_csv(io.StringIO(conteudo))
            df_input.columns = [c.lower().strip() for c in df_input.columns]
            
            # Validação
            colunas_esperadas = ['cidade', 'uf', 'servico', 'velocidade']
            if not all(col in df_input.columns for col in colunas_esperadas):
                return HttpResponse(f"Erro: O arquivo deve conter as colunas: {', '.join(colunas_esperadas)}")

            # Limpeza dos dados de entrada
            df_input['cidade'] = df_input['cidade'].astype(str).str.lower().str.strip()
            df_input['uf'] = df_input['uf'].astype(str).str.lower().str.strip()
            df_input['servico'] = df_input['servico'].astype(str).str.lower().str.strip()
            # Converte velocidade para int de forma segura
            df_input['capacidade_mb'] = pd.to_numeric(df_input['velocidade'], errors='coerce').fillna(-1).astype(int)

            # Busca dados do banco
            engine = get_db_engine()
            df_custos = pd.read_sql("SELECT cidade, uf, servico, valor_mensal, capacidade_mb FROM public.providers_contratocusto", engine)
            
            # Normaliza dados do banco
            df_custos['cidade'] = df_custos['cidade'].str.lower().str.strip()
            df_custos['uf'] = df_custos['uf'].str.lower().str.strip()
            df_custos['servico'] = df_custos['servico'].str.lower().str.strip()

            # OTIMIZAÇÃO: Usando merge em vez de loop for (muito mais rápido)
            df_merge = pd.merge(df_input, df_custos, on=['cidade', 'uf', 'servico', 'capacidade_mb'], how='left')
            
            # Agrupa para tirar a média por linha original do CSV
            df_resultado = df_merge.groupby(['cidade', 'uf', 'servico', 'velocidade'])['valor_mensal'].mean().reset_index()
            df_resultado.rename(columns={'valor_mensal': 'custo_medio'}, inplace=True)
            df_resultado['custo_medio'] = df_resultado['custo_medio'].fillna(0).round(2)

            # Gerar download
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="resultado_precificacao.csv"'
            df_resultado.to_csv(path_or_buf=response, index=False)
            return response
            
        except Exception as e:
            return HttpResponse(f"Erro ao processar: {e}")
            
    return HttpResponse("Erro: Arquivo não enviado ou formato inválido.")

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
    provedor = None
    if pk: # Apenas busca se um ID for fornecido
        provedor = get_object_or_404(Provedor, pk=pk)

    if request.method == 'POST':
        form = ProvedorForm(request.POST, instance=provedor)
        if form.is_valid():
            form.save()
            return redirect('lista_provedores')
    else:
        form = ProvedorForm(instance=provedor) # instance=None cria novo registro

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
    get_object_or_404(Contato, id=contato_id).delete()
    return redirect('lista_provedores')

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
    get_object_or_404(CidadeAtendida, id=cidade_id).delete()
    return redirect('lista_provedores')

@user_passes_test(e_admin)
@login_required
def excluir_todas_cidades(request, provedor_id):
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    return redirect('lista_provedores')

# --- IMPORTAÇÃO E MAPEAMENTO ---
@login_required
def importar_e_mapear_projeto(request):
    context = {}
    if request.method == 'POST' and request.FILES.get('arquivo_cidades'):
        try:
            arquivo = request.FILES['arquivo_cidades']
            df = pd.read_csv(arquivo, encoding='latin-1', sep=';', engine='python', header=0)
            
            resultado = []
            for _, row in df.iterrows():
                # 1. Limpa o nome do CSV (remove espaços extras)
                nome_cidade_csv = str(row['cidade']).strip().lower()
                if not nome_cidade_csv: continue
                
                # 2. Busca ignorando diferenças de formato no banco
                # Usamos Lower(Trim(cidade)) para normalizar os dados do banco na hora da consulta
                provedores = Provedor.objects.annotate(
                    cidade_limpa=Lower(Trim('cidadeatendida__cidade'))
                ).filter(cidade_limpa__icontains=nome_cidade_csv).distinct()
                
                for p in provedores:
                    if p not in resultado:
                        resultado.append(p)
            
            context['mapeamento'] = resultado
            if not resultado:
                messages.warning(request, "Nenhum provedor encontrado para as cidades listadas no arquivo.")
            else:
                messages.success(request, f"Mapeamento concluído! {len(resultado)} provedores encontrados.")
            
        except Exception as e:
            messages.error(request, f"Erro crítico: {str(e)}")
            
    return render(request, 'providers/consulta.html', context)

def normalizar_texto(texto):
    """Remove acentos, converte para maiúsculo e remove espaços extras."""
    if not texto or pd.isna(texto): return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    texto_limpo = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return texto_limpo.upper().strip()

@login_required
def importar_cidades_csv(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        try:
            csv_file = request.FILES['arquivo_csv']
            
            # Leitura robusta: aceita latin-1, qualquer separador e ignora linhas ruins
            df = pd.read_csv(
                csv_file, 
                encoding='latin-1', 
                sep=None, 
                engine='python', 
                on_bad_lines='skip'
            )
            
            novos = 0
            existentes = 0
            
            for _, row in df.iterrows():
                # Normaliza os dados usando a função de limpeza acima
                nome_cidade = normalizar_texto(row.iloc[0])
                uf_cidade = normalizar_texto(row.iloc[1]) if len(row) > 1 else "XX"
                
                if nome_cidade:
                    # Busca ou cria normalizando a busca também
                    obj, criado = CidadeAtendida.objects.get_or_create(
                        provedor=provedor, 
                        nome=nome_cidade, # Certifique-se que o campo no model é 'nome'
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