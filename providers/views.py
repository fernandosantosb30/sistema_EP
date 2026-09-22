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
from collections import defaultdict

# --- BIBLIOTECAS DJANGO ---
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import UserCreationForm, SetPasswordForm
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView
from django.core.paginator import Paginator
from django.db import transaction, connection 
from django.db.models import Q
from django.db.models.functions import Lower, Trim
from django.forms import inlineformset_factory, modelform_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView
from django.views.decorators.http import require_POST
from .services.consultas import filtrar_cobertura, calcular_custo, resposta_csv, ler_csv_validado, validar_uf

# --- IMPORTAÇÃO DA FUNÇÃO NORMALIZAR_TEXTO ---
from .utils import (
    normalizar_texto,
    celula_csv,
    decodificar_csv,
    ler_dataframe_csv,
    padronizar_colunas,
    provedor_coincide,
    construir_mapa_cidades,
    buscar_cidades_no_mapa,
) 

# --- MODELOS E FORMULÁRIOS LOCAIS ---
from .forms import (
    ProvedorForm, ContatoForm, CidadeForm, PrestadorServicoForm,
    CidadeAtendidaPrestadorForm, UsuarioEdicaoForm,
)
from .models import (
    InboxContrato, ContratoCusto, Provedor, Contato, CidadeAtendida,
    PrestadorServico, CidadeAtendidaPrestador,
)

class SistemaLoginView(LoginView):
    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def get_success_url(self):
        from django.urls import reverse
        return reverse('home')



def index_view(request):
    return redirect('home' if request.user.is_authenticated else 'login')


