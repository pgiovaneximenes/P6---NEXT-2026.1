import re
import unicodedata
import pandas as pd
import psycopg


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_ERRO_ANALISE = 15

SEM_INDICIO = "Sem indício identificado"
INDICIO_FRAUDE = "Possível fraude/manipulação"
INDICIO_DEFEITO = "Possível defeito"
ANALISE_MANUAL = "Revisão manual"


ANOMALIAS_FRAUDE = [
    r"tampa.*forcad",
    r"tampa.*abert",
    r"by.?pass",
    r"nao registra corretamente o consumo",
]

ANOMALIAS_DEFEITO = [
    r"display.*apagad",
    r"dispositivo de saida.*apagad",
]


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================

def normalizar(texto):

    if not texto:
        return ""

    texto = unicodedata.normalize(
        "NFKD",
        str(texto).lower()
    )

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def encontrar_anomalia(anomalias, lista_padroes):

    if anomalias is None or pd.isna(anomalias):
        return None

    for anomalia in str(anomalias).split(" | "):

        texto = normalizar(anomalia)

        for padrao in lista_padroes:
            if re.search(padrao, texto):
                return anomalia.strip()

    return None


def maior_erro_exatidao(laudo):

    erros = {
        "CN": laudo.get("erro_ativa_cn"),
        "CI": laudo.get("erro_ativa_ci"),
        "CP": laudo.get("erro_ativa_cp"),
    }

    erros_validos = {
        ensaio: float(erro)
        for ensaio, erro in erros.items()
        if erro is not None and not pd.isna(erro)
    }

    if not erros_validos:
        return None, None

    ensaio = max(
        erros_validos,
        key=lambda x: abs(erros_validos[x])
    )

    return ensaio, erros_validos[ensaio]

def status_aprovado(valor):

    if valor is None or pd.isna(valor):
        return False

    return normalizar(valor).strip() == "aprovado"

# ============================================================
# EXATIDÃO
# ============================================================

def analisar_exatidao(laudo):

    erros = [
        laudo.get("erro_ativa_cn"),
        laudo.get("erro_ativa_ci"),
        laudo.get("erro_ativa_cp"),
    ]

    erros_validos = [
        float(erro)
        for erro in erros
        if erro is not None and not pd.isna(erro)
    ]

    if not erros_validos:
        return None

    if any(
        abs(erro) >= LIMITE_ERRO_ANALISE
        for erro in erros_validos
    ):
        return "REPROVADO"

    return "APROVADO"


# ============================================================
# CLASSIFICAÇÃO
# ============================================================

def classificar_laudo(laudo):

    ensaios = [
        laudo.get("integridade_lacres"),
        laudo.get("inspecao_geral_medidor"),
        laudo.get("correspondencia_mod_aprovado"),
        laudo.get("ensaio_marcha_vazio"),
    ]

    qualitativos_aprovados = all(
        status_aprovado(ensaio)
        for ensaio in ensaios
    )

    # ========================================================
    # EXATIDÃO
    # ========================================================

    exatidao = laudo.get(
        "analise_exatidao"
    )

    if exatidao is None:
        exatidao = analisar_exatidao(
            laudo
        )

    if exatidao == "REPROVADO":

        ensaio, erro = maior_erro_exatidao(
            laudo
        )

        if ensaio:

            motivo_exatidao = (
                f"Erro acima de "
                f"{LIMITE_ERRO_ANALISE}% "
                f"({ensaio} = {erro:.2f}%)"
            )

        else:

            motivo_exatidao = (
                "Erro acima do limite"
            )

    elif exatidao == "APROVADO":

        motivo_exatidao = (
            "Exatidão dentro da tolerância"
        )

    else:

        motivo_exatidao = (
            "Exatidão sem valores"
        )

    # ========================================================
    # ANOMALIAS
    # ========================================================

    anomalia_fraude = encontrar_anomalia(
        laudo.get("anomalias", ""),
        ANOMALIAS_FRAUDE,
    )

    if anomalia_fraude:

        return (
            INDICIO_FRAUDE,
            f"{motivo_exatidao}; "
            f"{anomalia_fraude}"
        )

    anomalia_defeito = encontrar_anomalia(
        laudo.get("anomalias", ""),
        ANOMALIAS_DEFEITO,
    )

    if anomalia_defeito:

        return (
            INDICIO_DEFEITO,
            f"{motivo_exatidao}; "
            f"{anomalia_defeito}"
        )

    # ========================================================
    # SEM INDÍCIO
    # ========================================================

    if qualitativos_aprovados and exatidao == "APROVADO":

        return (
            SEM_INDICIO,
            "Os 4 ensaios qualitativos foram aprovados; "
            "exatidão dentro da tolerância"
        )

    # ========================================================
    # REVISÃO MANUAL
    # ========================================================

    if qualitativos_aprovados:

        return (
            ANALISE_MANUAL,
            f"{motivo_exatidao}; "
            "nenhuma anomalia reconhecida"
        )

    return (
        ANALISE_MANUAL,
        f"{motivo_exatidao}; "
        "um ou mais ensaios qualitativos não foram aprovados"
    )

# ============================================================
# PRIORIDADE
# ============================================================

def calcular_prioridade(laudo):

    classificacao = laudo.get(
        "classificacao"
    )

    peso = {
        INDICIO_FRAUDE: 300,
        INDICIO_DEFEITO: 200,
        ANALISE_MANUAL: 100,
        SEM_INDICIO: 0
    }

    prioridade = peso.get(
        classificacao,
        0
    )

    _, erro = maior_erro_exatidao(
        laudo
    )

    if erro is not None:
        prioridade += abs(erro)

    return round(prioridade, 2)


# ============================================================
# LEITURA DO BANCO
# ============================================================

def carregar_laudos():

    conexao = psycopg.connect(
        host="localhost",
        port=5432,
        dbname="triagem_laudos",
        user="postgres",
        password="123"
    )

    df = pd.read_sql_query(
        "SELECT * FROM laudos",
        conexao
    )

    conexao.close()

    return df
