import pandas as pd
from pypdf import PdfReader
from pathlib import Path
import re
import unicodedata
from datetime import datetime
import psycopg
from analise import classificar_laudo

#Definição de pastas utilizadas pelo script
pasta_script = Path(__file__).resolve().parent
pasta_dados = pasta_script / "dados"
pasta_brutos = pasta_dados / "brutos"

# Configuração do PostgreSQL
HOST = "localhost"
PORTA = 5432
BANCO = "triagem_laudos"
USUARIO = "postgres"
SENHA = "123"

# Função para conectar ao banco PostgreSQL
def conectar_banco():

    conexao = psycopg.connect(
        host=HOST,
        port=PORTA,
        dbname=BANCO,
        user=USUARIO,
        password=SENHA
    )

    return conexao

# Função para criar a tabela do banco de dados
def criar_banco(conexao):

    cursor = conexao.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS laudos (
            id SERIAL PRIMARY KEY,

            ordem_servico TEXT NOT NULL UNIQUE,

            arquivo TEXT NOT NULL,
            uc TEXT,
            dt_retirada TEXT,
            data_ensaio TEXT,
            validacao_data_ensaio TEXT,

            integridade_lacres TEXT,
            inspecao_geral_medidor TEXT,
            correspondencia_mod_aprovado TEXT,
            ensaio_marcha_vazio TEXT,

            erro_ativa_cn REAL,
            erro_ativa_ci REAL,
            erro_ativa_cp REAL,

            resultado_exatidao_ativa TEXT,
            analise_exatidao TEXT,

            anomalias TEXT,
            conclusao TEXT,

            classificacao TEXT,
            motivo_classificacao TEXT,

            data_ingestao TEXT
        )
    """)

    conexao.commit()
    cursor.close()

# Função para verificar se a ordem de serviço consta no banco
def ordem_servico_existe(conexao, ordem_servico):

    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM laudos
        WHERE ordem_servico = %s
        """,
        (ordem_servico,)
    )

    resultado = cursor.fetchone()

    cursor.close()

    return resultado is not None

