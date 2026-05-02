from django.shortcuts import render, get_object_or_404, redirect
from .models import Provedor, Contato
from django.contrib import messages

# Esta é a função que o erro está apontando
def home_view(request):
    return render(request, 'providers/index.html')

def consulta_provedores(request):
    return render(request, 'providers/consulta.html')

def lista_provedores(request):
    provedores = Provedor.objects.all().order_by('-data_cadastro')
    return render(request, 'providers/cadastro.html', {'provedores': provedores})

def editar_provedor(request, pk=None):
    provedor = get_object_or_404(Provedor, pk=pk) if pk else None

    if request.method == "POST":
        cnpj = request.POST.get('cnpj')
        
        # Validar se já existe um provedor com este CNPJ (apenas em novos cadastros)
        if not pk and Provedor.objects.filter(cnpj=cnpj).exists():
            messages.error(request, "Provedor já cadastrado com este CNPJ!")
            return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

    if request.method == "POST":
        # Capturando os dados do formulário baseados na imagem 2
        nome = request.POST.get('nome')
        razao_social = request.POST.get('razao_social')
        cnpj = request.POST.get('cnpj')
        observacao = request.POST.get('observacao')
        # Checkboxes e Switch
        ativo = request.POST.get('ativo') == 'on'
        fibra = request.POST.get('fibra') == 'on'
        radio = request.POST.get('radio') == 'on'
        link_dedicado = request.POST.get('link_dedicado') == 'on'
        link_banda_larga = request.POST.get('link_banda_larga') == 'on'
        zona_rural = request.POST.get('zona_rural') == 'on'

        if provedor:
            # Atualiza existente
            provedor.nome = nome
            provedor.razao_social = razao_social
            provedor.cnpj = cnpj
            provedor.observacao = observacao
            provedor.ativo = ativo
            provedor.fibra = fibra
            provedor.radio = radio
            provedor.link_dedicado = link_dedicado
            provedor.link_banda_larga = link_banda_larga
            provedor.zona_rural = zona_rural
            provedor.save()
        else:
            # Cria novo registro incluindo todos os campos
            Provedor.objects.create(
                nome=nome,
                razao_social=razao_social,
                cnpj=cnpj,
                observacao=observacao,
                ativo=ativo,
                fibra=fibra,
                radio=radio,
                link_dedicado=link_dedicado,
                link_banda_larga=link_banda_larga,
                zona_rural=zona_rural
            )
        return redirect('cadastro')

    return render(request, 'providers/cadastro_edit.html', {'provedor': provedor})

# Adicione a partir da linha 65:

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
        
        return redirect('editar_provedor', pk=provedor.id)

def excluir_provedor(request, pk):
    provedor = get_object_or_404(Provedor, pk=pk)
    provedor.delete()
    return redirect('cadastro')

