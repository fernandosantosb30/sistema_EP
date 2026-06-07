from django.db import models

class ContratoCusto(models.Model):
    # Campos que existem na sua tabela providers_contratocusto
    cidade = models.CharField(max_length=100)
    uf = models.CharField(max_length=2)
    servico = models.CharField(max_length=100)
    valor_mensal = models.DecimalField(max_digits=10, decimal_places=2)
    capacidade_mb = models.IntegerField()
    vigencia_meses = models.IntegerField()
    ip_fixo = models.CharField(max_length=50, blank=True, null=True)
    interface = models.CharField(max_length=50, blank=True, null=True) # Campo calculado no DF

    class Meta:
        managed = False  # Importante: Como o Pandas já gerencia os dados, o Django não deve tentar criar a tabela
        db_table = 'providers_contratocusto'