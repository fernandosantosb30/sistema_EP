import csv
import io
from django.shortcuts import render, get_object_or_404, redirect
from .models import Provedor, Contato
from django.contrib import messages
from .models import Provedor, Contato, CidadeAtendida

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
    
def editar_contato_action(request, contato_id):
    if request.method == "POST":
        contato = get_object_or_404(Contato, id=contato_id)
        contato.nome = request.POST.get('contato_nome')
        contato.cargo = request.POST.get('contato_cargo')
        contato.telefone = request.POST.get('contato_telefone')
        contato.email = request.POST.get('contato_email')
        contato.save()
        return redirect('editar_provedor', pk=contato.provedor.id)
    
def excluir_contato(request, contato_id):
    contato = get_object_or_404(Contato, id=contato_id)
    provedor_id = contato.provedor.id  # Guarda o ID para voltar à página certa
    contato.delete()
    messages.success(request, "Contato excluído com sucesso!")
    return redirect('editar_provedor', pk=provedor_id)

def excluir_provedor(request, pk):
    provedor = get_object_or_404(Provedor, pk=pk)
    provedor.delete()
    return redirect('cadastro')

def adicionar_cidade(request, provedor_id):
    if request.method == "POST":
        provedor = get_object_or_404(Provedor, id=provedor_id)
        CidadeAtendida.objects.create(
            provedor=provedor,
            nome=request.POST.get('cidade_nome').upper(),
            uf=request.POST.get('cidade_uf').upper()
        )
    return redirect('editar_provedor', pk=provedor_id)

def importar_cidades_csv(request, provedor_id):
    if request.method == "POST" and request.FILES.get('arquivo_csv'):
        provedor = get_object_or_404(Provedor, id=provedor_id)
        csv_file = request.FILES['arquivo_csv']
        
        try:
            # Tratamento de codificação (UTF-8 ou Latin-1/MS-DOS)
            try:
                decoded_file = csv_file.read().decode('utf-8')
            except UnicodeDecodeError:
                csv_file.seek(0)
                decoded_file = csv_file.read().decode('latin-1')

            io_string = io.StringIO(decoded_file)
            
            # Detecta automaticamente se o separador é , ou ;
            dialect = csv.Sniffer().sniff(io_string.read(1024))
            io_string.seek(0)
            reader = csv.reader(io_string, dialect)
            
            next(reader, None) # Pula cabeçalho

            criados = 0
            ignorados = 0

            for row in reader:
                if len(row) >= 2:
                    nome = row[0].strip().upper()
                    uf = row[1].strip().upper()
                    
                    # O get_or_create garante que não haverá duplicados
                    _, created = CidadeAtendida.objects.get_or_create(
                        provedor=provedor,
                        nome=nome,
                        uf=uf
                    )
                    
                    if created:
                        criados += 1
                    else:
                        ignorados += 1
            
            messages.success(request, f"Importação concluída: {criados} novas cidades adicionadas. {ignorados} já existiam e foram ignoradas.")
            
        except Exception as e:
            messages.error(request, f"Erro ao processar arquivo: {e}")
            
    return redirect('editar_provedor', pk=provedor_id)

# Nova função para limpar a lista
def excluir_todas_cidades(request, provedor_id):
    # Busca o provedor ou retorna erro 404 se não existir
    provedor = get_object_or_404(Provedor, id=provedor_id)
    
    # Deleta todas as cidades vinculadas a este provedor específico
    provedor.cidades.all().delete()
    
    # Opcional: Adiciona uma mensagem de sucesso para aparecer na tela
    # messages.success(request, "Todas as cidades foram removidas com sucesso.")
    
    # Redireciona de volta para a página de edição
    return redirect('editar_provedor', pk=provedor_id)

def excluir_cidade(request, cidade_id):
    cidade = get_object_or_404(CidadeAtendida, id=cidade_id)
    id_p = cidade.provedor.id
    cidade.delete()
    return redirect('editar_provedor', pk=id_p)
