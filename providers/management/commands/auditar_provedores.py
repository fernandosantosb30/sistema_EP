from django.core.management.base import BaseCommand

from providers.services.auditoria import (
    cidades_nao_normalizadas,
    coletar_totais,
    contar_cidades_nao_normalizadas,
    provedores_duplicados,
    provedores_sem_cidade,
    provedores_sem_contato,
    ufs_invalidas,
)


class Command(BaseCommand):
    help = 'Audita o banco de provedores e lista inconsistências.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limite',
            type=int,
            default=30,
            help='Quantidade máxima de itens por seção (padrão: 30).',
        )

    def handle(self, *args, **options):
        limite = options['limite']
        totais = coletar_totais()

        self.stdout.write(self.style.MIGRATE_HEADING('=== TOTAIS ==='))
        self.stdout.write(f"Provedores: {totais['provedores']}")
        self.stdout.write(f"Cidades atendidas: {totais['cidades']}")
        self.stdout.write(f"Sem cidade: {totais['sem_cidade']}")
        self.stdout.write(f"Sem contato: {totais['sem_contato']}")
        self.stdout.write(f"Inativos: {totais['inativos']}")

        nao_norm = contar_cidades_nao_normalizadas()
        self.stdout.write(f"Cidades fora do padrão: {nao_norm}")

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== PROVEDORES SEM CIDADE ==='))
        for item in provedores_sem_cidade(limite):
            self.stdout.write(
                f"  id={item['id']} | {item['nome']} | ativo={item['ativo']}"
            )

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== PROVEDORES SEM CONTATO ==='))
        for item in provedores_sem_contato(limite):
            self.stdout.write(f"  id={item['id']} | {item['nome']}")

        self.stdout.write(self.style.MIGRATE_HEADING('\n=== CIDADES NAO NORMALIZADAS ==='))
        for item in cidades_nao_normalizadas(limite):
            self.stdout.write(
                f"  id={item['id']} | {item['provedor']} | "
                f"DB=\"{item['nome_db']}\" -> \"{item['nome_ok']}\" | "
                f"UF {item['uf_db']} -> {item['uf_ok']}"
            )

        invalidas = ufs_invalidas(limite)
        if invalidas:
            self.stdout.write(self.style.MIGRATE_HEADING('\n=== UFS INVALIDAS ==='))
            for item in invalidas:
                self.stdout.write(
                    f"  id={item['id']} | {item['provedor']} | "
                    f"{item['cidade']} | uf=\"{item['uf']}\""
                )

        duplicados = provedores_duplicados()
        if duplicados:
            self.stdout.write(self.style.MIGRATE_HEADING('\n=== PROVEDORES DUPLICADOS ==='))
            for grupo in duplicados[:limite]:
                itens = ', '.join(
                    f"id={i['id']}({i['nome']})" for i in grupo['itens']
                )
                self.stdout.write(f"  {grupo['nome']}: {itens}")

        self.stdout.write(self.style.SUCCESS('\nAuditoria concluída.'))
