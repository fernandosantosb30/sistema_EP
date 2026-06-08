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
from .utils import normalizar_texto 
from .models import providers_contratocusto

# --- MODELOS E FORMULÁRIOS LOCAIS ---
from .forms import ProvedorForm, ContatoForm, CidadeForm
from .models import Provedor, Contato, CidadeAtendida

def buscar_custo(row):
    """
    Busca o custo médio usando o ORM do Django de forma segura.
    """
    try:
        # A busca retorna None se nenhum registro atender aos filtros
        custo = providers_contratocusto.objects.filter(
            cidade__iexact=row['cidade_norm'],
            uf__iexact=row['uf'],
            servico__iexact=row['servico'],
            capacidade_mb=row['capacidade_mb']
        ).first()
        
        # Verificação de segurança: se custo for None, retorna 0.0
        if custo and custo.valor_mensal:
            return float(custo.valor_mensal)
        return 0.0
        
    except Exception as e:
        # O log é importante para identificar se houve problema de conexão ou tipo
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
        queryset = providers_contratocusto.objects.all().values(
            'cidade', 'uf', 'servico', 'valor_mensal', 'capacidade_mb', 'vigencia_meses', 'ip_fixo'
        )
        df = pd.DataFrame(list(queryset))
        
        if not df.empty:
            df['valor_mensal'] = pd.to_numeric(df['valor_mensal'], errors='coerce')
        else:
            # Em caso de banco vazio, se for AJAX retorna erro, senão renderiza vazio
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Nenhum contrato encontrado.'}, status=404)
            df = pd.DataFrame(columns=['cidade', 'uf', 'servico', 'valor_mensal', 'capacidade_mb', 'vigencia_meses', 'ip_fixo', 'interface'])

        # PREPARAÇÃO E NORMALIZAÇÃO
        def extrair_interface(texto):
            norm = normalizar_texto(texto) if texto else ""
            if 'fibra' in norm: return 'Fibra'
            if 'wireless' in norm or 'radio' in norm: return 'Rádio'
            return 'Misto'

        df['interface'] = df['servico'].apply(extrair_interface)
        df['cidade_norm'] = df['cidade'].apply(lambda x: normalizar_texto(x) if x else "")
        df['uf'] = df['uf'].astype(str).str.upper().str.strip()

        # LÓGICA DE FILTROS
        mask = pd.Series(True, index=df.index)
        if request.GET.get('servico'): mask &= (df['servico'] == request.GET.get('servico'))
        if request.GET.get('interface'): mask &= (df['interface'] == request.GET.get('interface'))
        if request.GET.get('ip_fixo'): mask &= (df['ip_fixo'].astype(str) == request.GET.get('ip_fixo'))
        
        try:
            if request.GET.get('capacidade'): mask &= (df['capacidade_mb'] == int(request.GET.get('capacidade')))
            if request.GET.get('vigencia'): mask &= (df['vigencia_meses'] == int(request.GET.get('vigencia')))
        except ValueError:
            return JsonResponse({'error': 'Parâmetros numéricos inválidos.'}, status=400)

        df_base = df[mask]
        cidade_req = normalizar_texto(request.GET.get('cidade')) if request.GET.get('cidade') else None
        uf_req = request.GET.get('uf', '').upper().strip()

        df_final = pd.DataFrame()
        nivel = 'Geral'

        if cidade_req:
            cidades_list = df_base['cidade_norm'].unique().tolist()
            matches = difflib.get_close_matches(cidade_req, cidades_list, n=1, cutoff=0.7)
            if matches:
                df_final = df_base[df_base['cidade_norm'] == matches[0]]
                nivel = 'Cidade'
        
        if df_final.empty and uf_req:
            df_final = df_base[df_base['uf'] == uf_req]
            nivel = 'Estado' if not df_final.empty else 'Nenhum'
        elif df_final.empty and not cidade_req and not uf_req:
            df_final = df_base
            nivel = 'Geral'

        custo_medio = 0.00
        if not df_final.empty and 'valor_mensal' in df_final.columns:
            media = df_final['valor_mensal'].mean()
            custo_medio = round(float(media), 2) if pd.notnull(media) else 0.00

        dados_resposta = {
            'custo_medio': custo_medio,
            'quantidade_contratos': int(len(df_final)),
            'nivel': nivel
        }

        # RETORNO CONDICIONAL
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(dados_resposta)

        context = {
            'dados': dados_resposta,
            'servicos': sorted(df['servico'].dropna().unique()),
            'vigencias': sorted(df['vigencia_meses'].dropna().unique()),
            'ips_fixos': sorted([str(ip) for ip in df['ip_fixo'].dropna().unique()]),
            'interfaces': sorted(df['interface'].unique())
        }
        return render(request, 'providers/custo_medio_integrado.html', context)

    except Exception as e:
        logger.error(f"Erro no processamento de custo: {e}")
        return JsonResponse({'error': f'Erro interno: {str(e)}'}, status=500)

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

            # 2. CARREGA O CSV
            df_input = pd.read_csv(io.StringIO(conteudo), sep=None, engine='python', on_bad_lines='skip')
            df_input.columns = [c.lower().strip() for c in df_input.columns]
            
            # Validação de colunas essenciais
            colunas_obrigatorias = ['cidade', 'uf', 'servico', 'velocidade']
            for col in colunas_obrigatorias:
                if col not in df_input.columns:
                    raise ValueError(f"Coluna obrigatória ausente no CSV: {col}")

            # 3. NORMALIZAÇÃO E LIMPEZA
            df_input['cidade_norm'] = df_input['cidade'].apply(normalizar_texto)
            df_input['uf'] = df_input['uf'].astype(str).str.upper().str.strip()
            # Garante que capacidade é int (0 se inválido)
            df_input['capacidade_mb'] = pd.to_numeric(df_input['velocidade'], errors='coerce').fillna(0).astype(int)

            # 4. PROCESSAMENTO DO CUSTO (O coração da operação)
            # Em vez de confiar em um apply direto que pode falhar, fazemos um mapeamento seguro
            def safe_buscar_custo(row):
                try:
                    return buscar_custo(row)
                except Exception:
                    return 0.0

            df_input['custo_medio'] = df_input.apply(safe_buscar_custo, axis=1)
            
            # Garante que a coluna de resultado seja float
            df_input['custo_medio'] = df_input['custo_medio'].astype(float).fillna(0.0)

            # 5. EXPORTAÇÃO SEGURA
            cols_export = ['cidade', 'uf', 'servico', 'velocidade', 'custo_medio']
            
            response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
            response['Content-Disposition'] = 'attachment; filename="resultado_precificacao.csv"'
            
            df_input[cols_export].to_csv(
                path_or_buf=response, index=False, encoding='utf-8-sig', sep=';'
            )
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