    ## rubrica : problema + perguntas analiticas + documentacao da fonte dos dados

 # 1. Problema e Dados

## 1.1 Problema

Atualmente, a análise dos laudos de aferição de medidores é realizada de forma manual. 
O processo apresenta alto volume de documentos, demanda tempo dos analistas e está sujeito  a falhas humanas e divergências de interpretação.

O volume médio é de aproximadamente 810 laudos por mês, com tempo médio de análise de 20 minutos por laudo.

Além da análise manual, foram identificados problemas relacionados à subjetividade na interpretação dos laudos e ao direcionamento do diagnóstico de campo.

Dessa forma, o projeto busca automatizar parte desse processo, extraindo informações dos laudos em PDF, validando os dados, classificando os casos e estruturando uma fila de prioridades para apoiar a atuação dos analistas.

## 1.2 Usuário e decisão

O principal usuário da solução é o analista de perdas.

A solução deverá apoiar o analista na identificação e priorização dos laudos que necessitam de análise, fornecendo as informações extraídas e a classificação atribuída ao documento.

A decisão final sobre o tratamento do caso permanece com o analista.

## 1.3 Objetivo da solução

Automatizar a análise inicial dos laudos de aferição de medidores em formato PDF, permitindo:

- extrair informações relevantes dos documentos;
- validar informações de identificação;
- identificar resultados dos ensaios;
- analisar erros percentuais;
- identificar anomalias;
- classificar os laudos em categorias;
- organizar uma fila de prioridades para análise

## 1.4 Fonte dos dados

Os dados utilizados no projeto são provenientes de laudos de aferição de medidores fornecidos em formato PDF.

Os documentos possuem informações de identificação do cliente e do medidor, resultados dos ensaios realizados, valores de erro, descrição de anomalias e conclusão do laboratório.

A amostra disponibilizada para o desenvolvimento contém laudos com diferentes resultados, incluindo casos aprovados e reprovados.

## 1.5 Dados disponíveis

Os dados disponíveis nos PDFs são mais amplos do que os campos atualmente extraídos e armazenados pelo pipeline. A definição dos campos utilizados na solução deverá considerar tanto as informações presentes nos documentos quanto os requisitos necessários para classificação e priorização. Os principais dados identificados nos laudos são:

### Identificação

- Nome do cliente;
- Unidade Consumidora (UC);
- Ordem de Serviço (OS);
- Número do medidor;
- Data de retirada;
- Data do ensaio

### Dados do medidor

- Fabricante;
- Modelo;
- Classe;
- Tensão nominal;
- Corrente nominal;
- Constante KD/KE;
- Número do invólucro;
- Lacres

### Resultados dos ensaios

- Integridade dos lacres;
- Inspeção geral do medidor;
- Correspondência do modelo aprovado;
- Ensaio de marcha em vazio;
- Resultado do ensaio de exatidão de energia ativa;
- Erros de energia ativa nas cargas CN, CI e CP

### Informações para classificação

- Anomalias encontradas;
- Conclusão do laudo;
- Resultado dos ensaios;
- Valores de erro percentual

## 1.6 Perguntas analíticas

A partir dos dados disponíveis, foram definidas as seguintes perguntas:

1. Como os laudos se distribuem entre as classificações de Possível fraude/manipulação, Possível defeito, Sem indício identificado e Revisão manual?

2. Quais resultados dos ensaios e quais tipos de anomalias estão associados às diferentes classificações?

3. Entre os laudos classificados como possível fraude/manipulação, quais apresentam as maiores discrepâncias nos ensaios de energia ativa?

## 1.7 Regras de negócio levantadas

As regras apresentadas representam as regras de negócio levantadas junto à área demandante. A implementação dessas regras no pipeline está sujeita a validação e pode apresentar diferenças durante a etapa de desenvolvimento.

### Sem indício identificado

O laudo pode ser considerado Sem indício identificado quando os ensaios e itens de integridade/lacre estão aprovados e não existem anomalias que indiquem irregularidade.

### Possível fraude/manipulação

A classificação de possível fraude/manipulação está associada à identificação de manipulação do medidor.

Entre os indicadores levantados estão:

- erro percentual de energia ativa superior a 15% em valor absoluto;
- bypass ou desvio de corrente;
- tampa forçada ou aberta;
- violação ou irregularidade relacionada aos lacres;
- outras anomalias que indiquem manipulação

### Possível defeito

A classificação de possível defeito está associada a problemas do equipamento sem indicação de manipulação humana.

Entre os exemplos levantados estão:

- display apagado;
- visor apagado;
- problemas relacionados ao funcionamento do equipamento;
- erros dentro do limite de 15%, quando não houver indícios de manipulação

> As regras de classificação apresentadas nesta seção foram levantadas durante a reunião com a área demandante e ainda estão sujeitas à validação.

### Revisão manual

Casos que não possam ser classificados de forma segura pelas regras estabelecidas devem ser encaminhados para revisão manual.

## 1.8 Priorização

O pipeline possui uma função para calcular a prioridade dos casos de possível fraude/manipulação com base na maior discrepância absoluta entre os ensaios CN, CI e CP. A ordenação da fila deve ser verificada na etapa de integração/análise.

## 1.9 Validações dos dados

Durante a extração, algumas informações deverão ser validadas:

