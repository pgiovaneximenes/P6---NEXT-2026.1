# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader

leitor = PdfReader("Projeto-6---Next-Dados/dados/FRA_REP_03.pdf")

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

