from django.db import models
from django import forms

class Provedor(models.Model):
    # Identificação
    # Dica: O Django já cria um 'id' automático. Use o seu 'codigo' apenas se for um registro externo.
    codigo = models.CharField(max_length=50, unique=True, null=True, blank=True)
    nome = models.CharField(max_length=255, db_index=True)
    razao_social = models.CharField(max_length=255, null=True, blank=True)
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True, db_index=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    ativo = models.BooleanField(default=True)
    
    # Parceiros_Trunk
    parceiro_bst = models.BooleanField(default=False)
    
    # Meios Físicos
    fibra = models.BooleanField(default=False)
    radio = models.BooleanField(default=False)
    
    # Atuação/Serviços
    link_dedicado = models.BooleanField(default=False)
    link_banda_larga = models.BooleanField(default=False)
    zona_rural = models.BooleanField(default=False)
    
    observacao = models.TextField(blank=True, null=True)
    
    class Meta:
        app_label = 'providers'
        verbose_name = 'Provedor'
        verbose_name_plural = 'Provedores'

    def __str__(self):
        return self.nome
    
class CidadeAtendida(models.Model):
    provedor = models.ForeignKey(Provedor, on_delete=models.CASCADE, related_name='cidades')
    nome = models.CharField(max_length=100, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)

    class Meta:
        app_label = 'providers'  # <--- ADICIONE ISSO
        unique_together = ('provedor', 'nome', 'uf')
        indexes = [
            models.Index(fields=['nome', 'uf']),
        ]

    def __str__(self):
        return f"{self.nome}/{self.uf}"

class Contato(models.Model):
    provedor = models.ForeignKey('Provedor', on_delete=models.CASCADE, related_name='contatos')
    nome = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    # Adicione a linha abaixo aqui:
    prioridade = models.IntegerField(default=1)

    class Meta:
        app_label = 'providers'
    
class HistoricoCusto(models.Model):
    provedor = models.ForeignKey(Provedor, on_delete=models.CASCADE, related_name='historico_custos')
    valor_custo = models.DecimalField(max_digits=10, decimal_places=2)
    data_registro = models.DateField(auto_now_add=True)
    descricao = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        app_label = 'providers'
    
    def __str__(self):
        return f"{self.provedor.nome} - R$ {self.valor_custo}"
    
class ContratoCusto(models.Model):
    # Dados técnicos e contratuais
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    servico = models.CharField(max_length=100)
    ip_fixo = models.CharField(max_length=50, blank=True, null=True)
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2)
    capacidade_mb = models.IntegerField(help_text="Velocidade em MB")
    vigencia_meses = models.IntegerField()
    
    class Meta:
        app_label = 'providers'

    def __str__(self):
        return f"{self.cidade}/{self.uf} - {self.servico} ({self.valor_mensal})"
    