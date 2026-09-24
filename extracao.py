# Objetivo de realizar a extração dos dados em pdf para o formato de tabela.

import pandas as pd
from pypdf import PdfReader
from pathlib import Path
import re
import unicodedata
from datetime import datetime


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

def extrair_data(texto, rotulo):
    padrao = re.search(
        re.escape(rotulo) + r"(.*?)(?=\n|$)",
        texto,
        re.IGNORECASE
    )

    if not padrao:
        return "", "NÃO ENCONTRADA"

    trecho = padrao.group(1).strip()

    # Corrige possível separação indevida do primeiro dígito do dia.
    # Exemplo: "1 8/11/2030" -> "18/11/2030"
    trecho = re.sub(
        r"(?<=\d)\s+(?=\d/)",
        "",
        trecho
    )

    busca_data = re.search(
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
        trecho
    )

    if not busca_data:
        return trecho, "FORMATO INVÁLIDO"

    data = busca_data.group(1)

    try:
        datetime.strptime(data, "%d/%m/%Y")
        return data, "OK"
    except ValueError:
        return data, "DATA INVÁLIDA"

    
# Função para pegar o resultado logo depois do rótulo. 
# Pega apenas a palavra que vem imediatamente após o rótulo, para não trazer o resultado de outro ensaio caso duas linhas venham coladas.


def pegar_resultado(texto, rotulo):
    busca = re.search(re.escape(rotulo) + r"\s*(REPROVADO|APROVADO)", texto)
    return busca.group(1) if busca else ""

# Limite provisório para análise exploratória.
# Deve ser validado com a área demandante.
LIMITE_ERRO_ANALISE = 15


# Palavras-chave das anomalias (escritas sem acento e em minúsculas).
# Cada item é uma expressão regular procurada em cada anomalia do laudo.
ANOMALIAS_FRAUDE = [
    r"tampa.*forcad",                         # tampa forçada
    r"tampa.*abert",                          # tampa aberta
    r"by.?pass",                              # by-pass / bypass / by pass
    r"nao registra corretamente o consumo",   # medidor não registra corretamente
]
 
ANOMALIAS_DEFEITO = [
    r"display.*apagad",                       # display apagado
    r"dispositivo de saida.*apagad",          # dispositivo de saída apagado
]
 
# Textos da classificação final
SEM_INDICIO = "Sem indício identificado"
INDICIO_FRAUDE = "Possível fraude/manipulação"
INDICIO_DEFEITO = "Possível defeito"
ANALISE_MANUAL = "Revisão manual"



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
    analise_exatidao = ""
    anomalias = ""
    conclusao = ""
    
    # Leitura do PDF
    texto = ler_texto(arquivo_pdf)
    if not texto.strip():
        raise ValueError("PDF sem texto (pode ser escaneado)")
 
    linhas = texto.splitlines()

    # Dados do cliente
    uc = linha_seguinte(linhas, "UC")
    ordem_serv = linha_seguinte(linhas, "Ordem de Serviço").strip().zfill(12)
    dt_retirada = linha_seguinte(linhas, "Dt. Retirada")
 
    # Data do Ensaio: o valor vem na mesma linha, logo após o rótulo
    data_ensaio, validacao_data_ensaio = extrair_data(
    texto,
    "Data do Ensaio"
)


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
        if any(abs(valor) > LIMITE_ERRO_ANALISE for valor in valores_erro):
            analise_exatidao = "REPROVADO"
        else:
            analise_exatidao = "APROVADO"


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

    # Conclusão: texto entre a seção 8 e "Observações Complementares"
    busca_conclusao = re.search(
    r"Observações Complementares\s*"
    r"(?:Inexistente\.)?\s*"
    r"(.*?)"
    r"\s*FIM DO RELATÓRIO",
    texto,
    re.DOTALL,
)
    if busca_conclusao:
        conclusao = " ".join(
        linha.strip()
        for linha in busca_conclusao.group(1).splitlines()
    if linha.strip()
    )
    # Linha da tabela
    return {
        "arquivo": arquivo_pdf.name,
        "uc": uc,
        "ordem_servico": ordem_serv,
        "dt_retirada": dt_retirada,
        "data_ensaio": data_ensaio,
        "validacao_data_ensaio": validacao_data_ensaio,
        "integridade_lacres": integridade_lacre,
        "inspecao_geral_medidor": inspecao_geral,
        "correspondencia_mod_aprovado": correspondencia_mod,
        "ensaio_marcha_vazio": ensaio_de_marcha,
        "erro_ativa_cn": erro_ativa_cn,
        "erro_ativa_ci": erro_ativa_ci,
        "erro_ativa_cp": erro_ativa_cp,
        "resultado_exatidao_ativa": resultado_exatidao_ativa,
        "analise_exatidao": analise_exatidao,
        "anomalias": anomalias,
        "conclusao": conclusao
    }

# Função para padronizar o texto: minúsculas e sem acento
def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))

# Função que verifica se alguma anomalia do laudo bate com a lista de palavras-chave
def tem_anomalia(anomalias, lista_padroes):
    for anomalia in anomalias.split(" | "):
        anomalia = normalizar(anomalia)
        if any(re.search(padrao, anomalia) for padrao in lista_padroes):
            return True
    return False

# Função que classifica UM laudo a partir da linha extraída
def classificar_laudo(laudo):

    # Definição das variáveis
    classificacao = ""
    motivo = ""

    ensaios = [
        laudo["integridade_lacres"],
        laudo["inspecao_geral_medidor"],
        laudo["correspondencia_mod_aprovado"],
        laudo["ensaio_marcha_vazio"],
    ]

    # Passo 1: os 4 ensaios aprovados -> sem indício
    if all(ensaio == "APROVADO" for ensaio in ensaios):
        classificacao = SEM_INDICIO
        motivo = "Os 4 ensaios aprovados"
        return classificacao, motivo

    # Passo 2: algum ensaio diferente de aprovado -> olha a exatidão
    exatidao = laudo["analise_exatidao"]
    if exatidao == "REPROVADO":
        motivo = f"Ensaio reprovado e erro de exatidão acima de {LIMITE_ERRO_ANALISE}%"
    elif exatidao == "APROVADO":
        motivo = "Ensaio reprovado com exatidão dentro da tolerância"
    else:
        motivo = "Ensaio reprovado e exatidão sem valores"

    # Passo 3: anomalias definem se é fraude ou defeito (fraude tem prioridade)
    if tem_anomalia(laudo["anomalias"], ANOMALIAS_FRAUDE):
        classificacao = INDICIO_FRAUDE
        motivo += "; anomalia de fraude encontrada"
    elif tem_anomalia(laudo["anomalias"], ANOMALIAS_DEFEITO):
        classificacao = INDICIO_DEFEITO
        motivo += "; anomalia de defeito encontrada"
    else:
        classificacao = ANALISE_MANUAL
        motivo += "; nenhuma anomalia reconhecida"

    return classificacao, motivo


# Percorrer todos os PDFs da pasta
laudos, erros = [], []
 
for arquivo_pdf in sorted(pasta_brutos.glob("*.pdf")):
    try:
        laudo = extrair_laudo(arquivo_pdf)
        laudo["classificacao"], laudo["motivo_classificacao"] = classificar_laudo(laudo)
        laudos.append(laudo)
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

df_laudos.to_csv(
    pasta_amostra / "laudos.csv",
    index=False,
    sep=";",
    encoding="utf-8-sig",
)


