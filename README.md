# P6 — Triagem de Laudos

Pipeline em Python que lê laudos de aferição de medidores de energia elétrica em PDF, extrai os resultados dos ensaios, classifica cada laudo em **possível fraude/manipulação**, **possível defeito**, **sem indício identificado** ou **revisão manual**, calcula uma prioridade e grava tudo em um banco PostgreSQL. A partir do banco, é gerada a fila priorizada para análise.

Projeto do módulo M6 — Experiência Prática do programa **NExT Carreira em Dados 2026.1 (CESAR School)**.

---

## Contexto

A área demandante recebe laudos de laboratório sobre medidores retirados de campo. Hoje a triagem é manual: alguém abre cada PDF, lê os ensaios e decide se o caso indica fraude, defeito ou nada. O objetivo do projeto é transformar essa leitura em uma **regra escrita e reproduzível**, aplicada automaticamente, para que o analista comece pelos casos de maior impacto.

## Problema e dados

A triagem dos laudos de aferição de medidores é realizada manualmente, envolvendo a leitura dos resultados dos ensaios, identificação de anomalias e classificação dos casos. O projeto busca automatizar parte dessa análise a partir dos laudos em PDF, apoiando a classificação e a priorização dos casos para análise.

Os dados de entrada são laudos de aferição em PDF, contendo informações de identificação, resultados dos ensaios, erros de energia ativa, anomalias e conclusão do laboratório.

A documentação detalhada sobre o problema, perguntas analíticas, fonte dos dados, regras de negócio, validações, limitações e dicionário de dados está em `docs/01_problema_e_dados.md`.

## Entregas