@login_required
def editar_usuario(request, user_id):
    from django.core.exceptions import PermissionDenied
    from django.contrib.auth import update_session_auth_hash
    if not request.user.is_superuser:
        raise PermissionDenied
    usuario = get_object_or_404(User, pk=user_id)
    form = UsuarioEdicaoForm(usuario, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        if usuario.pk == request.user.pk and form.cleaned_data['autoridade'] != 'admin':
            form.add_error('autoridade', 'Você não pode remover sua própria autoridade de administrador.')
        else:
            return salvar_edicao_usuario(request, form)
    return render(request, 'registration/usuario_form.html', {
        'form': form, 'titulo': f'Editar usuário: {usuario.username}',
    })

def salvar_edicao_usuario(request, form):
    from django.contrib.auth import update_session_auth_hash
    usuario = form.save()
    if usuario.pk == request.user.pk:
        update_session_auth_hash(request, usuario)
    messages.success(request, 'Usuário atualizado com sucesso!')
    return redirect('gestao_usuarios')

# --- GESTÃO DE ACESSO (ADMIN) ---
def e_admin(user):
    return user.is_superuser

@user_passes_test(e_admin)
def gestao_usuarios(request):
    return render(request, 'registration/gestao_usuarios.html', {'usuarios': User.objects.all()})

@user_passes_test(e_admin)
def criar_usuario(request):
    form = UserCreationForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Usuário criado!")
            return redirect('gestao_usuarios')
    return render(request, 'registration/usuario_form.html', {'form': form, 'titulo': 'Novo Usuário'})

@user_passes_test(e_admin)
def alterar_senha(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    form = SetPasswordForm(usuario, request.POST if request.method == 'POST' else None)
    if request.method == 'POST':
        form = SetPasswordForm(usuario, request.POST)
        if form.is_valid():
            form.save()
            if usuario.pk == request.user.pk:
                from django.contrib.auth import update_session_auth_hash
                update_session_auth_hash(request, usuario)
            messages.success(request, "Senha alterada!")
            return redirect('gestao_usuarios')
    return render(request, 'registration/usuario_form.html', {'form': form, 'titulo': 'Alterar Senha'})

@user_passes_test(e_admin)
@require_POST
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
def lista_prestadores_servico(request):
    query = request.GET.get('q', '').strip()
    prestadores = PrestadorServico.objects.all()
    if query:
        prestadores = prestadores.filter(
            Q(nome_fantasia__icontains=query)
            | Q(razao_social__icontains=query)
            | Q(cnpj__icontains=query)
            | Q(contato__icontains=query)
        )

    uf = request.GET.get('uf', '').strip().upper()
    if uf:
        prestadores = prestadores.filter(cidades_atendidas__uf__iexact=uf).distinct()
    prestadores = prestadores.order_by('-id')
    paginator = Paginator(prestadores, 10)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(request, 'providers/prestadores_lista.html', {
        'page_obj': page_obj,
        'total_registros': prestadores.count(),
        'uf_selecionada': uf,
        'ufs': 'AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split(),
    })


@login_required
def editar_prestador_servico(request, pk=None):
    prestador = get_object_or_404(PrestadorServico, pk=pk) if pk else None
    CidadeFormSet = inlineformset_factory(
        PrestadorServico,
        CidadeAtendidaPrestador,
        form=CidadeAtendidaPrestadorForm,
        extra=1,
        can_delete=True,
    )

    if request.method == 'POST':
        form = PrestadorServicoForm(request.POST, instance=prestador)
        formset = CidadeFormSet(request.POST, instance=prestador)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                prestador = form.save()
                formset.instance = prestador
                formset.save()
            messages.success(request, 'Prestador de serviço salvo com sucesso!')
            return redirect('lista_prestadores_servico')
    else:
        form = PrestadorServicoForm(instance=prestador)
        formset = CidadeFormSet(instance=prestador)

    return render(request, 'providers/prestador_form.html', {
        'form': form,
        'formset': formset,
        'prestador': prestador,
    })


@user_passes_test(e_admin)
@login_required
@require_POST
def excluir_prestador_servico(request, pk):
    prestador = get_object_or_404(PrestadorServico, pk=pk)
    prestador.delete()
    messages.success(request, 'Prestador de serviço excluído com sucesso!')
    return redirect('lista_prestadores_servico')

@login_required
def consulta_provedores(request):
    provedores, _ = filtrar_cobertura(request.GET)
    return render(request, 'providers/consulta.html', {'mapeamento': provedores})


@login_required
def processar_custo_medio(request):
    contratos = list(ContratoCusto.objects.values('cidade', 'uf', 'tipo_servico', 'velocidade', 'meio_fisico', 'mensal'))
    try:
        dados = calcular_custo(contratos, request.GET)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(dados)
    return render(request, 'providers/custo_medio_integrado.html', {
        'dados': dados,
        'servicos': sorted({c['tipo_servico'] for c in contratos}),
        'velocidades': sorted({c['velocidade'] for c in contratos}),
        'meios_fisicos': sorted({c['meio_fisico'] for c in contratos}),
    })


@login_required
@require_POST
def processar_lote_csv(request):
    try:
        df = ler_csv_validado(request.FILES.get('arquivo_csv'), ['cidade', 'uf', 'tipo_servico', 'velocidade'])
        contratos = list(ContratoCusto.objects.values('cidade', 'uf', 'tipo_servico', 'velocidade', 'meio_fisico', 'mensal'))
        linhas = [['cidade', 'uf', 'tipo_servico', 'velocidade', 'custo_medio', 'nivel']]
        for _, row in df.iterrows():
            dados = calcular_custo(contratos, row)
            linhas.append([row['cidade'], row['uf'], row['tipo_servico'], row['velocidade'], dados['custo_medio'] if dados['quantidade_contratos'] else 'Não encontrado', dados['nivel']])
        return resposta_csv('resultado_precificacao.csv', linhas)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)



@user_passes_test(e_admin) # Apenas ADMIN pode excluir
@login_required
@require_POST
def excluir_provedor(request, pk):
    get_object_or_404(Provedor, pk=pk).delete()
    return redirect('lista_provedores')

# --- GESTÃO DE CONTATOS ---

@login_required
def adicionar_contato(request, provedor_id=None, contato_id=None):
    contato = get_object_or_404(Contato, pk=contato_id) if contato_id else None
    provedor = contato.provedor if contato else get_object_or_404(Provedor, pk=provedor_id)
    form = ContatoForm(request.POST if request.method == 'POST' else None, instance=contato)
    if request.method == 'POST' and form.is_valid():
        contato = form.save(commit=False)
        contato.provedor = provedor
        contato.save()
        messages.success(request, 'Contato salvo.')
        return redirect('editar_provedor', pk=provedor.pk)
    return render(request, 'providers/relacionado_form.html', {'form': form, 'provedor': provedor, 'titulo': 'Editar contato' if contato else 'Novo contato'})


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
@require_POST
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
    provedor = get_object_or_404(Provedor, pk=provedor_id)
    form = CidadeForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        nome = normalizar_texto(form.cleaned_data['nome'])
        CidadeAtendida.objects.get_or_create(provedor=provedor, nome=nome, uf=form.cleaned_data['uf'])
        messages.success(request, 'Cidade salva.')
        return redirect('editar_provedor', pk=provedor.pk)
    return render(request, 'providers/relacionado_form.html', {'form': form, 'provedor': provedor, 'titulo': 'Nova cidade'})


@user_passes_test(e_admin)
@login_required
@require_POST
def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    provedor_id = cidade.provedor.id # Captura o ID do provedor dono da cidade
    cidade.delete()
    
    # Redireciona de volta para o cadastro do provedor
    return redirect('editar_provedor', pk=provedor_id)

@user_passes_test(e_admin)
@login_required
@require_POST
def excluir_todas_cidades(request, provedor_id):
    # Deleta apenas as cidades relacionadas ao provedor informado
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    
    # Redireciona de volta para o cadastro do provedor
    return redirect('editar_provedor', pk=provedor_id)

# --- IMPORTAÇÃO E MAPEAMENTO ---
@login_required
@require_POST
def importar_mapeamento(request):
    try:
        df = ler_csv_validado(request.FILES.get('arquivo_cidades'), ['cidade', 'uf'])
        linhas = [['Cidade', 'UF', 'BST', 'Contato', 'Trunk']]
        vistos = set()
        for _, row in df.iterrows():
            cidades = CidadeAtendida.objects.filter(nome=normalizar_texto(row['cidade']), uf__iexact=validar_uf(row['uf'])).select_related('provedor').prefetch_related('provedor__contatos')
            for cidade in cidades:
                p = cidade.provedor
                if row.get('provedor', '') and not provedor_coincide(row['provedor'], p.nome):
                    continue
                if cidade.pk in vistos:
                    continue
                vistos.add(cidade.pk)
                telefones = ', '.join(c.telefone for c in p.contatos.all() if c.telefone)
                linhas.append([cidade.nome, cidade.uf, p.nome, telefones or 'N/A', 'Sim' if p.parceiro_bst else 'Não'])
        if len(linhas) == 1:
            messages.warning(request, 'Nenhum mapeamento encontrado para as cidades e UFs informadas.')
            return redirect('consulta_provedores')
        return resposta_csv('mapeamento_filtrado.csv', linhas)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect('consulta_provedores')


@login_required
def exportar_mapeamento_csv(request):
    provedores, cidades = filtrar_cobertura(request.GET)
    linhas = [['Cidade', 'UF', 'BST', 'Contato', 'Trunk']]
    for cidade in cidades.filter(provedor__in=provedores).select_related('provedor').prefetch_related('provedor__contatos'):
        p = cidade.provedor
        telefones = ', '.join(c.telefone for c in p.contatos.all() if c.telefone)
        linhas.append([cidade.nome, cidade.uf, p.nome, telefones or 'N/A', 'Sim' if p.parceiro_bst else 'Não'])
    return resposta_csv('mapeamento_parceiros.csv', linhas)


@login_required
@require_POST
def importar_cidades_csv(request, provedor_id):
    provedor = get_object_or_404(Provedor, pk=provedor_id)
    try:
        df = ler_csv_validado(request.FILES.get('arquivo_csv'), ['cidade', 'uf'])
        # Valida o arquivo inteiro antes de gravar qualquer linha.
        linhas = [(normalizar_texto(row['cidade']), validar_uf(row['uf'])) for _, row in df.iterrows()]
        with transaction.atomic():
            novas = sum(CidadeAtendida.objects.get_or_create(provedor=provedor, nome=nome, uf=uf)[1] for nome, uf in linhas)
        messages.success(request, f'Importação concluída: {novas} novas cidades.')
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect('editar_provedor', pk=provedor.pk)
