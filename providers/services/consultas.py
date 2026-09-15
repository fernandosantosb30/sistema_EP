"""Regras compartilhadas pela tela e pelos arquivos de consulta."""
import csv
import io
import re
from decimal import Decimal

from django.db.models import Q
from django.http import HttpResponse
from providers.models import Provedor, CidadeAtendida
from providers.utils import normalizar_texto, padronizar_colunas, decodificar_csv
import pandas as pd

UFS = set('AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO'.split())


def validar_uf(value):
    uf = str(value).strip().upper()
    if uf not in UFS:
        raise ValueError('UF inválida. Informe uma sigla brasileira de duas letras.')
    return uf


def filtrar_cobertura(params):
    provedores = Provedor.objects.prefetch_related('contatos', 'cidades').all()
    cidades = CidadeAtendida.objects.all()
    fornecedor = params.get('fornecedor', '').strip()
    uf = params.get('uf', '').strip().upper()
    termos = [normalizar_texto(params.get(f'cidade{i}', '')) for i in range(1, 4)]
    termos = [t for t in termos if t]
    if fornecedor:
        provedores = provedores.filter(Q(nome__icontains=fornecedor) | Q(razao_social__icontains=fornecedor))
    if uf:
        cidades = cidades.filter(uf__iexact=uf)
        provedores = provedores.filter(pk__in=cidades.values('provedor_id'))
    for termo in termos:
        # Todas as cidades pedidas devem ser atendidas dentro da UF selecionada.
        provedores = provedores.filter(pk__in=cidades.filter(nome__icontains=termo).values('provedor_id'))
    if termos:
        condicao = Q()
        for termo in termos:
            condicao |= Q(nome__icontains=termo)
        cidades = cidades.filter(condicao)
    return provedores.order_by('nome'), cidades.order_by('provedor_id', 'uf', 'nome')


def velocidade_normalizada(value):
    texto = str(value).strip().upper().replace(',', '.')
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*(GBPS|GB|G|MBPS|MB|M|KBPS|KB|K)?', texto)
    if not match:
        return texto
    numero = Decimal(match[1])
    unidade = match[2] or 'MB'
    if unidade.startswith('G'):
        numero *= 1000
    elif unidade.startswith('K'):
        numero /= 1000
    return str(numero.normalize())


def calcular_custo(contratos, params):
    cidade = normalizar_texto(params.get('cidade', ''))
    uf = str(params.get('uf', '')).strip().upper()
    if uf:
        validar_uf(uf)
    servico = normalizar_texto(params.get('servico', params.get('tipo_servico', '')))
    meio = normalizar_texto(params.get('meio_fisico', ''))
    velocidade = str(params.get('velocidade', '')).strip()
    base = [c for c in contratos if
            (not servico or normalizar_texto(c['tipo_servico']) == servico) and
            (not meio or normalizar_texto(c['meio_fisico']) == meio) and
            (not velocidade or velocidade_normalizada(c['velocidade']) == velocidade_normalizada(velocidade))]
    if uf:
        base = [c for c in base if c['uf'].strip().upper() == uf]
    if cidade:
        base = [c for c in base if normalizar_texto(c['cidade']) == cidade]
        # Cidade sem UF ambígua não deve misturar localidades homônimas.
        if not uf and len({c['uf'].strip().upper() for c in base}) > 1:
            raise ValueError('Informe a UF: há cidades com esse nome em mais de um estado.')
    valores = [Decimal(str(c['mensal'])) for c in base]
    return {
        'custo_medio': float(round(sum(valores) / len(valores), 2)) if valores else 0,
        'quantidade_contratos': len(valores),
        'nivel': ('Cidade' if cidade else 'Estado' if uf else 'Geral') if valores else 'Sem dados',
    }


def resposta_csv(filename, linhas):
    buffer = io.StringIO(newline='')
    writer = csv.writer(buffer, delimiter=';')
    for linha in linhas:
        # Evita fórmulas executáveis em células originadas de dados cadastrados.
        writer.writerow(["'" + v if isinstance(v, str) and v.lstrip().startswith(('=', '+', '-', '@')) else v for v in linha])
    response = HttpResponse(buffer.getvalue().encode('utf-8-sig'), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def ler_csv_validado(arquivo, obrigatorias):
    if arquivo is None:
        raise ValueError('Selecione um arquivo CSV.')
    if arquivo.size > 5 * 1024 * 1024:
        raise ValueError('O arquivo deve ter no máximo 5 MB.')
    try:
        texto = decodificar_csv(arquivo.read())
        delimitador = csv.Sniffer().sniff(texto[:8192], delimiters=';,\t').delimiter
        df = pd.read_csv(io.StringIO(texto), sep=delimitador, dtype=str, keep_default_na=False, on_bad_lines='error')
        df.columns = [c.strip().lower() for c in df.columns]
        df = padronizar_colunas(df)
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise ValueError('CSV inválido. Confira a codificação, o cabeçalho e as colunas de cada linha.') from exc
    if not set(obrigatorias).issubset(df.columns):
        raise ValueError('Colunas obrigatórias: ' + ', '.join(obrigatorias))
    if df.empty:
        raise ValueError('O CSV não contém registros.')
    for numero, (_, row) in enumerate(df.iterrows(), 2):
        if any(not str(row[c]).strip() for c in obrigatorias):
            raise ValueError(f'Linha {numero}: preencha todos os campos obrigatórios.')
        if 'uf' in obrigatorias:
            validar_uf(row['uf'])
    return df