| Entrega | Onde está |
|---|---|
| Regra de classificação escrita | Seção [Regra de classificação](#regra-de-classificação) e função `classificar_laudo()` em `analise.py` |
| Cálculo de prioridade | Seção [Prioridade](#prioridade) e função `calcular_prioridade()` em `analise.py` |
| Pipeline com validação na entrada | `extracao.py` |
| Problema, perguntas analíticas e documentação dos dados | `docs/01_problema_e_dados.md` |

---

## Como funciona

```
dados/brutos/*.pdf
      │
      ▼
1. Cálculo do hash do arquivo (SHA-256) ── já existe no banco? ──► ignorado
      │
      ▼
2. Leitura do PDF (pypdf)
      │
      ▼
3. Extração dos campos (UC, OS, datas, ensaios, erros de exatidão, anomalias, conclusão)
      │
      ▼
4. Validação (PDF sem texto, data do ensaio, OS válida, OS repetida em outro arquivo)
      │
      ▼
5. Classificação e prioridade (analise.py)
      │
      ▼
6. Gravação no PostgreSQL (tabela laudos)  ──►  7. Exportação da tabela para dados/amostra/laudos.csv
```

### Identificação dos laudos e controle de duplicidade

Cada PDF é identificado pelo **hash SHA-256 do seu conteúdo** (`hash_arquivo`). O mesmo arquivo gera sempre o mesmo hash, mesmo que seja renomeado. A cada execução, o script lê todos os PDFs da pasta `dados/brutos` e ignora os que já estão no banco.

A **Ordem de Serviço (OS)** continua sendo o identificador de negócio do laudo, mas não é mais obrigatória:

- Quando a OS é encontrada, ela é gravada e `status_os = 'OK'`.
- Quando o campo está vazio no PDF, o laudo **é processado normalmente** (classificação e prioridade), com `ordem_servico = NULL` e `status_os = 'OS AUSENTE'`.
- O valor lido só é aceito como OS se tiver apenas letras e números, pelo menos um dígito e no mínimo 6 caracteres. Isso evita capturar rótulos vizinhos do PDF (como `UF` ou `ORDEM`) quando o campo está em branco.
- Se a mesma OS aparecer em **outro arquivo** (hash diferente), o laudo não é gravado e aparece na lista de erros como **possível reemissão**, para análise manual.

---

## Regra de classificação

A regra está em `classificar_laudo()` (`analise.py`) e é aplicada a cada laudo nesta ordem.

**Passo 1: ensaios qualitativos.** Verifica se os 4 ensaios abaixo estão **APROVADOS**:

- Integridade dos Lacres
- Inspeção Geral do Medidor
- Correspondência com o Modelo Aprovado
- Ensaio de Marcha em Vazio

**Passo 2: exatidão.** Verifica os erros de energia ativa (carga nominal, indutiva e pequena). Se qualquer erro, em módulo, for **superior a 15%**, a exatidão é considerada reprovada. Se o laudo não traz valores de erro (por exemplo, ensaio NÃO REALIZADO), a exatidão fica "sem valores".

Há **evidência técnica** quando algum ensaio qualitativo não foi aprovado **ou** a exatidão foi reprovada.

**Passo 3: anomalias descritas no laudo.** O texto da seção "Anomalia(s) Encontrada(s)" é comparado com listas de padrões:

| Grupo | Padrões procurados (sem acento, minúsculas) |
|---|---|
| Fraude/manipulação | tampa forçada, tampa aberta, by-pass, "não registra corretamente o consumo" |
| Defeito | display apagado, dispositivo de saída apagado |

Os padrões de fraude são testados antes dos de defeito.

**Resultado:**

| Situação | Classificação |
|---|---|
| Anomalia de fraude + evidência técnica | Possível fraude/manipulação (corroborada tecnicamente) |
| Anomalia de fraude sem evidência técnica | Possível fraude/manipulação (indício apenas textual) |
| Anomalia de defeito + evidência técnica | Possível defeito (corroborado tecnicamente) |
| Anomalia de defeito sem evidência técnica | Possível defeito (indício apenas textual) |
| Nenhuma anomalia reconhecida, 4 ensaios aprovados e exatidão aprovada | Sem indício identificado |
| Qualquer outro caso | Revisão manual |

A coluna `motivo_classificacao` registra o caminho percorrido (resultado da exatidão, maior erro e anomalia encontrada), para que cada decisão possa ser auditada.

## Prioridade

A prioridade é calculada em `calcular_prioridade()` (`analise.py`): um peso pela classificação somado ao maior erro de exatidão, em módulo, entre CN, CI e CP. Quanto maior o valor, mais cedo o laudo deve ser analisado.

| Classificação | Peso |
|---|---|
| Possível fraude/manipulação (corroborada tecnicamente) | 400 |
| Possível fraude/manipulação (indício apenas textual) | 300 |
| Possível defeito (corroborado tecnicamente) | 250 |
| Possível defeito (indício apenas textual) | 200 |
| Revisão manual | 100 |
| Sem indício identificado | 0 |

Exemplo: um laudo de fraude corroborada com maior erro de -89,21% recebe prioridade 400 + 89,21 = **489,21**.

---

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

### Atualizando de uma versão anterior

A partir da versão com identificação por hash, a tabela `laudos` ganhou as colunas `hash_arquivo` e `status_os`, e `ordem_servico` deixou de ser obrigatória. O comando `CREATE TABLE IF NOT EXISTS` **não altera uma tabela já existente**. Quem já tinha a tabela criada deve apagá-la antes de rodar a nova versão:

```sql
DROP TABLE laudos;
```

Na execução seguinte, a tabela é recriada e todos os PDFs da pasta `dados/brutos` são reprocessados.


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
3. Exemplos de consulta:

   ```sql
   -- Fila priorizada
   SELECT id, ordem_servico, status_os, arquivo,
          classificacao, prioridade, motivo_classificacao
   FROM laudos
   ORDER BY prioridade DESC;

   -- Laudos sem Ordem de Serviço
   SELECT id, arquivo, classificacao, prioridade
   FROM laudos
   WHERE status_os = 'OS AUSENTE';
   ```

---

## Dicionário de dados: tabela `laudos`

| Coluna | Tipo | Descrição |
|---|---|---|
| `id` | SERIAL | Chave primária. Identificador usado para referenciar o laudo nas análises |
| `hash_arquivo` | TEXT (único, obrigatório) | Hash SHA-256 do conteúdo do PDF; usado para evitar duplicidade |
| `ordem_servico` | TEXT (único, opcional) | Ordem de serviço do laudo; `NULL` quando o campo está vazio no PDF |
| `status_os` | TEXT | `OK` ou `OS AUSENTE` |
| `arquivo` | TEXT | Nome do PDF de origem |
| `uc` | TEXT | Unidade consumidora |
| `dt_retirada` | TEXT | Data de retirada do medidor |
| `data_ensaio` | TEXT | Data do ensaio em laboratório |
| `validacao_data_ensaio` | TEXT | `OK`, `NÃO ENCONTRADA`, `FORMATO INVÁLIDO` ou `DATA INVÁLIDA` |
| `integridade_lacres` | TEXT | APROVADO / REPROVADO |
| `inspecao_geral_medidor` | TEXT | APROVADO / REPROVADO |
| `correspondencia_mod_aprovado` | TEXT | APROVADO / REPROVADO |
| `ensaio_marcha_vazio` | TEXT | APROVADO / REPROVADO / NÃO REALIZADO |
| `erro_ativa_cn` | REAL | Erro (%) de energia ativa em carga nominal |
| `erro_ativa_ci` | REAL | Erro (%) de energia ativa em carga indutiva |
| `erro_ativa_cp` | REAL | Erro (%) de energia ativa em carga pequena |
| `resultado_exatidao_ativa` | TEXT | Resultado de exatidão informado no laudo |
| `analise_exatidao` | TEXT | Resultado recalculado pelo limite do projeto (erro superior a 15%) |
| `anomalias` | TEXT | Anomalias descritas, separadas por ` \| ` |
| `conclusao` | TEXT | Texto de conclusão/observações do laudo |
| `classificacao` | TEXT | Resultado da regra de classificação |
| `prioridade` | REAL | Peso da classificação + maior erro de exatidão em módulo |
| `motivo_classificacao` | TEXT | Justificativa da classificação |
| `data_ingestao` | TEXT | Data e hora em que o registro entrou no banco |
---

## Limitações conhecidas e próximos passos

- **Registros existentes não são atualizados:** se a regra mudar, os laudos já gravados mantêm a classificação antiga. Para reclassificar, limpe a tabela (`TRUNCATE laudos;`) e rode o script novamente.
- **Laudos sem OS não podem ser cruzados com a base da demandante:** eles entram na triagem e na fila, mas ficam fora da comparação com a classificação manual do analista (pergunta analítica 2), que depende da OS como chave. Nos exemplos analisados, a UC e o Nº do Medidor também vêm vazios, então não servem como chave alternativa.
- **Reemissão de laudos:** um laudo reemitido (PDF diferente com a mesma OS) não é gravado; fica na lista de erros para análise. Falta definir com a área demandante se a reemissão deve substituir o registro anterior. Um laudo que entrou sem OS e depois é reemitido com a OS preenchida entra como um segundo registro.
- **Datas armazenadas como texto:** a conversão para `DATE`/`TIMESTAMP` facilitaria filtros por período.
- **PDFs escaneados:** não são suportados (não há OCR).

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
| Ana Carolina Martir| [@acarolmartir-dotcom](https://github.com/acarolmartir-dotcom) |
| Victor Silva | [@Victor-CSilva](https://github.com/Victor-CSilva) |


|  |  |

Mentor: Ricardo Teixeira
