import unicodedata
import pandas as pd

def normalizar_texto(texto):
    if not texto or pd.isna(texto): 
        return ""
    nfkd_form = unicodedata.normalize('NFKD', str(texto))
    texto_limpo = "".join([c for c in nfkd_form if not unicodedata.combining(c)])
    return texto_limpo.replace('-', ' ').upper().strip()