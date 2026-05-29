# --- BIBLIOTECAS PADRÃO ---
import csv
import os
import unicodedata

# --- BIBLIOTECAS DE TERCEIROS ---
import pandas as pd
from sqlalchemy import create_engine
from django.forms import modelform_factory

# --- BIBLIOTECAS DJANGO ---
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404, redirect

# --- MODELOS LOCAIS ---
from .models import Provedor, Contato, CidadeAtendida

# --- UTILS / CONFIGURAÇÕES ---
def get_db_engine():
    return create_engine(os.environ.get('DATABASE_URL'))

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
    query = request.GET.get('q', '').strip()
    queryset = Provedor.objects.all().order_by('-data_cadastro')
    if query:
        queryset = queryset.filter(Q(nome__icontains=query) | Q(razao_social__icontains=query))
    
    paginator = Paginator(queryset, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'providers/lista.html', {'provedores': page_obj, 'total_registros': queryset.count()})

@login_required
def consulta_provedores(request):
    fornecedor = request.GET.get('fornecedor', '').strip()
    uf = request.GET.get('uf', '').strip()
    cidades = [request.GET.get(f'cidade{i}', '').strip() for i in range(1, 4)]

    queryset = Provedor.objects.filter(ativo=True)
    if fornecedor:
        queryset = queryset.filter(Q(nome__icontains=fornecedor) | Q(razao_social__icontains=fornecedor))
    if uf:
        queryset = queryset.filter(cidades__uf__iexact=uf)
    
    filtros_cidade = Q()
    for c in cidades:
        if c: filtros_cidade |= Q(cidades__nome__icontains=c)
    
    return render(request, 'providers/consulta.html', {'provedores': queryset.filter(filtros_cidade).distinct()})

# --- GESTÃO DE CUSTO MÉDIO (INTEGRADA) ---

@login_required
def processar_custo_medio(request):
    context = {}
    if not request.GET:
        return render(request, 'providers/custo_medio_integrado.html', context)

    try:
        engine = get_db_engine()
        query = "SELECT cidade, uf, servico, valor_mensal, capacidade_mb, vigencia_meses FROM public.providers_contratocusto"
        df = pd.read_sql(query, engine)

        mask = pd.Series(True, index=df.index)
        if request.GET.get('uf'): mask &= (df['uf'].str.upper() == request.GET.get('uf').upper())
        if request.GET.get('cidade'): mask &= (df['cidade'].str.contains(request.GET.get('cidade'), case=False, na=False))
        if request.GET.get('servico'): mask &= (df['servico'] == request.GET.get('servico'))
        if request.GET.get('capacidade'): mask &= (df['capacidade_mb'] == int(request.GET.get('capacidade')))
        if request.GET.get('vigencia'): mask &= (df['vigencia_meses'] == int(request.GET.get('vigencia')))

        df_filtrado = df[mask]
        if not df_filtrado.empty:
            context.update({'custo_medio': round(float(df_filtrado['valor_mensal'].mean()), 2), 'quantidade_contratos': len(df_filtrado)})
        else:
            context['mensagem_erro'] = "Nenhum contrato encontrado."
    except Exception as e:
        context['mensagem_erro'] = f"Erro ao processar dados: {e}"

    return render(request, 'providers/custo_medio_integrado.html', context)

ProvedorForm = modelform_factory(Provedor, fields="__all__")
ContatoForm = modelform_factory(Contato, fields="__all__")
CidadeAtendidaForm = modelform_factory(CidadeAtendida, fields="__all__")

@login_required
def editar_provedor(request, pk=None):
    provedor = get_object_or_404(Provedor, pk=pk) if pk else Provedor()
    if request.method == 'POST':
        form = ProvedorForm(request.POST, instance=provedor)
        if form.is_valid():
            form.save()
            return redirect('lista_provedores')
    else:
        form = ProvedorForm(instance=provedor)
    return render(request, 'providers/provedor_form.html', {'form': form})

@login_required
def excluir_provedor(request, pk):
    provedor = get_object_or_404(Provedor, pk=pk)
    provedor.delete()
    return redirect('lista_provedores')

# --- GESTÃO DE CONTATOS ---

@login_required
def adicionar_contato(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    if request.method == 'POST':
        form = ContatoForm(request.POST)
        if form.is_valid():
            contato = form.save(commit=False)
            contato.provedor = provedor
            contato.save()
            return redirect('lista_provedores')
    return render(request, 'providers/contato_form.html', {'form': ContatoForm()})

@login_required
def editar_contato(request, contato_id):
    contato = get_object_or_404(Contato, id=contato_id)
    if request.method == 'POST':
        form = ContatoForm(request.POST, instance=contato)
        if form.is_valid():
            form.save()
            return redirect('lista_provedores')
    return render(request, 'providers/contato_form.html', {'form': ContatoForm(instance=contato)})

@login_required
def excluir_contato(request, contato_id):
    contato = get_object_or_404(Contato, id=contato_id)
    contato.delete()
    return redirect('lista_provedores')

# --- GESTÃO DE CIDADES ---

@login_required
def adicionar_cidade(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    if request.method == 'POST':
        form = CidadeAtendidaForm(request.POST)
        if form.is_valid():
            cidade = form.save(commit=False)
            cidade.provedor = provedor
            cidade.save()
            return redirect('lista_provedores')
    return render(request, 'providers/cidade_form.html', {'form': CidadeAtendidaForm()})

@login_required
def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    cidade.delete()
    return redirect('lista_provedores')

@login_required
def excluir_todas_cidades(request, provedor_id):
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    return redirect('lista_provedores')

# --- IMPORTAÇÃO E MAPEAMENTO ---

@login_required
def importar_e_mapear_projeto(request):
    return render(request, 'providers/importar.html')

@login_required
def importar_cidades_csv(request, provedor_id):
    return redirect('lista_provedores')