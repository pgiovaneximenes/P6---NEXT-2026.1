import pandas as pd
from pypdf import PdfReader
from pathlib import Path
import re
import os
import hashlib
import unicodedata
from datetime import datetime
import psycopg
from analise import (
    calcular_prioridade,
    classificar_laudo,
    LIMITE_ERRO_ANALISE
)

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

            hash_arquivo TEXT NOT NULL UNIQUE,
            ordem_servico TEXT UNIQUE,
            status_os TEXT,

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
            prioridade REAL,
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

# Função para calcular o hash (SHA-256) do conteúdo do PDF.
# O mesmo arquivo gera sempre o mesmo hash, mesmo se renomeado.
def calcular_hash(arquivo_pdf):

    return hashlib.sha256(
        arquivo_pdf.read_bytes()
    ).hexdigest()

# Função para verificar se o arquivo (hash) já consta no banco
def laudo_existe(conexao, hash_arquivo):

    cursor = conexao.cursor()

    cursor.execute(
        """
        SELECT 1
        FROM laudos
        WHERE hash_arquivo = %s
        """,
        (hash_arquivo,)
    )

    resultado = cursor.fetchone()

    cursor.close()

    return resultado is not None

# Função para inserir o laudo no banco
def inserir_laudo(conexao, laudo):

    cursor = conexao.cursor()

    cursor.execute("""
        INSERT INTO laudos (
            hash_arquivo,
            ordem_servico,
            status_os,
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
            prioridade,
            motivo_classificacao,
            data_ingestao
        )
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s,
            %s, %s, %s
        )
    """, (
        laudo["hash_arquivo"],
        laudo["ordem_servico"],
        laudo["status_os"],
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
        laudo["prioridade"],
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

        linha_limpa = linha.strip()

        if (
            linha_limpa == rotulo
            or linha_limpa.endswith(" " + rotulo)
        ):

            if i + 1 < len(linhas):
                return linhas[i + 1].strip()

        # Corrige casos em que o PDF junta o primeiro
        # caractere do valor ao rótulo.
        #
        # Exemplo:
        # UC1
        # 23
        #
        # Resultado:
        # 123
        busca = re.search(
            r"(?:^|\s)" + re.escape(rotulo) + r"([A-Za-z0-9])$",
            linha_limpa
        )

        if busca:

            parte_valor = busca.group(1)

            if i + 1 < len(linhas):

                proxima_linha = linhas[i + 1].strip()

                if proxima_linha:
                    return parte_valor + proxima_linha

    return ""

# Função para validar se o valor lido parece uma UC.
# Aceita só letras e números, sem espaços, e recusa
# rótulos do próprio laudo que às vezes vêm na linha seguinte.
ROTULOS_LAUDO = {"UC", "UF", "CLIENTE", "ORDEM"}

def uc_valida(valor):

    return (
        bool(re.fullmatch(r"[A-Za-z0-9]+", valor))
        and valor.upper() not in ROTULOS_LAUDO
    )


# Função para validar se o valor lido parece uma OS.
# Evita capturar rótulos vizinhos (ex.: "UF", "ORDEM")
# quando o campo da OS está vazio no PDF.
TAMANHO_MINIMO_OS = 6

def os_valida(valor):

    return (
        bool(re.fullmatch(r"[A-Za-z0-9]+", valor))
        and any(caractere.isdigit() for caractere in valor)
        and len(valor) >= TAMANHO_MINIMO_OS
    )
def extrair_ordem_servico(linhas):

    for i, linha in enumerate(linhas):

        linha_limpa = linha.strip()

        # Caso normal:
        # Ordem de Serviço
        # 44660011
        if linha_limpa == "Ordem de Serviço":

            if i + 1 < len(linhas):

                proxima_linha = linhas[i + 1].strip()

                if os_valida(proxima_linha):
                    return proxima_linha

        # Caso em que o PDF junta o primeiro dígito
        # com o texto:
        #
        # Ordem de Serviço4
        # 4660011
        #
        # Resultado:
        # 44660011
        busca = re.search(
            r"Ordem\s+de\s+Serviço([A-Za-z0-9]+)",
            linha_limpa,
            re.IGNORECASE
        )

        if busca:

            parte_os = busca.group(1)

            if i + 1 < len(linhas):

                proxima_linha = re.sub(
                    r"[^A-Za-z0-9]",
                    "",
                    linhas[i + 1].strip()
                )

                if (
                    len(parte_os) == 1
                    and os_valida(parte_os + proxima_linha)
                ):
                    return parte_os + proxima_linha

            if os_valida(parte_os):
                return parte_os

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
        re.escape(rotulo) +
        r"\s*(REPROVADO|APROVADO|NÃO REALIZADO(?:\s*\(VER ANOMALIA\(S\)\))?)",
        texto
    )

    return busca.group(1) if busca else None



# Função que lê UM PDF e devolve uma linha da tabela
def extrair_laudo(arquivo_pdf):

    # Definição das variáveis
    uc = ""
    ordem_serv = ""
    dt_retirada = ""
    data_ensaio = ""
    integridade_lacre = None
    inspecao_geral = None
    correspondencia_mod = None
    ensaio_de_marcha = None
    erro_ativa_cn = None
    erro_ativa_ci = None
    erro_ativa_cp = None
    resultado_exatidao_ativa = None
    analise_exatidao = None
    anomalias = ""
    conclusao = ""

    # Leitura do PDF
    texto = ler_texto(arquivo_pdf)

    if not texto.strip():
        raise ValueError("PDF sem texto (pode ser escaneado)")

    linhas = texto.splitlines()

    # Dados do cliente
    uc = linha_seguinte(linhas, "UC") 
    if not uc_valida(uc):                # Descarta valores que não parecem uma UC  (rótulos vizinhos, endereços, textos com espaço)
        uc = ""


    # Ordem de Serviço
    ordem_serv = extrair_ordem_servico(linhas)

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
        r"(-?\d+,\d+)\s*"
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

    # Se não houver valores numéricos de exatidão,
    # verifica se o resultado foi NÃO REALIZADO.
    if resultado_exatidao_ativa is None:

        busca_exatidao_nao_realizada = re.search(
            r"Ensaio de Exatidão - Energia Ativa.*?"
            r"NÃO REALIZADO(?:\s*\(VER ANOMALIA\(S\)\))?",
            texto,
            re.DOTALL
        )

        if busca_exatidao_nao_realizada:

            resultado_exatidao_ativa = re.search(
                r"NÃO REALIZADO(?:\s*\(VER ANOMALIA\(S\)\))?",
                busca_exatidao_nao_realizada.group(0)
            ).group(0)

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

        if itens:
            anomalias = " | ".join(itens)
        else:
            anomalias = "Sem anomalias registradas"

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
        "uc": uc or None,
        "ordem_servico": ordem_serv or None,
        "status_os": "OK" if ordem_serv else "OS AUSENTE",
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
sem_os = 0
 
# Percorre todos os PDFs da pasta brutos
for arquivo_pdf in sorted(
    pasta_brutos.glob("*.pdf")
):
 
    try:
 
        # 1. Verifica pelo hash se o arquivo já foi processado
        # (feito antes da extração para não ler o PDF à toa)
        hash_arquivo = calcular_hash(arquivo_pdf)
 
        if laudo_existe(conexao, hash_arquivo):
 
            print(
                f"IGNORADO - Arquivo já processado: "
                f"{arquivo_pdf.name}"
            )
 
            ignorados += 1
 
            continue
 
        # 2. Extrai os dados do PDF
        laudo = extrair_laudo(arquivo_pdf)
        laudo["hash_arquivo"] = hash_arquivo
 
        # 3. Verifica se a mesma OS já existe em outro arquivo
        # (possível reemissão do laudo)
        if (
            laudo["ordem_servico"]
            and ordem_servico_existe(conexao, laudo["ordem_servico"])
        ):
 
            erros.append({
                "arquivo": arquivo_pdf.name,
                "erro": (
                    f"OS {laudo['ordem_servico']} já existe em "
                    f"outro arquivo (possível reemissão)"
                )
            })
 
            continue
 
        # 4. Classifica o laudo
        (
            laudo["classificacao"],
            laudo["motivo_classificacao"]
        ) = classificar_laudo(laudo)
 
        # 5. Calcula a prioridade
        laudo["prioridade"] = calcular_prioridade(laudo)
 
        # 6. Insere o novo laudo
        inserir_laudo(
            conexao,
            laudo
        )
 
        print(
            f"INSERIDO - {arquivo_pdf.name} | "
            f"OS: {laudo['ordem_servico'] or 'NÃO INFORMADA'}"
        )
 
        novos += 1
 
        if laudo["status_os"] == "OS AUSENTE":
            sem_os += 1
 
        laudos.append(laudo)
 
    except Exception as e:
 
        erros.append({
            "arquivo": arquivo_pdf.name,
            "erro": str(e)
        })
 
 
# Confirma as alterações
conexao.commit()
 
# Mostrar resultado da execução
 
df_laudos = pd.DataFrame(laudos)
df_erros = pd.DataFrame(erros)
 
# Mostrar novos registros
if not df_laudos.empty:
 
    print("\nLaudos novos:")
    print(
        df_laudos.drop(columns=["hash_arquivo"]).to_string(index=False)
    )
 
# Mostrar erros
if not df_erros.empty:
 
    print("\nPDFs com erro ou pendência:")
    print(
        df_erros.to_string(index=False)
    )
 
# Resumo da ingestão
print("\nResumo da ingestão:")
print(f"Novos registros: {novos}")
print(f"  - sem Ordem de Serviço: {sem_os}")
print(f"Já existentes: {ignorados}")
print(f"Erros: {len(erros)}")
 
 
# Salvar a tabela completa do banco em CSV dentro de dados/amostra
# (exporta do banco, e não só os laudos novos desta execução,
# para o CSV não ser sobrescrito vazio quando não há novidades)
 
pasta_amostra = pasta_dados / "amostra"
pasta_amostra.mkdir(exist_ok=True)
 
with conexao.cursor() as cursor:
 
    cursor.execute("SELECT * FROM laudos ORDER BY id")
 
    colunas = [coluna.name for coluna in cursor.description]
 
    df_banco = pd.DataFrame(
        cursor.fetchall(),
        columns=colunas
    )
 
# Fecha a conexão
conexao.close()
 
df_banco.to_csv(
    pasta_amostra / "laudos.csv",
    index=False,
    sep=",",
    encoding="utf-8-sig",
)