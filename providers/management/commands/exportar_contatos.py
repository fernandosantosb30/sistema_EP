import csv
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Count
from django.db.models.fields.files import FieldFile

from providers.models import Provedor


CAMPOS_PROVEDOR = [
    'provedor_id',
    'codigo',
    'nome',
    'razao_social',
    'cnpj',
    'ativo',
    'parceiro_bst',
    'fibra',
    'radio',
    'link_dedicado',
    'link_banda_larga',
    'zona_rural',
    'observacao',
    'data_cadastro',
    'cidades',
    'qtd_cidades',
    'qtd_contatos',
    'tem_contato',
]


def _sim_nao(valor):
    return 'sim' if valor else 'nao'


def _celula(valor):
    if valor is None:
        return ''
    if isinstance(valor, bool):
        return _sim_nao(valor)
    if isinstance(valor, Decimal):
        return str(valor)
    if isinstance(valor, datetime):
        return valor.isoformat(sep=' ', timespec='seconds')
    if isinstance(valor, date):
        return valor.isoformat()
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    if isinstance(valor, FieldFile):
        return valor.name or ''
    return str(valor)


def _cidades(provedor):
    return ' | '.join(
        f'{cidade.nome}/{cidade.uf}'
        for cidade in provedor.cidades.all()
    )


def _linha_provedor(provedor):
    qtd_contatos = provedor.qtd_contatos
    return [
        provedor.id,
        provedor.codigo or '',
        provedor.nome,
        provedor.razao_social or '',
        provedor.cnpj or '',
        _sim_nao(provedor.ativo),
        _sim_nao(provedor.parceiro_bst),
        _sim_nao(provedor.fibra),
        _sim_nao(provedor.radio),
        _sim_nao(provedor.link_dedicado),
        _sim_nao(provedor.link_banda_larga),
        _sim_nao(provedor.zona_rural),
        provedor.observacao or '',
        _celula(provedor.data_cadastro),
        _cidades(provedor),
        provedor.qtd_cidades,
        qtd_contatos,
        _sim_nao(qtd_contatos > 0),
    ]


def _escrever_csv(caminho, cabecalho, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open('w', encoding='utf-8-sig', newline='') as arquivo:
        writer = csv.writer(arquivo, delimiter=';')
        writer.writerow(cabecalho)
        writer.writerows(linhas)


def _exportar_modelo(model, caminho):
    campos = [field.name for field in model._meta.fields]
    linhas = []
    for obj in model.objects.all().order_by('pk'):
        linhas.append([_celula(getattr(obj, campo)) for campo in campos])
    _escrever_csv(caminho, campos, linhas)
    return len(linhas)


class Command(BaseCommand):
    help = (
        'Exporta todos os registros do app providers em CSV, '
        'incluindo arquivos para cruzar provedor e contato.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--pasta',
            default=str(Path(settings.BASE_DIR) / 'export_csv'),
            help='Pasta onde os CSVs serão gravados.',
        )
        parser.add_argument(
            '--apenas-ativos',
            action='store_true',
            help='Nos arquivos de cruzamento, inclui só provedores ativos.',
        )

    def handle(self, *args, **options):
        pasta = Path(options['pasta'])
        pasta.mkdir(parents=True, exist_ok=True)

        self.stdout.write(self.style.MIGRATE_HEADING('=== TODAS AS TABELAS ==='))
        for model in apps.get_app_config('providers').get_models():
            nome = f'{model._meta.db_table}.csv'
            qtd = _exportar_modelo(model, pasta / nome)
            self.stdout.write(f'{nome}: {qtd} registros')

        queryset = (
            Provedor.objects.annotate(
                qtd_contatos=Count('contatos', distinct=True),
                qtd_cidades=Count('cidades', distinct=True),
            )
            .prefetch_related('contatos', 'cidades')
            .order_by('nome')
        )
        if options['apenas_ativos']:
            queryset = queryset.filter(ativo=True)

        provedores = list(queryset)
        linhas_provedores = [_linha_provedor(p) for p in provedores]
        linhas_sem_contato = [
            linha for linha in linhas_provedores if linha[-1] == 'nao'
        ]
        linhas_contatos = []
        for provedor in provedores:
            for contato in provedor.contatos.all():
                linhas_contatos.append([
                    contato.id,
                    provedor.id,
                    provedor.nome,
                    contato.nome,
                    contato.cargo or '',
                    contato.telefone or '',
                    contato.email or '',
                ])

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== CRUZAMENTO ==='))
        arquivos = {
            pasta / 'provedores.csv': (CAMPOS_PROVEDOR, linhas_provedores),
            pasta / 'contatos.csv': (
                [
                    'contato_id',
                    'provedor_id',
                    'provedor_nome',
                    'contato_nome',
                    'contato_cargo',
                    'contato_telefone',
                    'contato_email',
                ],
                linhas_contatos,
            ),
            pasta / 'provedores_sem_contato.csv': (
                CAMPOS_PROVEDOR,
                linhas_sem_contato,
            ),
        }
        for caminho, (cabecalho, linhas) in arquivos.items():
            _escrever_csv(caminho, cabecalho, linhas)
            self.stdout.write(f'{caminho.name}: {len(linhas)} linhas -> {caminho}')

        total = len(provedores)
        sem_contato = len(linhas_sem_contato)
        com_contato = total - sem_contato
        self.stdout.write(self.style.SUCCESS(
            f'\nProvedores: {total} | com contato: {com_contato} | '
            f'sem contato: {sem_contato}'
        ))
        self.stdout.write(f'Pasta: {pasta}')
        self.stdout.write(
            'Ligue provedores.csv e contatos.csv pelo campo provedor_id.'
        )
