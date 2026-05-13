import csv
import io
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User

# Importação centralizada dos modelos
from .models import Provedor, Contato, CidadeAtendida 

# --- GESTÃO DE ACESSO (ADMIN) ---

def e_admin(user):
    return user.is_superuser

@user_passes_test(e_admin)
def gestao_usuarios(request):
    usuarios = User.objects.all()
    return render(request, 'registration/gestao_usuarios.html', {'usuarios': usuarios})

@user_passes_test(e_admin)
def excluir_usuario(request, user_id):
    usuario = get_object_or_404(User, id=user_id)
    if usuario.username != request.user.username:
        usuario.delete()
        messages.success(request, "Usuário removido com sucesso.")
    return redirect('gestao_usuarios')


# --- NAVEGAÇÃO PRINCIPAL ---

@login_required
def home_view(request):
    return render(request, 'providers/home.html')

@login_required
def lista_provedores(request):
    provedores = Provedor.objects.all().order_by('-data_cadastro')
    return render(request, 'providers/cadastro.html', {'provedores': provedores})


# --- CONSULTAS E MAPEAMENTO ---

@login_required
def consulta_provedores(request):
    fornecedor_query = request.GET.get('fornecedor')
    uf_query = request.GET.get('uf')
    cidade1 = request.GET.get('cidade1')
    cidade2 = request.GET.get('cidade2')
    cidade3 = request.GET.get('cidade3')

    provedores = Provedor.objects.filter(ativo=True)

    if fornecedor_query:
        provedores = provedores.filter(
            Q(nome__icontains=fornecedor_query) | 
            Q(razao_social__icontains=fornecedor_query)
        )

    if uf_query:
        provedores = provedores.filter(cidades__uf__iexact=uf_query.strip())

    filtros_cidade = Q()
    if cidade1: filtros_cidade |= Q(cidades__nome__icontains=cidade1.strip())
    if cidade2: filtros_cidade |= Q(cidades__nome__icontains=cidade2.strip())
    if cidade3: filtros_cidade |= Q(cidades__nome__icontains=cidade3.strip())
    
    if filtros_cidade:
        provedores = provedores.filter(filtros_cidade)

    provedores = provedores.distinct()
    return render(request, 'providers/consulta.html', {'provedores': provedores})

@login_required
def importar_e_mapear_projeto(request):
    """Mapeia uma lista de cidades em CSV contra os 1.500 provedores."""
    if request.method == 'POST' and request.FILES.get('arquivo_cidades'):
        arquivo = request.FILES['arquivo_cidades']
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="resultado_mapeamento.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['CIDADE PESQUISADA', 'UF', 'FORNECEDOR ENCONTRADO', 'TECNOLOGIA', 'CONTATO'])

        try:
            decoded_file = arquivo.read().decode('utf-8').splitlines()
            reader = csv.reader(decoded_file)
            next(reader, None) 

            for linha in reader:
                if not linha: continue
                cidade_nome = linha[0].strip()
                uf_sigla = linha[1].strip() if len(linha) > 1 else None

                filtros = Q(cidades__nome__iexact=cidade_nome)
                if uf_sigla: filtros &= Q(cidades__uf__iexact=uf_sigla)
                
                provedores_encontrados = Provedor.objects.filter(filtros).distinct()

                if provedores_encontrados.exists():
                    for p in provedores_encontrados:
                        tecs = []
                        if p.fibra: tecs.append("Fibra")
                        if p.radio: tecs.append("Rádio")
                        writer.writerow([cidade_nome.upper(), uf_sigla.upper() if uf_sigla else "---", p.nome, " / ".join(tecs), "Ver no Sistema"])
                else:
                    writer.writerow([cidade_nome.upper(), uf_sigla, "NENHUM ENCONTRADO", "-", "-"])
            return response
        except Exception as e:
            messages.error(request, f"Erro: {e}")
            return redirect('consulta')
    return redirect('consulta')


# --- GESTÃO DE DADOS (PROVEDORES) ---

