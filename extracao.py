# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader
from pathlib import Path
import re


pasta_script = Path(__file__).resolve().parent
arquivo_pdf = pasta_script / "dados" / "FRA_REP_02.pdf"

#Leitura do PDF
leitor = PdfReader(arquivo_pdf)

texto_completo = "\n".join(
    pagina.extract_text() or ""
    for pagina in leitor.pages
)

#Pegar erro energia ativa e resultado
padrao = r'(-?\d+,\d+)\s+(-?\d+,\d+)\s+(-?\d+,\d+)'

resultado = re.search(padrao, texto_completo)

if resultado:
    erros = resultado.groups()

    for valor in erros:
        erro = float(valor.replace(',', '.'))

        if abs(erro) > 15:
            status = "REPROVADO"
        else:
            status = "APROVADO"

        print(f"Erro de Energia Ativa: {erro:.2f} - {status}")

#Definição das variáveis
uc = ""
ordem_serv = ""
data_retirada = ""
Integridade_lacre = ""
Correspondencia_Mod = ""
Inspeção_geral = ""
Ensaio_de_marcha = ""


# Função para pegar somente o resultado
def pegar_resultado(linha):

    if "REPROVADO" in linha:
        return "REPROVADO"

    if "APROVADO" in linha:
        return "APROVADO"

    return ""

#Identificador do laudo ; Ordem de serviço
# Pegar resultado dos ensaios
linhas = texto_completo.splitlines()

for i, linha in enumerate(linhas):

    if "UC" in linha.split():
        uc = linhas[i + 1]

    if "Ordem de Serviço" in linha:
        ordem_serv = linhas[i + 1]

    if "Dt. Retirada" in linha:
        data_retirada = linhas[i + 1]

    if "Integridade dos Lacres" in linha:
        Integridade_lacre = pegar_resultado(linha)

    if "Correspondencia Mod.Aprovado" in linha:
        Correspondencia_Mod = pegar_resultado(linha)

    if "Inspeção Geral Medidor" in linha:
        Inspeção_Geral = pegar_resultado(linha)

    if "Ensaio de Marcha em Vazio" in linha:
        Ensaio_de_marcha = pegar_resultado(linha)

    
# Criar uma tabela
dados = {
    "uc": [uc],
    "Ordem de Serviço": [ordem_serv],
    "Data de Retirada": [data_retirada],
    "Integridade dos Lacres": [Integridade_lacre],
    "Correspondência do Modelo": [Correspondencia_Mod],
    "Inspeção Geral": [Inspeção_Geral],
    "Marcha em Vazio": [Ensaio_de_marcha]
 }

df = pd.DataFrame(dados)

# Mostrar resultado
print(df.to_string(index=False))





