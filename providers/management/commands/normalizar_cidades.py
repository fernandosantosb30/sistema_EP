from django.core.management.base import BaseCommand

from providers.services.auditoria import normalizar_cidades_banco


class Command(BaseCommand):
    help = (
        'Normaliza nomes e UFs das cidades atendidas. '
        'Por padrão roda em modo simulação (dry-run).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--aplicar',
            action='store_true',
            help='Grava as correções no banco (sem esta flag, apenas simula).',
        )

    def handle(self, *args, **options):
        aplicar = options['aplicar']
        modo = 'APLICANDO' if aplicar else 'SIMULACAO (dry-run)'

        self.stdout.write(self.style.MIGRATE_HEADING(f'=== NORMALIZAR CIDADES — {modo} ==='))

        if not aplicar:
            self.stdout.write(
                'Nenhuma alteração será salva. Use --aplicar para gravar no banco.\n'
            )

        stats = normalizar_cidades_banco(aplicar=aplicar)

        self.stdout.write(f"Cidades analisadas: {stats['analisadas']}")
        self.stdout.write(f"Correções {'aplicadas' if aplicar else 'previstas'}: {stats['corrigidas']}")

        if aplicar:
            self.stdout.write(f"Duplicatas removidas: {stats['duplicadas_removidas']}")
            self.stdout.write(f"Erros: {stats['erros']}")

        if stats['pendencias']:
            self.stdout.write(self.style.WARNING('\n=== PENDENCIAS (revisão manual) ==='))
            for item in stats['pendencias'][:50]:
                self.stdout.write(
                    f"  id={item['id']} | {item['provedor']} | "
                    f"\"{item['nome_db']}\" / uf=\"{item['uf_db']}\" | {item['motivo']}"
                )
            restantes = len(stats['pendencias']) - 50
            if restantes > 0:
                self.stdout.write(f'  ... e mais {restantes} pendência(s).')

        if aplicar:
            self.stdout.write(self.style.SUCCESS('\nNormalização concluída.'))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '\nSimulação concluída. Rode com --aplicar para gravar as correções.'
                )
            )
