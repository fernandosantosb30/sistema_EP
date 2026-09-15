import io
import re
import unicodedata
import difflib

import pandas as pd

# Encodings comuns em CSV exportado pelo Excel no Windows (MS-DOS / ANSI)
ENCODINGS_CSV = ('utf-8-sig', 'cp1252', 'latin-1')

# Aliases aceitos para colunas do CSV (qualquer capitalização)
ALIAS_COLUNAS = {
    'cidade': ('cidade', 'municipio', 'município', 'city', 'nome_cidade', 'local'),
    'uf': ('uf', 'estado', 'sigla', 'sigla_uf', 'uf_sigla'),
    'provedor': ('provedor', 'parceiro', 'fornecedor', 'provider', 'operadora', 'empresa'),
}


def normalizar_texto(texto):
    """Remove acentos, padroniza espaços e caixa para comparação."""
    if not texto or pd.isna(texto):
        return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    texto_limpo = "".join(c for c in nfkd_form if not unicodedata.combining(c))
    texto_limpo = texto_limpo.replace('-', ' ')
    texto_limpo = re.sub(r'\s+', ' ', texto_limpo)
    return texto_limpo.upper().strip()


def limpar_nome_cidade(nome, uf=None):
    """
    Normaliza nome de cidade importado fora do Django.
    Remove lixo de encoding e UF duplicada no campo nome.
    """
    nome = normalizar_texto(nome)
    nome = re.sub(r'[^A-Z0-9 ]', ' ', nome)
    nome = re.sub(r'\s+', ' ', nome).strip()

    if uf:
        uf = str(uf).strip().upper()[:2]
        for separador in (' - ', ' '):
            sufixo = f'{separador}{uf}'
            if nome.endswith(sufixo):
                nome = nome[:-len(sufixo)].strip()

    return nome


def normalizar_uf(uf):
    """Padroniza UF para 2 letras maiúsculas."""
    uf = normalizar_texto(uf)
    uf = re.sub(r'[^A-Z]', '', uf)
    return uf[:2]


def celula_csv(valor):
    """Lê célula do CSV tratando vazios e NaN do pandas."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ""
    texto = str(valor).strip()
    return "" if texto.lower() == 'nan' else texto


def decodificar_csv(raw_data):
    """Decodifica bytes de CSV tentando encodings típicos do Windows/MS-DOS."""
    for encoding in ENCODINGS_CSV:
        try:
            return raw_data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(
        "Formato de arquivo não suportado. Salve o CSV como UTF-8 ou ANSI (Windows)."
    )


def ler_dataframe_csv(conteudo):
    """
    Lê CSV MS-DOS/Windows (;) ou padrão (,).
    Aceita delimitador automático como fallback.
    """
    buffer = io.StringIO(conteudo)
    try:
        df = pd.read_csv(buffer, sep=';', engine='python', on_bad_lines='skip')
        if df.shape[1] <= 1:
            raise ValueError('delimitador incorreto')
    except Exception:
        buffer.seek(0)
        df = pd.read_csv(buffer, sep=None, engine='python', on_bad_lines='skip')

    df.columns = [str(c).lower().strip() for c in df.columns]
    return df


def padronizar_colunas(df):
    """Mapeia aliases de colunas para cidade, uf e provedor."""
    colunas = {
        c: normalizar_texto(c).replace(' ', '_').lower()
        for c in df.columns
    }

    renomear = {}
    for destino, aliases in ALIAS_COLUNAS.items():
        for coluna, coluna_norm in colunas.items():
            if coluna_norm in aliases or coluna_norm.replace('_', '') in aliases:
                renomear[coluna] = destino
                break

    return df.rename(columns=renomear)


def provedor_coincide(nome_csv, nome_db):
    """
    Compara nomes de provedor de forma flexível.
    Ex.: VALENET == VALE NET; ON NET == ONNET.
    """
    a = normalizar_texto(nome_csv)
    b = normalizar_texto(nome_db)
    if not a:
        return True
    if not b:
        return False
    if a == b or a in b or b in a:
        return True

    a_compact = a.replace(' ', '')
    b_compact = b.replace(' ', '')
    if a_compact == b_compact or a_compact in b_compact or b_compact in a_compact:
        return True

    return bool(difflib.get_close_matches(a, [b], n=1, cutoff=0.82))


def construir_mapa_cidades(cidades_queryset):
    """
    Agrupa cidades do banco por (nome_normalizado, uf).
    Suporta vários provedores na mesma cidade.
    """
    mapa = {}
    for cidade in cidades_queryset:
        chave = (normalizar_texto(cidade.nome), cidade.uf.strip().upper())
        mapa.setdefault(chave, []).append(cidade)
    return mapa


def buscar_cidades_no_mapa(mapa_cidades, cidade_input, uf_input, cutoff=0.75):
    """
    Busca cidades no mapa: primeiro exata, depois a mais próxima na mesma UF.
  """
    chave = (cidade_input, uf_input)
    if chave in mapa_cidades:
        return mapa_cidades[chave]

    nomes_uf = sorted({nome for (nome, uf) in mapa_cidades if uf == uf_input})
    if not nomes_uf:
        return []

    match = difflib.get_close_matches(cidade_input, nomes_uf, n=1, cutoff=cutoff)
    if match:
        return mapa_cidades.get((match[0], uf_input), [])

    return []
