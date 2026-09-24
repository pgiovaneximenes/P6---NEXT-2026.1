import re
import unicodedata


# ============================================================
# CONFIGURAÇÕES
# ============================================================

LIMITE_ERRO_ANALISE = 15

SEM_INDICIO = "Sem indício identificado"
INDICIO_FRAUDE = "Possível fraude/manipulação"
INDICIO_DEFEITO = "Possível defeito"
ANALISE_MANUAL = "Revisão manual"


# ============================================================
# PADRÕES DE ANOMALIAS
# ============================================================

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
    """
    Coloca o texto em minúsculas e remove acentos.

    Exemplo:
    'Tampa Forçada' -> 'tampa forcada'
    """

    if not texto:
        return ""

    texto = unicodedata.normalize("NFKD", texto.lower())

    return "".join(
        caractere
        for caractere in texto
        if not unicodedata.combining(caractere)
    )


def encontrar_anomalia(anomalias, lista_padroes):
    """
    Procura uma anomalia que corresponda a algum dos padrões.

    Retorna:
        - texto da anomalia encontrada
        - None caso nenhuma seja encontrada
    """

    if not anomalias:
        return None

    for anomalia in anomalias.split(" | "):

        anomalia_normalizada = normalizar(anomalia)

        for padrao in lista_padroes:

            if re.search(padrao, anomalia_normalizada):
                return anomalia.strip()

    return None


def maior_erro_exatidao(laudo):
    """
    Identifica o maior erro absoluto entre CN, CI e CP.

    Retorna:
        (ensaio, valor)

    Exemplo:
        ('CI', -18.5)
    """

    erros = {
        "CN": laudo.get("erro_ativa_cn"),
        "CI": laudo.get("erro_ativa_ci"),
        "CP": laudo.get("erro_ativa_cp"),
    }

    erros_validos = {
        ensaio: erro
        for ensaio, erro in erros.items()
        if erro is not None
    }

    if not erros_validos:
        return None, None

    ensaio = max(
        erros_validos,
        key=lambda x: abs(erros_validos[x])
    )

    return ensaio, erros_validos[ensaio]


# ============================================================
# ANÁLISE DA EXATIDÃO
# ============================================================

def analisar_exatidao(laudo):
    """
    Verifica os erros de exatidão ativa.

    Se qualquer erro absoluto for maior que 15%:
        -> REPROVADO

    Caso contrário:
        -> APROVADO
    """

    erros = [
        laudo.get("erro_ativa_cn"),
        laudo.get("erro_ativa_ci"),
        laudo.get("erro_ativa_cp"),
    ]

    erros_validos = [
        erro for erro in erros
        if erro is not None
    ]

    if not erros_validos:
        return None

    if any(abs(erro) > LIMITE_ERRO_ANALISE for erro in erros_validos):
        return "REPROVADO"

    return "APROVADO"


# ============================================================
# CLASSIFICAÇÃO DO LAUDO
# ============================================================

