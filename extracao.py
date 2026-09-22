# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader
from pathlib import Path


pasta_script = Path(__file__).resolve().parent
arquivo_pdf = pasta_script / "dados" / "FRA_REP_03.pdf"

leitor = PdfReader(arquivo_pdf)

texto_completo = "\n".join(
    pagina.extract_text() or ""
    for pagina in leitor.pages
)

#Identificador do laudo ; Ordem de serviço
# Pegar resultado dos ensaios
linhas = texto_completo.splitlines()

for i, linha in enumerate(linhas):

    if "Ordem de Serviço" in linha:
        ordem_serv = linhas[i + 1]

    if "Integridade dos Lacres" in linha:
        etapa1_aprov = linhas[i]

    if "Correspondencia Mod.Aprovado" in linha:
        etapa2_aprov = linhas[i]

    if "Inspeção Geral Medidor" in linha:
        etapa3_aprov = linhas[i]

    if "Ensaio de Marcha em Vazio" in linha:
        etapa4_aprov = linhas[i]

print("Ordem de Serviço:", ordem_serv)
print("Etapa 1:", etapa1_aprov)
print("Etapa 2:", etapa2_aprov)
print("Etapa 3:", etapa3_aprov)
print("Etapa 4:", etapa4_aprov)
print("-" * 50)