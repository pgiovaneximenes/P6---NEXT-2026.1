# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader
from pathlib import Path
import re


pasta_script = Path(__file__).resolve().parent
pasta_dados = pasta_script / "dados"
pasta_brutos = pasta_dados / "brutos"


# Função para ler o texto completo de um PDF
def ler_texto(arquivo_pdf):
    leitor = PdfReader(arquivo_pdf)
    return "\n".join(
        pagina.extract_text() or ""
        for pagina in leitor.pages
    )


# Função para pegar o valor da linha seguinte ao rótulo
def linha_seguinte(linhas, rotulo):
    for i, linha in enumerate(linhas):
        if linha.strip() == rotulo or linha.strip().endswith(" " + rotulo):
            if i + 1 < len(linhas):
                return linhas[i + 1].strip()
    return ""

# Função para pegar o resultado logo depois do rótulo. 
# Pega apenas a palavra que vem imediatamente após o rótulo, para não trazer o resultado de outro ensaio caso duas linhas venham coladas.


def pegar_resultado(texto, rotulo):
    busca = re.search(re.escape(rotulo) + r"\s*(REPROVADO|APROVADO)", texto)
    return busca.group(1) if busca else ""

# Limite de erro (%) usado na análise de indício de fraude
LIMITE_ERRO_FRAUDE = 15



# Função que lê UM pdf e devolve uma linha da tabela
def extrair_laudo(arquivo_pdf):
 
    # Definição das variáveis
    uc = ""
    ordem_serv = ""
    dt_retirada = ""
    data_ensaio = ""
    integridade_lacre = ""
    inspecao_geral = ""
    correspondencia_mod = ""
    ensaio_de_marcha = ""
    erro_ativa_cn = ""
    erro_ativa_ci = ""
    erro_ativa_cp = ""
    resultado_exatidao_ativa = ""
    analise_indicador_fraude = ""
    anomalias = ""

    
    # Leitura do PDF
    texto = ler_texto(arquivo_pdf)
    if not texto.strip():
        raise ValueError("PDF sem texto (pode ser escaneado)")
 
    linhas = texto.splitlines()

    # Dados do cliente
    uc = linha_seguinte(linhas, "UC")
    ordem_serv = linha_seguinte(linhas, "Ordem de Serviço")
    dt_retirada = linha_seguinte(linhas, "Dt. Retirada")
 
    # Data do Ensaio: o valor vem na mesma linha, logo após o rótulo
    for linha in linhas:
        if "Data do Ensaio" in linha:
            data_ensaio = linha.split("Data do Ensaio", 1)[1].strip()
            break


    # Ensaio de Exatidão - Energia Ativa: erros de CN, CI e CP e o resultado do laudo
    padrao = r"(-?\d+,\d+)\s+(-?\d+,\d+)\s+(-?\d+,\d+)\s+(REPROVADO|APROVADO)"
    busca = re.search(padrao, texto)
    if busca:
        erro_ativa_cn, erro_ativa_ci, erro_ativa_cp, resultado_exatidao_ativa = busca.groups()
 
        # Análise de indício de fraude: REPROVADO se algum erro passar do limite
        valores_erro = [
            float(valor.replace(",", "."))
            for valor in (erro_ativa_cn, erro_ativa_ci, erro_ativa_cp)
        ]
        if any(abs(valor) > LIMITE_ERRO_FRAUDE for valor in valores_erro):
            analise_indicador_fraude = "REPROVADO"
        else:
            analise_indicador_fraude = "APROVADO"


    # Resultados dos ensaios
    integridade_lacre = pegar_resultado(texto, "Integridade dos Lacres")
    inspecao_geral = pegar_resultado(texto, "Inspeção Geral Medidor")
    correspondencia_mod = pegar_resultado(texto, "Correspondencia Mod.Aprovado")
    ensaio_de_marcha = pegar_resultado(texto, "Ensaio de Marcha em Vazio")

    # Anomalias: texto entre o título da seção 6 e o da seção 7
    busca_anomalias = re.search(
        r"6\. Anomalia\(s\) Encontrada\(s\) - Descrição:\s*(.*?)\s*7\. Evidências",
        texto,
        re.DOTALL,
    )
    if busca_anomalias:
        itens = [
            linha.strip()
            for linha in busca_anomalias.group(1).splitlines()
            if linha.strip()
        ]
        anomalias = " | ".join(itens)

 
    # Linha da tabela
    return {
        "arquivo": arquivo_pdf.name,
        "uc": uc,
        "ordem_servico": ordem_serv,
        "dt_retirada": dt_retirada,
        "data_ensaio": data_ensaio,
        "integridade_lacres": integridade_lacre,
        "inspecao_geral_medidor": inspecao_geral,
        "correspondencia_mod_aprovado": correspondencia_mod,
        "ensaio_marcha_vazio": ensaio_de_marcha,
        "erro_ativa_cn": erro_ativa_cn,
        "erro_ativa_ci": erro_ativa_ci,
        "erro_ativa_cp": erro_ativa_cp,
        "resultado_exatidao_ativa": resultado_exatidao_ativa,
        "analise_indicador_fraude": analise_indicador_fraude,
        "anomalias": anomalias
    }


# Percorrer todos os PDFs da pasta
laudos, erros = [], []
 
for arquivo_pdf in sorted(pasta_brutos.glob("*.pdf")):
    try:
        laudos.append(extrair_laudo(arquivo_pdf))
    except Exception as e:
        erros.append({"arquivo": arquivo_pdf.name, "erro": str(e)})
 
df_laudos = pd.DataFrame(laudos)
df_erros = pd.DataFrame(erros)


# Mostrar resultado
print(df_laudos.to_string(index=False))

if not df_erros.empty:
    print("\nPDFs com erro na leitura:")
    print(df_erros.to_string(index=False))

# Salvar a tabela em CSV dentro de dados/amostra
pasta_amostra = pasta_dados / "amostra"
pasta_amostra.mkdir(exist_ok=True)   # cria a pasta se ela ainda não existir

#df_laudos.to_csv(
#    pasta_amostra / "laudos.csv",
#    index=False,
#    sep=";",
#    encoding="utf-8-sig",
#)