# Função para inserir o laudo no banco
def inserir_laudo(conexao, laudo):

    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO laudos (
            ordem_servico,
            arquivo,
            uc,
            dt_retirada,
            data_ensaio,
            validacao_data_ensaio,
            integridade_lacres,
            inspecao_geral_medidor,
            correspondencia_mod_aprovado,
            ensaio_marcha_vazio,
            erro_ativa_cn,
            erro_ativa_ci,
            erro_ativa_cp,
            resultado_exatidao_ativa,
            analise_exatidao,
            anomalias,
            conclusao,
            classificacao,
            motivo_classificacao,
            data_ingestao
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s
        )
    """, (
        laudo["ordem_servico"],
        laudo["arquivo"],
        laudo["uc"],
        laudo["dt_retirada"],
        laudo["data_ensaio"],
        laudo["validacao_data_ensaio"],
        laudo["integridade_lacres"],
        laudo["inspecao_geral_medidor"],
        laudo["correspondencia_mod_aprovado"],
        laudo["ensaio_marcha_vazio"],
        laudo["erro_ativa_cn"],
        laudo["erro_ativa_ci"],
        laudo["erro_ativa_cp"],
        laudo["resultado_exatidao_ativa"],
        laudo["analise_exatidao"],
        laudo["anomalias"],
        laudo["conclusao"],
        laudo["classificacao"],
        laudo["motivo_classificacao"],
        datetime.now().isoformat()
    ))

    cursor.close()

# Função para ler o texto completo de um PDF
def ler_texto(arquivo_pdf):
    try:
        leitor = PdfReader(arquivo_pdf)

        texto = []

        for pagina in leitor.pages:
            conteudo = pagina.extract_text()
            if conteudo:
                texto.append(conteudo)
        texto_final = "\n".join(texto)

        if not texto_final.strip():
            raise ValueError("PDF sem texto (pode ser escaneado)")

        return texto_final
    except Exception as e:
        raise ValueError(f"Erro ao ler o PDF: {e}")

# Função para pegar o valor da linha seguinte ao rótulo
def linha_seguinte(linhas, rotulo):

    for i, linha in enumerate(linhas):

        if (
            linha.strip() == rotulo
            or linha.strip().endswith(" " + rotulo)
        ):

            if i + 1 < len(linhas):
                return linhas[i + 1].strip()

    return ""

# Função para extrair e validar a data
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


# Função para pegar o resultado logo depois do rótulo
def pegar_resultado(texto, rotulo):

    busca = re.search(
        re.escape(rotulo) + r"\s*(REPROVADO|APROVADO)",
        texto
    )

    return busca.group(1) if busca else ""


# Limite provisório para análise exploratória.
# Deve ser validado com a área demandante.
LIMITE_ERRO_ANALISE = 15


# Função que lê UM PDF e devolve uma linha da tabela
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

    ordem_serv = linha_seguinte(
        linhas,
        "Ordem de Serviço"
    ).strip()

    dt_retirada = linha_seguinte(
        linhas,
        "Dt. Retirada"
    )

    # Data do Ensaio
    data_ensaio, validacao_data_ensaio = extrair_data(
        texto,
        "Data do Ensaio"
    )

    # Ensaio de Exatidão - Energia Ativa
    padrao = (
        r"(-?\d+,\d+)\s+"
        r"(-?\d+,\d+)\s+"
        r"(-?\d+,\d+)\s+"
        r"(REPROVADO|APROVADO)"
    )

    busca = re.search(padrao, texto)

    if busca:

        (
            erro_ativa_cn,
            erro_ativa_ci,
            erro_ativa_cp,
            resultado_exatidao_ativa
        ) = busca.groups()

        valores_erro = [
            float(valor.replace(",", "."))
            for valor in (
                erro_ativa_cn,
                erro_ativa_ci,
                erro_ativa_cp
            )
        ]

        if any(
            abs(valor) > LIMITE_ERRO_ANALISE
            for valor in valores_erro
        ):

            analise_exatidao = "REPROVADO"

        else:

            analise_exatidao = "APROVADO"

    # Resultados dos ensaios
    integridade_lacre = pegar_resultado(
        texto,
        "Integridade dos Lacres"
    )

    inspecao_geral = pegar_resultado(
        texto,
        "Inspeção Geral Medidor"
    )

    correspondencia_mod = pegar_resultado(
        texto,
        "Correspondencia Mod.Aprovado"
    )

    ensaio_de_marcha = pegar_resultado(
        texto,
        "Ensaio de Marcha em Vazio"
    )

    # Anomalias
    busca_anomalias = re.search(
        r"6\. Anomalia\(s\) Encontrada\(s\) - Descrição:\s*"
        r"(.*?)\s*7\. Evidências",
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

    # Conclusão
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

    # Retorna uma linha da tabela
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
        "erro_ativa_cn": float(erro_ativa_cn.replace(",", ".")) if erro_ativa_cn else None,
        "erro_ativa_ci": float(erro_ativa_ci.replace(",", ".")) if erro_ativa_ci else None,
        "erro_ativa_cp": float(erro_ativa_cp.replace(",", ".")) if erro_ativa_cp else None,
        "resultado_exatidao_ativa": resultado_exatidao_ativa,
        "analise_exatidao": analise_exatidao,
        "anomalias": anomalias,
        "conclusao": conclusao
    }

# INGESTÃO DOS PDFS

conexao = conectar_banco()

# Cria a tabela caso ainda não exista
criar_banco(conexao)

laudos = []
erros = []

novos = 0
ignorados = 0

# Percorre todos os PDFs da pasta brutos
for arquivo_pdf in sorted(
    pasta_brutos.glob("*.pdf")
):

    try:

        # 1. Extrai os dados do PDF
        laudo = extrair_laudo(arquivo_pdf)

        # 2. Classifica o laudo
        (
            laudo["classificacao"],
            laudo["motivo_classificacao"]
        ) = classificar_laudo(laudo)

        # 3. Verifica se a Ordem de Serviço já existe
        if ordem_servico_existe(
            conexao,
            laudo["ordem_servico"]
        ):

            print(
                f"IGNORADO - Ordem de Serviço já existe: "
                f"{laudo['ordem_servico']}"
            )

            ignorados += 1

            continue

        # 4. Insere o novo laudo
        inserir_laudo(
            conexao,
            laudo
        )

        print(
            f"INSERIDO - Ordem de Serviço: "
            f"{laudo['ordem_servico']}"
        )

        novos += 1

        laudos.append(laudo)

    except Exception as e:

        erros.append({
            "arquivo": arquivo_pdf.name,
            "erro": str(e)
        })


# Confirma as alterações
conexao.commit()

# Fecha a conexão
conexao.close()

# Mostrar resultado da execução

df_laudos = pd.DataFrame(laudos)
df_erros = pd.DataFrame(erros)

# Mostrar novos registros
if not df_laudos.empty:

    print("\nLaudos novos:")
    print(
        df_laudos.to_string(index=False)
    )

# Mostrar erros
if not df_erros.empty:

    print("\nPDFs com erro na leitura:")
    print(
        df_erros.to_string(index=False)
    )

# Resumo da ingestão
print("\nResumo da ingestão:")
print(f"Novos registros: {novos}")
print(f"Já existentes: {ignorados}")
print(f"Erros: {len(erros)}")


# Salvar a tabela em CSV dentro de dados/amostra

pasta_amostra = pasta_dados / "amostra"
pasta_amostra.mkdir(exist_ok=True)


df_laudos.to_csv(
    pasta_amostra / "laudos.csv",
    index=False,
    sep=";",
    encoding="utf-8-sig",
)