- Nome do cliente;
- Unidade Consumidora (UC);
- Ordem de Serviço (OS);
- Número do medidor;
- Datas;
- Resultados dos ensaios;
- Valores de erro;
- Existência e conteúdo das anomalias

A UC deverá ser padronizada para 12 caracteres, com preenchimento de zeros à esquerda quando necessário.

A Ordem de Serviço também deverá ser utilizada para identificação de possíveis duplicidades.

## 1.10 Limitações e pontos pendentes

Alguns pontos ainda dependem de validação com a área demandante:

- quantidade e formato exatos dos caracteres da Ordem de Serviço;
- formato esperado do Número do Medidor;
- lista completa de palavras-chave para identificação de fraude e defeito;
- disponibilização de uma amostra maior de laudos para testes;
- validação das regras de classificação com a área responsável;
- validação da Ordem de Serviço ainda possui uma limitação: registros com OS em branco não são atualmente rejeitados pelo pipeline

## 1.11 Dicionário de dados

O dicionário abaixo descreve os principais campos identificados nos laudos de aferição. Nem todos os campos identificados nos documentos fazem parte da tabela atualmente implementada no banco de dados.

### Identificação do cliente e do laudo

| Campo                     | Tipo  | Utilização no projeto                                       |
| ------------------------- | ----- | ----------------------------------------------------------- |
| **Cliente**               | Texto | Identificação e validação do cliente                        |
| **UC**                    | Texto | Identificação da unidade consumidora e validação            |
| **Ordem de Serviço (OS)** | Texto | Identificação do atendimento e controle de duplicidade      |
| **Nº do Medidor**         | Texto | Identificação do equipamento e cruzamento com dados/imagens |
| **Data de Retirada**      | Data  | Identificação temporal do atendimento                       |
| **Data do Ensaio**        | Data  | Identificação da data da aferição                           |
| **Validação Data Ensaio** | Categ | Indicação do resultado da validação da data extraída        |

### Dados do medidor

| Campo                   | Tipo           | Utilização                        |
| ----------------------- | -------------- | --------------------------------- |
| **Fabricante**          | Texto          | Identificação do equipamento      |
| **Modelo**              | Texto          | Identificação do equipamento      |
| **Classe**              | Texto          | Caracterização do medidor         |
| **Tensão Nominal**      | Numérico/Texto | Informação técnica do equipamento |
| **Corrente Nominal**    | Numérico       | Informação técnica do equipamento |
| **Constante KD/KE**     | Numérico       | Informação técnica do equipamento |
| **Número do Invólucro** | Texto          | Identificação física              |
| **Lacre(s)**            | Texto          | Verificação de integridade        |


### Resultados dos ensaios

### Resultados dos ensaios

| Campo | Tipo | Valores esperados | Utilização 
|
| --------------------------------- | ---------- | ------------------------------------ | ---------------------------------- |
| **Integridade dos Lacres** | Categórico | APROVADO / REPROVADO | Verificação de irregularidade |
| **Inspeção Geral do Medidor** | Categórico | APROVADO / REPROVADO | Classificação |
| **Correspondência Mod. Aprovado** | Categórico | APROVADO / REPROVADO | Classificação |
| **Ensaio de Marcha em Vazio** | Categórico | APROVADO / REPROVADO / NÃO REALIZADO | Classificação e necessidade de análise |
| **Erro Energia Ativa CN** | Numérico | Valor numérico (%) | Análise da exatidão e priorização |
| **Erro Energia Ativa CI** | Numérico | Valor numérico (%) | Análise da exatidão e priorização |
| **Erro Energia Ativa CP** | Numérico | Valor numérico (%) | Análise da exatidão e priorização |
| **Resultado Exatidão Energia Ativa** | Categórico | APROVADO / REPROVADO / NÃO REALIZADO | Resultado do ensaio de exatidão |
| **Análise da Exatidão** | Categórico | Resultado da análise considerando o limite de 15% | Apoio à classificação |



### Informações para classificação

| Campo                                     | Tipo         | Utilização na classificação                                                  |
| ----------------------------------------- | ------------ | ---------------------------------------------------------------------------- |
| **Anomalias Encontradas**                 | Texto        | Identificar indícios de fraude ou defeito por meio das ocorrências descritas |
| **Conclusão do Laudo**                    | Texto        | Apoiar a validação da classificação                                          |


## 1.12 Dados derivados

| Campo                   | Origem           | Tipo                | Como é obtido                          |
| ----------------------- | ---------------- | ------------------- | -------------------------------------- |
| Maior discrepância      | Calculado        | Numérico            | Maior valor absoluto entre CN, CI e CP |
| Classificação           | Regra de negócio | Categórico          | Aplicação das regras                   |
| Motivo da classificação | Calculado        | Texto               | Regra que determinou a classificação   |
| Prioridade              | Calculado        | Numérico/Categórico | Classificação + discrepância           |

## 1.13 Pontos pendentes com a área demandante

- definição da data de referência para apresentação dos laudos na dashboard: data de retirada do equipamento ou data de realização do ensaio;
- disponibilização das palavras-chave, expressões ou critérios atualmente utilizados no campo 6 - “Anomalia(s) Encontrada(s) - Descrição” - para identificação de possíveis casos de fraude/manipulação e possível defeito;
- disponibilização de 3 laudos por mês, idealmente dos últimos 12 meses, contemplando 1 caso de possível fraude, 1 de possível defeito e 1 aprovado;
- validação das regras de classificação

