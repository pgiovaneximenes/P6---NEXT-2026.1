# P6 — Triagem de Laudos

Pipeline em Python que lê laudos de aferição de medidores de energia elétrica em PDF, extrai os resultados dos ensaios, classifica cada laudo como **indício de fraude**, **indício de defeito**, **sem indício** ou **revisão manual** e grava tudo em um banco PostgreSQL. A partir do banco, é gerada a fila priorizada para análise.

Projeto do módulo M6 — Experiência Prática do programa **NExT Carreira em Dados 2026.1 (CESAR School)**.

---

## Contexto

A área demandante recebe laudos de laboratório sobre medidores retirados de campo. Hoje a triagem é manual: alguém abre cada PDF, lê os ensaios e decide se o caso indica fraude, defeito ou nada. O objetivo do projeto é transformar essa leitura em uma **regra escrita e reproduzível**, aplicada automaticamente, para que o analista comece pelos casos de maior impacto.

## Entregas

| Entrega | Onde está |
|---|---|
| Regra de classificação escrita | Seção [Regra de classificação](#regra-de-classificação) e função `classificar_laudo()` em `extracao.py` |
| Pipeline com validação na entrada | `extracao.py` |


---

## Como funciona

```
dados/brutos/*.pdf
      │
      ▼
1. Leitura do PDF (pypdf)
      │
      ▼
2. Extração dos campos (UC, OS, datas, ensaios, erros de exatidão, anomalias, conclusão)
      │
      ▼
3. Validação (data do ensaio, PDF sem texto, OS já existente)
      │
      ▼
4. Classificação (regra abaixo)
      │
      ▼
5. Gravação no PostgreSQL (tabela laudos)  ──►  6. Exportação para dados/amostra/laudos.csv
```

A cada execução o script lê todos os PDFs da pasta `dados/brutos`. Um laudo só é inserido se a **Ordem de Serviço** ainda não existir no banco. Os já existentes são ignorados e contados no resumo.

---

## Regra de classificação

A regra é aplicada a cada laudo, nesta ordem:

**Passo 1: ensaios qualitativos.** Se os 4 ensaios abaixo estiverem **APROVADOS**, o laudo é classificado como **Sem indício identificado** e a análise termina.

- Integridade dos Lacres
- Inspeção Geral do Medidor
- Correspondência com o Modelo Aprovado
- Ensaio de Marcha em Vazio

**Passo 2: exatidão.** Se algum ensaio foi reprovado, o script verifica os erros de energia ativa (carga nominal, indutiva e pequena). Se qualquer erro, em módulo, passar de **15%**, a exatidão é considerada reprovada. Essa informação entra no motivo da classificação.
**Passo 3: anomalias descritas no laudo.** O texto da seção "Anomalia(s) Encontrada(s)" é comparado com listas de palavras-chave:

| Classificação | Padrões procurados (sem acento, minúsculas) |
|---|---|
| Possível fraude/manipulação | tampa forçada, tampa aberta, by-pass, "não registra corretamente o consumo" |
| Possível defeito | display apagado, dispositivo de saída apagado |
| Revisão manual | nenhum padrão reconhecido |

Os padrões de fraude são testados antes dos de defeito. A coluna `motivo_classificacao` registra o caminho percorrido, para que cada decisão possa ser auditada.


---

## Estrutura do repositório


```
P6---NEXT-2026.1/
├── extracao.py              # pipeline: leitura, extração, classificação e carga no banco
├── requirements.txt         # dependências Python
├── dados/
│   ├── brutos/              # PDFs dos laudos (entrada)
│   └── amostra/
│       └── laudos.csv       # exportação da tabela laudos

```

---

## Pré-requisitos

- Python 3.12.10
- PostgreSQL instalado e em execução (porta padrão 5432)
- DBeaver (opcional, para visualizar o banco)

## Instalação

```powershell
# 1. Clonar o repositório
git clone https://github.com/pgiovaneximenes/P6---NEXT-2026.1.git
cd P6---NEXT-2026.1

# 2. Criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Instalar as dependências
pip install -r requirements.txt
```

### Configurar o banco

1. Crie o database **uma única vez**. O script cria a tabela, mas não cria o database. No DBeaver ou no psql:

   ```sql
   CREATE DATABASE triagem_laudos;
   ```

2. No início do `extracao.py`, ajuste as credenciais para as do **seu** PostgreSQL:

   ```python
   HOST = "localhost"
   PORTA = 5432
   BANCO = "triagem_laudos"
   USUARIO = "postgres"
   SENHA = "sua_senha"
   ```

   Não faça commit do arquivo com a sua senha real.

## Execução

Coloque os PDFs em `dados/brutos/` e rode:

```powershell
python extracao.py
```

Ao final, o terminal mostra o resumo:

```
Resumo da ingestão:
Novos registros: 8
Já existentes: 0
Erros: 0
```

PDFs que não puderam ser lidos (por exemplo, escaneados, sem texto) aparecem na lista de erros e não interrompem o processamento dos demais.

## Visualizar no DBeaver

1. **Nova conexão → PostgreSQL**, com host `localhost`, porta `5432`, e o mesmo usuário e senha configurados no `extracao.py`.
2. Navegue até `triagem_laudos → Esquemas → public → Tabelas → laudos`. Se a tabela não aparecer, aperte **F5**.
3. Exemplo de consulta:

   ```sql
   SELECT ordem_servico, classificacao, motivo_classificacao,
          erro_ativa_cn, erro_ativa_ci, erro_ativa_cp
   FROM laudos
   ORDER BY classificacao;
   ```

---

## Dicionário de dados: tabela `laudos`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL | Chave primária |
| `ordem_servico` | TEXT (único) | Ordem de serviço do laudo; usada para evitar duplicidade |
| `arquivo` | TEXT | Nome do PDF de origem |
| `uc` | TEXT | Unidade consumidora |
| `dt_retirada` | TEXT | Data de retirada do medidor |
| `data_ensaio` | TEXT | Data do ensaio em laboratório |
| `validacao_data_ensaio` | TEXT | `OK`, `NÃO ENCONTRADA`, `FORMATO INVÁLIDO` ou `DATA INVÁLIDA` |
| `integridade_lacres` | TEXT | APROVADO / REPROVADO |
| `inspecao_geral_medidor` | TEXT | APROVADO / REPROVADO |
| `correspondencia_mod_aprovado` | TEXT | APROVADO / REPROVADO |
| `ensaio_marcha_vazio` | TEXT | APROVADO / REPROVADO |
| `erro_ativa_cn` | REAL | Erro (%) de energia ativa em carga nominal |
| `erro_ativa_ci` | REAL | Erro (%) de energia ativa em carga indutiva |
| `erro_ativa_cp` | REAL | Erro (%) de energia ativa em carga pequena |
| `resultado_exatidao_ativa` | TEXT | Resultado de exatidão informado no laudo |
| `analise_exatidao` | TEXT | Resultado recalculado pelo limite do projeto (15%) |
| `anomalias` | TEXT | Anomalias descritas, separadas por ` \| ` |
| `conclusao` | TEXT | Texto de conclusão/observações do laudo |
| `classificacao` | TEXT | Resultado da regra |
| `motivo_classificacao` | TEXT | Justificativa da classificação |
| `data_ingestao` | TEXT | Data e hora em que o registro entrou no banco |
---

## Limitações conhecidas e próximos passos

- **Base fictícia:** os laudos atuais são simulados. A regra precisa ser recalibrada com a amostra real de 12 meses.
- **Registros existentes não são atualizados:** se a regra mudar, os laudos já gravados mantêm a classificação antiga. Para reclassificar, limpe a tabela (`TRUNCATE laudos;`) e rode o script novamente.
- **Ordem de serviço em branco:** ainda não é rejeitada na validação de entrada.
- **Datas armazenadas como texto:** a conversão para `DATE`/`TIMESTAMP` facilitaria filtros por período.
- **PDFs escaneados:** não são suportados (não há OCR).
## Dados e privacidade

Laudos reais contêm dados de unidades consumidoras. **Não versione PDFs reais nem o CSV gerado a partir deles.** Quando a amostra real chegar, inclua `dados/brutos/` e `dados/amostra/` no `.gitignore`.

---

## Equipe


| Nome | GitHub |
|---|---|
| Paulo Giovane Ximenes  | [@pgiovaneximenes](https://github.com/pgiovaneximenes) |
| Marcelo  | [@marcel0g](https://github.com/marcel0g) |
| Rodrigo Amorim  | [@rodrigoamorim182](https://github.com/rodrigoamorim182) |
| Maria Alice Gadelha | [@mariaalicegadelha](https://github.com/mariaalicegadelha) |
| Paulo Neves | [@pneves953](https://github.com/pneves953) |
| Luiza Delgado | [@delgadoluiza](https://github.com/delgadoluiza) |
| Amanda Conceição | [@amanda87eng-ship-it](https://github.com/amanda87eng-ship-it) |
| Maria Clara | [@mclarabritocarvalho-ship-it](https://github.com/mclarabritocarvalho-ship-it) |
| Carol Martir| [@acarolmartir-dotcom](https://github.com/acarolmartir-dotcom) |


|  |  |

Mentor: Ricardo Teixeira