def classificar_laudo(laudo):
    """
    Classifica o laudo seguindo a ordem definida no projeto.

    Regra 1:
        Se os 4 ensaios qualitativos forem APROVADO:
            -> Sem indício identificado

    Regra 2:
        Caso contrário, analisa a exatidão.

    Regra 3:
        Procura anomalias de fraude.

    Regra 4:
        Caso não seja fraude, procura anomalias de defeito.

    Regra 5:
        Caso nenhuma anomalia conhecida seja encontrada:
            -> Revisão manual

    Retorna:
        classificacao, motivo
    """

    # --------------------------------------------------------
    # 1. ENSAIOS QUALITATIVOS
    # --------------------------------------------------------

    ensaios = [
        laudo.get("integridade_lacres"),
        laudo.get("inspecao_geral_medidor"),
        laudo.get("correspondencia_mod_aprovado"),
        laudo.get("ensaio_marcha_vazio"),
    ]

    if all(ensaio == "APROVADO" for ensaio in ensaios):

        return (
            SEM_INDICIO,
            "Os 4 ensaios qualitativos foram aprovados"
        )

    # --------------------------------------------------------
    # 2. EXATIDÃO
    # --------------------------------------------------------

    exatidao = laudo.get("analise_exatidao")

    # Caso o campo ainda não tenha sido calculado
    if exatidao is None:
        exatidao = analisar_exatidao(laudo)

    if exatidao == "REPROVADO":

        ensaio, erro = maior_erro_exatidao(laudo)

        if ensaio is not None:

            motivo_exatidao = (
                f"Ensaio reprovado e erro de exatidão acima de "
                f"{LIMITE_ERRO_ANALISE}% "
                f"(maior erro: {ensaio} = {erro:.2f}%)"
            )

        else:

            motivo_exatidao = (
                f"Ensaio reprovado e erro de exatidão acima de "
                f"{LIMITE_ERRO_ANALISE}%"
            )

    elif exatidao == "APROVADO":

        motivo_exatidao = (
            "Ensaio reprovado com exatidão dentro da tolerância"
        )

    else:

        motivo_exatidao = (
            "Ensaio reprovado e exatidão sem valores"
        )

    # --------------------------------------------------------
    # 3. ANOMALIA DE FRAUDE
    # --------------------------------------------------------

    anomalia_fraude = encontrar_anomalia(
        laudo.get("anomalias", ""),
        ANOMALIAS_FRAUDE
    )

    if anomalia_fraude:

        motivo = (
            f"{motivo_exatidao}; "
            f"anomalia de fraude encontrada: "
            f"{anomalia_fraude}"
        )

        return INDICIO_FRAUDE, motivo

    # --------------------------------------------------------
    # 4. ANOMALIA DE DEFEITO
    # --------------------------------------------------------

    anomalia_defeito = encontrar_anomalia(
        laudo.get("anomalias", ""),
        ANOMALIAS_DEFEITO
    )

    if anomalia_defeito:

        motivo = (
            f"{motivo_exatidao}; "
            f"anomalia de defeito encontrada: "
            f"{anomalia_defeito}"
        )

        return INDICIO_DEFEITO, motivo

    # --------------------------------------------------------
    # 5. NENHUMA ANOMALIA RECONHECIDA
    # --------------------------------------------------------

    motivo = (
        f"{motivo_exatidao}; "
        "nenhuma anomalia reconhecida"
    )

    return ANALISE_MANUAL, motivo


# ============================================================
# PRIORIDADE
# ============================================================

def calcular_prioridade(laudo):
    """
    Identifica o maior erro absoluto de exatidão.

    Esta função NÃO altera a classificação.

    Ela pode ser utilizada posteriormente para
    ordenar os casos de possível fraude.
    """

    classificacao = laudo.get("classificacao")

    if classificacao != INDICIO_FRAUDE:
        return None

    ensaio, erro = maior_erro_exatidao(laudo)

    if erro is None:
        return None

    return abs(erro)


# ============================================================
# TESTE MANUAL
# ============================================================

if __name__ == "__main__":

    laudo_teste = {
        "integridade_lacres": "REPROVADO",
        "inspecao_geral_medidor": "APROVADO",
        "correspondencia_mod_aprovado": "APROVADO",
        "ensaio_marcha_vazio": "APROVADO",

        "erro_ativa_cn": 2.5,
        "erro_ativa_ci": -18.7,
        "erro_ativa_cp": 4.2,

        "analise_exatidao": "REPROVADO",

        "anomalias": "Tampa forçada",
    }

    classificacao, motivo = classificar_laudo(laudo_teste)

    laudo_teste["classificacao"] = classificacao

    print("Classificação:", classificacao)
    print("Motivo:", motivo)
    print(
        "Prioridade:",
        calcular_prioridade(laudo_teste)
    )