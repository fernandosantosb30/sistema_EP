import csv
import io
import unicodedata
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Q
from .models import Provedor, Contato, CidadeAtendida 
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User

# --- GESTÃO DE ACESSO (ADMIN) ---

def e_admin(user):
    return user.is_superuser

# Funções de normalização mantidas para uso futuro ou consistência
def normalizar_texto(texto):
    if not texto: return ""
    nfkd_form = unicodedata.normalize('NFKD', texto)
    texto_sem_acentos = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return texto_sem_acentos.lower().replace('-', ' ').strip()

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
    fornecedor_query = request.GET.get('fornecedor', '').strip()
    uf_query = request.GET.get('uf', '').strip()
    cidades = [request.GET.get(f'cidade{i}', '').strip() for i in range(1, 4)]

    provedores = Provedor.objects.filter(ativo=True)

    if fornecedor_query:
        provedores = provedores.filter(
            Q(nome__icontains=fornecedor_query) | 
            Q(razao_social__icontains=fornecedor_query)
        )

    if uf_query:
        provedores = provedores.filter(cidades__uf__iexact=uf_query)

    filtros_cidade = Q()
    for cidade in cidades:
        if cidade:
            filtros_cidade |= Q(cidades__nome__icontains=cidade)
    
    if filtros_cidade:
        provedores = provedores.filter(filtros_cidade)

    return render(request, 'providers/consulta.html', {'provedores': provedores.distinct()})

@login_required
def importar_e_mapear_projeto(request):
    """
    CORREÇÃO: Mapeia cidades da planilha aceitando qualquer escrita e 
    retornando todos os provedores correspondentes do banco.
    """
    if request.method == 'POST' and request.FILES.get('arquivo_cidades'):
        arquivo = request.FILES['arquivo_cidades']
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="mapeamento_fornecedores.csv"'
        
        # BOM para Excel reconhecer acentuação em UTF-8 ou use latin-1
        writer = csv.writer(response, delimiter=';')
        writer.writerow(['CIDADE PESQUISADA', 'UF', 'FORNECEDOR NO SISTEMA', 'TECNOLOGIAS', 'CONTATO'])

        try:
            # Tenta latin-1 (padrão MS-DOS/Excel) para não quebrar com acentos
            conteudo = arquivo.read().decode('latin-1').splitlines()
            reader = csv.reader(conteudo, delimiter=';')
            next(reader, None) 

            for linha in reader:
                if not linha or len(linha) < 1: continue
                
                # Aceita qualquer escrita: limpa espaços e usa busca parcial (icontains)
                cidade_planilha = linha[0].strip()
                uf_planilha = linha[1].strip().upper() if len(linha) > 1 else None

                # Busca no banco ignorando acentos/case (dependendo da collation do banco)
                filtros = Q(cidades__nome__icontains=cidade_planilha)
                if uf_planilha:
                    filtros &= Q(cidades__uf__iexact=uf_planilha)

                provedores_no_banco = Provedor.objects.filter(filtros).distinct()

                if provedores_no_banco.exists():
                    for p in provedores_no_banco:
                        tecs = []
                        if p.fibra: tecs.append("Fibra")
                        if p.radio: tecs.append("Rádio")
                        if p.link_dedicado: tecs.append("Dedicado")
                        
                        writer.writerow([
                            cidade_planilha.upper(),
                            uf_planilha or "---",
                            p.nome,
                            " / ".join(tecs),
                            "Ver no Sistema"
                        ])
                else:
                    writer.writerow([cidade_planilha.upper(), uf_planilha or "---", "NÃO ENCONTRADO", "-", "-"])

            return response

        except Exception as e:
            messages.error(request, f"Erro no mapeamento: {e}")
            return redirect('consulta')

    return redirect('consulta')


# --- GESTÃO DE DADOS (PROVEDORES) ---

@login_required
def editar_provedor(request, pk=None):
    provedor = get_object_or_404(Provedor, pk=pk) if pk else None

    if request.method == "POST":
        # Simplificação da captura de booleanos
        campos_bool = [
            'ativo', 'fibra', 'radio', 'link_dedicado', 
            'link_banda_larga', 'zona_rural', 'parceiro_bst'
        ]
        dados = {campo: request.POST.get(campo) == 'on' for campo in campos_bool}
        dados.update({
            'nome': request.POST.get('nome'),
            'razao_social': request.POST.get('razao_social'),
            'cnpj': request.POST.get('cnpj'),
            'observacao': request.POST.get('observacao'),
        })

        if not pk and Provedor.objects.filter(cnpj=dados['cnpj']).exists():
            messages.error(request, "CNPJ já cadastrado!")
            return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

        if provedor:
            for attr, value in dados.items():
                setattr(provedor, attr, value)
            provedor.save()
            messages.success(request, "Atualizado com sucesso!")
        else:
            provedor = Provedor.objects.create(**dados)
            messages.success(request, "Cadastrado com sucesso!")
        
        return redirect('lista_provedores')

    return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

@login_required
def excluir_provedor(request, pk):
    get_object_or_404(Provedor, pk=pk).delete()
    messages.success(request, "Provedor removido.")
    return redirect('lista_provedores')


# --- GESTÃO DE CONTATOS ---

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
    contato = get_object_or_404(Contato, id=contato_id)
    if request.method == 'POST':
        contato.nome = request.POST.get('contato_nome')
        contato.cargo = request.POST.get('contato_cargo')
        contato.telefone = request.POST.get('contato_telefone')
        contato.email = request.POST.get('contato_email')
        contato.save()
        messages.success(request, "Contato atualizado!")
        return redirect('editar_provedor', pk=contato.provedor.id)
    
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
        nome = request.POST.get('cidade_nome', '').strip().title()
        uf = request.POST.get('cidade_uf', '').upper().strip()
        if nome and uf:
            CidadeAtendida.objects.get_or_create(provedor=provedor, nome=nome, uf=uf)
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def importar_cidades_csv(request, provedor_id):
    if request.method == "POST" and request.FILES.get('arquivo_csv'):
        provedor = get_object_or_404(Provedor, id=provedor_id)
        try:
            csv_file = request.FILES['arquivo_csv'].read().decode('latin-1').splitlines()
            reader = csv.reader(csv_file, delimiter=';')
            
            cidades_criadas = 0
            for linha in reader:
                if len(linha) >= 2:
                    nome = linha[0].strip().title()
                    uf = linha[1].strip().upper()
                    CidadeAtendida.objects.get_or_create(provedor=provedor, nome=nome, uf=uf)
                    cidades_criadas += 1
            messages.success(request, f"{cidades_criadas} cidades processadas!")
        except Exception as e:
            messages.error(request, f"Erro: {e}")
            
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def excluir_todas_cidades(request, provedor_id):
    CidadeAtendida.objects.filter(provedor_id=provedor_id).delete()
    messages.warning(request, "Cidades removidas.")
    return redirect('editar_provedor', pk=provedor_id)

@login_required
def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    id_p = cidade.provedor.id
    cidade.delete()
    return redirect('editar_provedor', pk=id_p)