from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from providers.models import Provedor, CidadeAtendida, Contato, PrestadorServico, CidadeAtendidaPrestador, ContratoCusto

class Command(BaseCommand):
    help = 'Cria dados fictícios somente no banco SQLite local.'

    @transaction.atomic
    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if db['ENGINE'] != 'django.db.backends.sqlite3' or not settings.DEBUG:
            raise CommandError('Dados demonstrativos permitidos apenas no ambiente local.')
        p, _ = Provedor.objects.get_or_create(codigo='DEMO-001', defaults={'nome': 'Provedor Demonstração'})
        CidadeAtendida.objects.get_or_create(provedor=p, nome='CIDADE DEMONSTRACAO', uf='RS')
        Contato.objects.get_or_create(provedor=p, nome='Contato Fictício', defaults={'email': 'contato@example.invalid'})
        s, _ = PrestadorServico.objects.get_or_create(nome_fantasia='Prestador Demonstração', defaults={'razao_social': 'Empresa Fictícia', 'contato': 'Pessoa Fictícia', 'telefone': '', 'email': 'servicos@example.invalid'})
        CidadeAtendidaPrestador.objects.get_or_create(prestador=s, nome='CIDADE DEMONSTRACAO', uf='RS')
        ContratoCusto.objects.get_or_create(cidade='CIDADE DEMONSTRACAO', uf='RS', velocidade='100', tipo_servico='Link', meio_fisico='Fibra', defaults={'mensal': 100})
        self.stdout.write(self.style.SUCCESS('Dados fictícios preparados. Nenhum usuário ou senha foi criado.'))
