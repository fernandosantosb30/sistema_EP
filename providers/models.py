from django.db import models
from django import forms
from .utils import normalizar_texto

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
    provedor = models.ForeignKey('Provedor', on_delete=models.CASCADE, related_name='cidades')
    nome = models.CharField(max_length=100, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)

    class Meta:
        app_label = 'providers'
        unique_together = ('provedor', 'nome', 'uf')
        indexes = [
            models.Index(fields=['nome', 'uf']),
        ]

    def save(self, *args, **kwargs):
        # Garante que o nome esteja sempre no padrão (sem acentos, maiúsculo)
        self.nome = normalizar_texto(self.nome)
        # Garante que a UF seja sempre maiúscula e sem espaços
        self.uf = self.uf.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome}/{self.uf}"

class Contato(models.Model):
    provedor = models.ForeignKey('Provedor', on_delete=models.CASCADE, related_name='contatos')
    nome = models.CharField(max_length=100)
    cargo = models.CharField(max_length=100, null=True, blank=True)
    telefone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    class Meta:
        app_label = 'providers'
       
class ContratoCusto(models.Model):
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    velocidade = models.CharField(max_length=50) # Removi o db_column
    tipo_servico = models.CharField(max_length=100) # Removi o db_column
    meio_fisico = models.CharField(max_length=50)
    mensal = models.DecimalField(max_digits=10, decimal_places=2) # Removi o db_column

    class Meta:
        db_table = 'providers_contratocusto'

    def __str__(self):
        return f"{self.cidade}/{self.uf} - {self.velocidade}"
    
class InboxContrato(models.Model):
    texto_original = models.TextField()
    dados_extraidos = models.JSONField() # Aqui guardamos o JSON que a IA devolver
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Coleta de {self.data_criacao}"


class PrestadorServico(models.Model):
    """Cadastro de empresas parceiras que prestam serviços de campo."""
    razao_social = models.CharField(max_length=255)
    nome_fantasia = models.CharField(max_length=255)
    cnpj = models.CharField(max_length=18, unique=True, null=True, blank=True, db_index=True)
    contato = models.CharField(max_length=100)
    telefone = models.CharField(max_length=20)
    email = models.EmailField()
    instalacao_satelite = models.BooleanField(default=False)
    teste_rede = models.BooleanField(default=False)
    possui_documentacao = models.BooleanField(default=False)
    observacoes = models.TextField(blank=True)
    data_cadastro = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Prestador de serviço'
        verbose_name_plural = 'Prestadores de serviço'
        ordering = ['nome_fantasia']

    def __str__(self):
        return self.nome_fantasia


class CidadeAtendidaPrestador(models.Model):
    prestador = models.ForeignKey(
        PrestadorServico,
        on_delete=models.CASCADE,
        related_name='cidades_atendidas',
    )
    nome = models.CharField(max_length=100, db_index=True)
    uf = models.CharField(max_length=2, db_index=True)

    class Meta:
        verbose_name = 'Cidade atendida pelo prestador'
        verbose_name_plural = 'Cidades atendidas pelos prestadores'
        unique_together = ('prestador', 'nome', 'uf')

    def save(self, *args, **kwargs):
        self.nome = normalizar_texto(self.nome)
        self.uf = self.uf.upper().strip()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.nome}/{self.uf}"
