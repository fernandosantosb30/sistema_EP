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
    query = "SELECT cidade, uf, servico, valor_mensal, capacidade_mb, vigencia_meses FROM public.providers_contratocusto"
    df = pd.read_sql(query, engine)

    # 1. Se for apenas o carregamento inicial da página (sem parâmetros GET)
    if not request.GET.get('cidade') and not request.GET.get('uf') and not request.GET.get('servico'):
        context = {
            'servicos': sorted([s for s in df['servico'].unique() if s]),
            'vigencias': sorted([v for v in df['vigencia_meses'].unique() if pd.notnull(v)]),
            'ips_fixos': sorted([str(ip) for ip in df['ip_fixo'].unique() if pd.notnull(ip)])
        }
        return render(request, 'providers/custo_medio_integrado.html', context)

    # 2. Se for uma requisição de filtro (via JavaScript fetch)
    try:
        mask = pd.Series(True, index=df.index)
        
        if request.GET.get('uf'): 
            mask &= (df['uf'].str.upper() == request.GET.get('uf').upper())
        if request.GET.get('cidade'): 
            mask &= (df['cidade'].str.contains(request.GET.get('cidade'), case=False, na=False))
        if request.GET.get('servico'): 
            mask &= (df['servico'] == request.GET.get('servico'))
        if request.GET.get('ip_fixo'):
            mask &= (df['ip_fixo'].astype(str) == request.GET.get('ip_fixo'))
        if request.GET.get('capacidade'): 
            mask &= (df['capacidade_mb'] == int(request.GET.get('capacidade')))
        if request.GET.get('vigencia'): 
            mask &= (df['vigencia_meses'] == int(request.GET.get('vigencia')))
        
        
        df_filtrado = df[mask]
        
        resultado = {
            'custo_medio': round(float(df_filtrado['valor_mensal'].mean()), 2) if not df_filtrado.empty else 0.00,
            'quantidade_contratos': int(len(df_filtrado))
        }
        return JsonResponse(resultado)

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
            df = pd.read_csv(arquivo, sep=None, engine='python')
            
            # Limpeza básica das colunas
            df.columns = [c.strip() for c in df.columns]
            
            # OTIMIZAÇÃO: Carrega todos os provedores de uma vez para um dicionário (chave: nome minúsculo)
            # Isso evita consultar o banco a cada linha do CSV
            provedores_dict = {p.nome.lower(): p for p in Provedor.objects.all()}
            
            resultado = []
            for _, row in df.iterrows():
                # Tenta pegar as colunas de forma genérica
                nome_fornecedor = str(row.iloc[0]).strip()
                contato = str(row.iloc[1]).strip() if len(row) > 1 else ""
                
                # Busca no dicionário em memória (rápido)
                provedor = provedores_dict.get(nome_fornecedor.lower())
                
                # Verifica o campo conforme definido no seu modelo
                trunk_status = "BST" if provedor and getattr(provedor, 'parceiro_bst', False) else ""
                
                resultado.append({
                    'fornecedor': nome_fornecedor,
                    'contato': contato,
                    'trunk': trunk_status
                })
            
            context['mapeamento'] = resultado
            messages.success(request, "Arquivo mapeado com sucesso!")
            
        except Exception as e:
            messages.error(request, f"Erro ao processar arquivo: {e}")
            
    return render(request, 'providers/consulta.html', context)

@login_required
def importar_cidades_csv(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        try:
            csv_file = request.FILES['arquivo_csv']
            # O engine='python' com sep=None detecta automaticamente o separador (vírgula, ponto e vírgula, etc.)
            df = pd.read_csv(csv_file, sep=None, engine='python')
            
            novos = 0
            existentes = 0
            
            for _, row in df.iterrows():
                # Normaliza para string, remove espaços extras e transforma em maiúsculas
                nome_cidade = str(row.iloc[0]).strip().upper()
                # Assume que a segunda coluna é a UF, se existir
                uf_cidade = str(row.iloc[1]).strip().upper() if len(row) > 1 else "XX"
                
                if nome_cidade:
                    # Tenta buscar ou criar: se já existir a combinação provedor + nome + uf, ele ignora
                    obj, criado = CidadeAtendida.objects.get_or_create(
                        provedor=provedor, 
                        nome=nome_cidade,
                        uf=uf_cidade
                    )
                    
                    if criado:
                        novos += 1
                    else:
                        existentes += 1
            
            messages.success(request, f"Importação concluída: {novos} novas cidades adicionadas. ({existentes} já existiam e foram ignoradas).")
            
        except Exception as e:
            messages.error(request, f"Erro ao processar o arquivo: {str(e)}")
            
    # Redireciona de volta para a tela de edição do provedor para que o usuário veja o resultado
    return redirect('editar_provedor', pk=provedor.id)