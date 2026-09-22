# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader
from pathlib import Path


pasta_script = Path(__file__).resolve().parent
arquivo_pdf = pasta_script / "dados" / "FRA_REP_02.pdf"

#Leitura do PDF
leitor = PdfReader(arquivo_pdf)

texto_completo = "\n".join(
    pagina.extract_text() or ""
    for pagina in leitor.pages
)

#Definição das variáveis
ordem_serv = ""
etapa1_aprov = ""
etapa2_aprov = ""
etapa3_aprov = ""
etapa4_aprov = ""

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

    if "Ordem de Serviço" in linha:
        ordem_serv = linhas[i + 1]

    if "Integridade dos Lacres" in linha:
        etapa1_aprov = pegar_resultado(linha)

    if "Correspondencia Mod.Aprovado" in linha:
        etapa2_aprov = pegar_resultado(linha)

    if "Inspeção Geral Medidor" in linha:
        etapa3_aprov = pegar_resultado(linha)

    if "Ensaio de Marcha em Vazio" in linha:
        etapa4_aprov = pegar_resultado(linha)

# Criar uma tabela
dados = {
    "Ordem de Serviço": [ordem_serv],
    "Integridade dos Lacres": [etapa1_aprov],
    "Correspondência do Modelo": [etapa2_aprov],
    "Inspeção Geral": [etapa3_aprov],
    "Marcha em Vazio": [etapa4_aprov]
 }

df = pd.DataFrame(dados)


# Mostrar resultado
print(df.to_string(index=False))
