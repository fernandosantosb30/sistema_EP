from django.db import models

class Provedor(models.Model):
    # Identificação
    # Dica: O Django já cria um 'id' automático. Use o seu 'codigo' apenas se for um registro externo.
    codigo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nome = models.CharField(max_length=255)
    razao_social = models.CharField(max_length=255, null=True, blank=True)
    cnpj = models.CharField(max_length=20, unique=True, null=True, blank=True) # Adicionado unique=True para evitar duplicidade
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    
    # Meios Físicos
    fibra = models.BooleanField(default=False)
    radio = models.BooleanField(default=False)
    
    # Atuação/Serviços
    link_dedicado = models.BooleanField(default=False)
    link_banda_larga = models.BooleanField(default=False)
    zona_rural = models.BooleanField(default=False)
    
    observacao = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.nome

class CidadeAtendida(models.Model):
    provedor = models.ForeignKey(Provedor, related_name='cidades', on_delete=models.CASCADE)
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)

    def __str__(self):
        return f"{self.cidade} - {self.uf}"

class Contato(models.Model):
    provedor = models.ForeignKey(Provedor, related_name='contatos', on_delete=models.CASCADE)
    nome = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100, null=True, blank=True) # Ajustado para opcional conforme imagem
    telefone = models.CharField(max_length=20, null=True, blank=True) # Ajustado para opcional
    email = models.EmailField(null=True, blank=True) # Ajustado para opcional
    
    # Campos que você já tinha (mantidos)
    prioridade = models.CharField(max_length=1, default='S')
    valor_medio = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    aval_retorno = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.nome} ({self.provedor.nome})"