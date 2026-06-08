# --- BIBLIOTECAS PADRÃO ---
import csv
import io
import os
import unicodedata

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
from .utils import normalizar_texto  # <--- CORRIGIDO: Agora vem de utils.py

# --- MODELOS E FORMULÁRIOS LOCAIS ---
from .forms import ProvedorForm, ContatoForm, CidadeForm
from .models import Provedor, Contato, CidadeAtendida

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
        # Busca os dados do banco
        query = "SELECT cidade, uf, servico, valor_mensal, capacidade_mb, vigencia_meses, ip_fixo FROM public.providers_contratocusto"
        df = pd.read_sql(query, connection)
        
        if df.empty:
            return JsonResponse({'error': 'Nenhum contrato encontrado no banco.'}, status=404)

        # 1. PREPARAÇÃO E NORMALIZAÇÃO
        def extrair_interface(texto):
            texto = normalizar_texto(texto) if texto else ""
            if 'FIBRA' in texto: return 'Fibra'
            if 'WIRELESS' in texto or 'RADIO' in texto: return 'Rádio'
            return 'Misto'

        df['interface'] = df['servico'].apply(extrair_interface)
        df['cidade_norm'] = df['cidade'].apply(lambda x: normalizar_texto(x) if x else "")
        df['uf'] = df['uf'].str.upper().str.strip()

        # 2. VERIFICAÇÃO DE PARÂMETROS
        params_keys = ['cidade', 'uf', 'servico', 'capacidade', 'vigencia', 'interface', 'ip_fixo']
        has_params = any(request.GET.get(k) for k in params_keys)

        if not has_params:
            context = {
                'servicos': sorted([s for s in df['servico'].unique() if s]),
                'vigencias': sorted([v for v in df['vigencia_meses'].unique() if pd.notnull(v)]),
                'ips_fixos': sorted([str(ip) for ip in df['ip_fixo'].unique() if pd.notnull(ip)]),
                'interfaces': sorted(df['interface'].unique()) 
            }
            return render(request, 'providers/custo_medio_integrado.html', context)

        # 3. LÓGICA DE FILTROS
        # Criamos uma máscara base com os filtros fixos (serviço, capacidade, etc)
        mask = pd.Series(True, index=df.index)
        if request.GET.get('servico'): mask &= (df['servico'] == request.GET.get('servico'))
        if request.GET.get('interface'): mask &= (df['interface'] == request.GET.get('interface'))
        if request.GET.get('ip_fixo'): mask &= (df['ip_fixo'].astype(str) == request.GET.get('ip_fixo'))
        if request.GET.get('capacidade'): mask &= (df['capacidade_mb'] == int(request.GET.get('capacidade')))
        if request.GET.get('vigencia'): mask &= (df['vigencia_meses'] == int(request.GET.get('vigencia')))

        df_base = df[mask]
        cidade_req = normalizar_texto(request.GET.get('cidade')) if request.GET.get('cidade') else None
        uf_req = request.GET.get('uf', '').upper().strip()

        # TENTA FILTRAR POR CIDADE
        df_final = pd.DataFrame()
        nivel = 'Geral'

        if cidade_req:
            cidades_list = df_base['cidade_norm'].unique().tolist()
            matches = difflib.get_close_matches(cidade_req, cidades_list, n=1, cutoff=0.7)
            if matches:
                df_final = df_base[df_base['cidade_norm'] == matches[0]]
                nivel = 'Cidade'
        
        # FALLBACK: Se não encontrou por cidade, tenta por Estado
        if df_final.empty and uf_req:
            df_final = df_base[df_base['uf'] == uf_req]
            nivel = 'Estado' if not df_final.empty else 'Nenhum'

        # 4. RESULTADO
        return JsonResponse({
            'custo_medio': round(float(df_final['valor_mensal'].mean()), 2) if not df_final.empty else 0.00,
            'quantidade_contratos': int(len(df_final)),
            'nivel': nivel
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# --- Nova Função de Processamento em Lote (CSV) ---
@login_required
def processar_lote_csv(request):
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        arquivo = request.FILES['arquivo_csv']
        try:
            # 1. LEITURA ROBUSTA: Decodifica os bytes antes de passar para o Pandas
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

            # 2. CARREGA O CSV
            df_input = pd.read_csv(io.StringIO(conteudo), sep=None, engine='python', on_bad_lines='skip')
            df_input.columns = [c.lower().strip() for c in df_input.columns]
            
            # Validação: Verifica se as colunas necessárias existem
            colunas_obrigatorias = ['cidade', 'uf', 'velocidade']
            if not all(col in df_input.columns for col in colunas_obrigatorias):
                raise ValueError(f"O CSV deve conter as colunas: {', '.join(colunas_obrigatorias)}")

            # 3. NORMALIZAÇÃO
            df_input['cidade_norm'] = df_input['cidade'].apply(normalizar_texto)
            df_input['uf'] = df_input['uf'].astype(str).str.upper().str.strip()
            df_input['capacidade_mb'] = pd.to_numeric(df_input['velocidade'], errors='coerce').fillna(-1).astype(int)

            # --- SUA LÓGICA DE BUSCA NO BANCO PERMANECE AQUI ---
            # (Exemplo: df_custos = pd.read_sql("...", connection)...)

            # 4. GERAR DOWNLOAD
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="resultado_precificacao.csv"'
            
            # Garantir que o df_input contenha a coluna 'custo_medio' calculada
            df_input[['cidade', 'uf', 'velocidade', 'custo_medio']].to_csv(
                path_or_buf=response, index=False, encoding='utf-8-sig', sep=';'
            )
            return response
            
        except Exception as e:
            logger.exception("ERRO DETALHADO NO PROCESSAR_LOTE:") # Isso aparecerá no seu painel de Logs do Render
            return HttpResponse(f"Erro ao processar: {str(e)}", status=500)
            
    return HttpResponse("Erro: Arquivo não enviado.", status=400)

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
            
            # 1. Decodificação robusta para suportar padrões legados (MS-DOS)
            conteudo = None
            for encoding in ['utf-8-sig', 'latin-1', 'cp850', 'cp1252']:
                try:
                    conteudo = raw_data.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if conteudo is None:
                raise ValueError("Formato de arquivo não suportado. Tente salvar como UTF-8.")

            # 2. Carregar e Limpar DataFrame
            df = pd.read_csv(io.StringIO(conteudo), sep=None, engine='python', on_bad_lines='skip')
            df.columns = [str(c).lower().strip() for c in df.columns]
            
            if 'cidade' not in df.columns:
                raise ValueError("A coluna 'cidade' não foi encontrada no arquivo.")

            # Remove linhas vazias e duplicatas para não repetir cidades no resultado
            cidades_entrada = df['cidade'].dropna().unique()
            
            # 3. Preparar dados do banco para busca em memória
            todas_cidades = CidadeAtendida.objects.select_related('provedor').all()
            mapa_cidades = {normalizar_texto(c.nome): c for c in todas_cidades}
            lista_norm_banco = list(mapa_cidades.keys())

            # 4. Preparar resposta (utf-8-sig para o Excel reconhecer acentos)
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="mapeamento_filtrado.csv"'
            writer = csv.writer(response, delimiter=';')
            writer.writerow(['Cidade', 'UF', 'Parceiro', 'Contato', 'Trunk'])
            
            encontrou_algum = False
            
            # 5. Processamento único por cidade
            for cidade_raw in cidades_entrada:
                cidade_input = normalizar_texto(str(cidade_raw))
                if not cidade_input: continue
                
                # Busca inteligente (cutoff 0.7 evita falsos positivos)
                matches = get_close_matches(cidade_input, lista_norm_banco, n=1, cutoff=0.7)
                
                if matches:
                    cidade_obj = mapa_cidades[matches[0]]
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
                messages.warning(request, "Nenhum mapeamento encontrado para as cidades informadas.")
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
    # Define o content type com charset utf-8
    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="mapeamento_parceiros.csv"'

    # O 'utf-8-sig' acima já ajuda o Excel a reconhecer os caracteres especiais
    writer = csv.writer(response, delimiter=';')
    
    # Cabeçalho
    writer.writerow(['Cidade', 'UF', 'Parceiro', 'Contato', 'Trunk'])

    for p in resultado:
        # Acessa as cidades relacionadas ao provedor
        cidades = p.cidades.all()
        
        # Se o provedor não tiver cidades, você pode decidir pular ou mostrar como N/A
        if not cidades:
            continue
            
        for cidade in cidades:
            # Obtém o contato de forma segura
            contato_obj = p.contatos.first()
            nome_contato = f"{contato_obj.nome} ({contato_obj.telefone})" if contato_obj else "N/A"
            
            writer.writerow([
                cidade.nome,
                cidade.uf,
                p.nome,
                nome_contato,
                'Sim' if getattr(p, 'parceiro_bst', False) else 'Não'
            ])
            
    return response

@login_required
def importar_cidades_csv(request, provedor_id):
    provedor = get_object_or_404(Provedor, id=provedor_id)
    
    if request.method == 'POST' and request.FILES.get('arquivo_csv'):
        try:
            csv_file = request.FILES['arquivo_csv']
            
            # Leitura robusta
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
                # 1. Normaliza o nome da cidade
                nome_cidade = normalizar_texto(row.iloc[0])
                
                # 2. Normaliza a UF: pega apenas os 2 primeiros caracteres e garante que seja maiúsculo
                uf_raw = str(row.iloc[1]) if len(row) > 1 else "XX"
                uf_cidade = uf_raw.strip().upper()[:2]
                
                if nome_cidade:
                    # Busca ou cria normalizando a busca também
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