@login_required
def editar_provedor(request, pk=None):
    provedor = get_object_or_404(Provedor, pk=pk) if pk else None

    if request.method == "POST":
        dados = {
            'nome': request.POST.get('nome'),
            'razao_social': request.POST.get('razao_social'),
            'cnpj': request.POST.get('cnpj'),
            'observacao': request.POST.get('observacao'),
            'ativo': request.POST.get('ativo') == 'on',
            'fibra': request.POST.get('fibra') == 'on',
            'radio': request.POST.get('radio') == 'on',
            'link_dedicado': request.POST.get('link_dedicado') == 'on',
            'link_banda_larga': request.POST.get('link_banda_larga') == 'on',
            'zona_rural': request.POST.get('zona_rural') == 'on',
            'parceiro_bst': request.POST.get('parceiro_bst') == 'on',
        }

        if not pk and Provedor.objects.filter(cnpj=dados['cnpj']).exists():
            messages.error(request, "CNPJ já cadastrado!")
            return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

        if provedor:
            for attr, value in dados.items():
                setattr(provedor, attr, value)
            provedor.save()
            messages.success(request, "Atualizado com sucesso!")
        else:
            Provedor.objects.create(**dados)
            messages.success(request, "Cadastrado com sucesso!")
        
        return redirect('lista_provedores')

    return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

@login_required
def excluir_provedor(request, pk):
    get_object_or_404(Provedor, pk=pk).delete()
    messages.success(request, "Provedor removido.")
    return redirect('lista_provedores')


# --- GESTÃO DE CONTATOS (CORRIGIDO) ---

@login_required
def adicionar_contato(request, provedor_id):
    if request.method == "POST":
        provedor = get_object_or_404(Provedor, id=provedor_id)
        Contato.objects.create(
            provedor=provedor,
            nome=request.POST.get('contato_nome'),
            cargo=request.POST.get('contato_cargo'),
            telefone=request.POST.get('contato_telefone'),
            email=request.POST.get('contato_email')
        )
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def editar_contato(request, contato_id):
    """Função única para renderizar e salvar a edição de contato."""
    contato = get_object_or_404(Contato, id=contato_id)
    id_p = contato.provedor.id
    
    if request.method == 'POST':
        contato.nome = request.POST.get('contato_nome') # Nome do campo ajustado para seu HTML
        contato.cargo = request.POST.get('contato_cargo')
        contato.telefone = request.POST.get('contato_telefone')
        contato.email = request.POST.get('contato_email')
        contato.save()
        messages.success(request, "Contato atualizado!")
        return redirect('editar_provedor', pk=id_p)
    
    return render(request, 'providers/contato_edit.html', {'contato': contato})

@login_required
def excluir_contato(request, contato_id):
    contato = get_object_or_404(Contato, id=contato_id)
    id_p = contato.provedor.id
    contato.delete()
    messages.success(request, "Contato excluído.")
    return redirect('editar_provedor', pk=id_p)


# --- GESTÃO DE CIDADES ---

@login_required
def adicionar_cidade(request, provedor_id):
    if request.method == 'POST':
        provedor = get_object_or_404(Provedor, id=provedor_id)
        nome = request.POST.get('cidade_nome')
        uf = request.POST.get('cidade_uf', '').upper()
        if nome and uf:
            CidadeAtendida.objects.create(provedor=provedor, nome=nome, uf=uf)
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def importar_cidades_csv(request, provedor_id):
    if request.method == "POST" and request.FILES.get('arquivo_csv'):
        provedor = get_object_or_404(Provedor, id=provedor_id)
        csv_file = request.FILES['arquivo_csv'].read().decode('utf-8').splitlines()
        reader = csv.reader(csv_file)
        
        cidades_criadas = 0
        for linha in reader:
            if len(linha) >= 2:
                CidadeAtendida.objects.get_or_create(
                    provedor=provedor, 
                    nome=linha[0].strip(), 
                    uf=linha[1].strip().upper()
                )
                cidades_criadas += 1
        
        messages.success(request, f"{cidades_criadas} cidades importadas com sucesso!")
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def excluir_todas_cidades(request, provedor_id):
    """Remove o mapeamento de todas as cidades deste provedor."""
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    messages.warning(request, "Todas as cidades foram removidas deste provedor.")
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    id_p = cidade.provedor.id
    cidade.delete()
    return redirect('editar_provedor', pk=id_p)