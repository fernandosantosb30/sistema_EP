"""Lógica de auditoria e normalização do banco de provedores."""
from collections import defaultdict

from django.db import IntegrityError
from django.db.models import Count

from providers.models import CidadeAtendida, Provedor
from providers.utils import limpar_nome_cidade, normalizar_texto, normalizar_uf


def coletar_totais():
    return {
        'provedores': Provedor.objects.count(),
        'cidades': CidadeAtendida.objects.count(),
        'sem_cidade': Provedor.objects.annotate(n=Count('cidades')).filter(n=0).count(),
        'sem_contato': Provedor.objects.annotate(n=Count('contatos')).filter(n=0).count(),
        'inativos': Provedor.objects.filter(ativo=False).count(),
    }


def provedores_sem_cidade(limit=50):
    return list(
        Provedor.objects.annotate(n=Count('cidades'))
        .filter(n=0)
        .order_by('nome')
        .values('id', 'nome', 'ativo')[:limit]
    )


def provedores_sem_contato(limit=50):
    return list(
        Provedor.objects.annotate(n=Count('contatos'))
        .filter(n=0)
        .order_by('nome')
        .values('id', 'nome')[:limit]
    )


def cidades_nao_normalizadas(limit=50):
    resultado = []
    for cidade in CidadeAtendida.objects.select_related('provedor').iterator():
        nome_ok = limpar_nome_cidade(cidade.nome, cidade.uf)
        uf_ok = normalizar_uf(cidade.uf)
        if cidade.nome != nome_ok or cidade.uf != uf_ok:
            resultado.append({
                'id': cidade.id,
                'provedor': cidade.provedor.nome,
                'nome_db': cidade.nome,
                'nome_ok': nome_ok,
                'uf_db': cidade.uf,
                'uf_ok': uf_ok,
            })
            if len(resultado) >= limit:
                break
    return resultado


def contar_cidades_nao_normalizadas():
    total = 0
    for cidade in CidadeAtendida.objects.iterator():
        nome_ok = limpar_nome_cidade(cidade.nome, cidade.uf)
        uf_ok = normalizar_uf(cidade.uf)
        if cidade.nome != nome_ok or cidade.uf != uf_ok:
            total += 1
    return total


def provedores_duplicados():
    grupos = defaultdict(list)
    for provedor in Provedor.objects.all().only('id', 'nome', 'ativo'):
        chave = normalizar_texto(provedor.nome)
        if chave:
            grupos[chave].append(provedor)

    return [
        {
            'nome': chave,
            'itens': [
                {'id': p.id, 'nome': p.nome, 'ativo': p.ativo}
                for p in provedores
            ],
        }
        for chave, provedores in grupos.items()
        if len(provedores) > 1
    ]


def ufs_invalidas(limit=50):
    resultado = []
    for cidade in CidadeAtendida.objects.select_related('provedor').iterator():
        uf_ok = normalizar_uf(cidade.uf)
        if not uf_ok or len(uf_ok) != 2:
            resultado.append({
                'id': cidade.id,
                'provedor': cidade.provedor.nome,
                'cidade': cidade.nome,
                'uf': cidade.uf,
            })
            if len(resultado) >= limit:
                break
    return resultado


def normalizar_cidades_banco(aplicar=False):
    """
    Corrige nomes/UFs de CidadeAtendida.
    Retorna dict com estatísticas e pendências.
    """
    stats = {
        'analisadas': 0,
        'corrigidas': 0,
        'duplicadas_removidas': 0,
        'erros': 0,
        'pendencias': [],
    }

    for cidade in CidadeAtendida.objects.select_related('provedor').iterator():
        stats['analisadas'] += 1
        nome_ok = limpar_nome_cidade(cidade.nome, cidade.uf)
        uf_ok = normalizar_uf(cidade.uf)

        if not nome_ok or len(uf_ok) != 2:
            stats['pendencias'].append({
                'id': cidade.id,
                'provedor': cidade.provedor.nome,
                'nome_db': cidade.nome,
                'uf_db': cidade.uf,
                'motivo': 'nome ou UF inválido após limpeza',
            })
            continue

        if cidade.nome == nome_ok and cidade.uf == uf_ok:
            continue

        if not aplicar:
            stats['corrigidas'] += 1
            continue

        duplicata = CidadeAtendida.objects.filter(
            provedor_id=cidade.provedor_id,
            nome=nome_ok,
            uf=uf_ok,
        ).exclude(pk=cidade.pk).exists()

        if duplicata:
            cidade.delete()
            stats['duplicadas_removidas'] += 1
            continue

        cidade.nome = nome_ok
        cidade.uf = uf_ok
        try:
            cidade.save(update_fields=['nome', 'uf'])
            stats['corrigidas'] += 1
        except IntegrityError:
            stats['erros'] += 1
            stats['pendencias'].append({
                'id': cidade.id,
                'provedor': cidade.provedor.nome,
                'nome_db': cidade.nome,
                'uf_db': cidade.uf,
                'motivo': 'conflito de unicidade (provedor, cidade, uf)',
            })

    return stats
