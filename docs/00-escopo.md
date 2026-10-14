# 00 - Escopo

## Objetivo

Construir um copiloto que, dado um evento de rede sintético (ex.: linha de transmissão desligada por atuação de proteção), sugere passos de resposta a um operador. Cada passo cita o trecho do procedimento operativo de onde veio. Quando não há procedimento aplicável, o sistema recusa explicitamente. O operador aprova ou rejeita cada sugestão, e tudo fica em uma trilha de auditoria.

O projeto demonstra engenharia de IA aplicada: citação obrigatória e verificável, recusa, aprovação humana, auditoria e avaliação medida. Foi inspirado em desafios públicos do setor elétrico e não replica nenhum projeto de terceiros.

## Não-objetivos

- Operar, simular ou integrar com sistemas reais (SCADA, EMS, SAGE etc.).
- Fidelidade técnica de engenharia elétrica: os procedimentos são fictícios e simplificados.
- Front-end elaborado, autenticação real, multi-tenancy, alta disponibilidade.
- Treinar ou fazer fine-tuning de modelos.
- Executar qualquer ação sobre a rede. O sistema só sugere; quem decide é o humano.
- Cobrir todo tipo de contingência. O escopo são 10 a 15 procedimentos.

## Personas

| Persona | Necessidade | Interação |
|---|---|---|
| Operador (simulado) | Receber passos de resposta rastreáveis e decidir rápido, sabendo de onde vem cada passo | Registra evento, solicita sugestão, aprova ou rejeita (com justificativa) |
| Avaliador (técnico que lê o repositório) | Verificar rigor: rodar a suíte de avaliação, ler as métricas, inspecionar a auditoria | Roda `make eval`, lê o relatório, consulta a trilha |

## Requisitos funcionais

| ID | Requisito |
|---|---|
| RF-01 | Registrar um evento de rede (tipo, elemento, horário, atributos livres). |
| RF-02 | Gerar sugestão para um evento: lista ordenada de passos, cada um com ao menos uma citação (procedimento, versão, seção, trecho literal). |
| RF-03 | Recusar quando a recuperação não achar procedimento aplicável ou quando nenhum passo puder ser citado. A recusa traz o motivo. |
| RF-04 | Validar cada citação: o trecho citado deve existir literalmente no procedimento indicado. Passo sem citação válida é descartado, e a sugestão sem passos vira recusa. |
| RF-05 | O operador aprova ou rejeita a sugestão como um todo. Rejeição exige justificativa. |
| RF-06 | Nenhuma sugestão é tratada como "aplicada" sem decisão humana registrada. |
| RF-07 | Registrar na trilha de auditoria: evento recebido, recuperação, chamada ao LLM (modelo, versão do prompt), resultado da validação, decisão. A trilha é só de acréscimo. |
| RF-08 | Consultar a trilha de um evento em ordem cronológica. |
| RF-09 | Carregar procedimentos (Markdown com front-matter) e indexá-los por comando. |
| RF-10 | Rodar a suíte de avaliação e produzir relatório comparando 2 modelos e com/sem RAG. |

## Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | Reprodutibilidade: `docker compose up` sobe API e banco; `make eval` roda a avaliação. |
| RNF-02 | Testabilidade: o domínio e a aplicação rodam em teste sem rede, sem banco e sem LLM (fakes nas portas). |
| RNF-03 | Resiliência do LLM: timeout, retry limitado, circuit breaker e fallback para um segundo modelo. Se tudo falhar, a resposta é um erro explícito, nunca uma sugestão sem citação. |
| RNF-04 | Auditabilidade: nenhum UPDATE ou DELETE na tabela de auditoria pela aplicação, e encadeamento por hash para detectar adulteração. |
| RNF-05 | Observabilidade mínima: logs estruturados com `event_id` e `suggestion_id`. |
| RNF-06 | Latência: sem meta rígida. Referência de 15 s por sugestão (p95), dominada pelo LLM. |
| RNF-07 | Custo: avaliação completa dentro de um orçamento pequeno (meta: abaixo de US$ 5 por rodada). |
| RNF-08 | Segurança do repositório: sem segredos versionados; chave do OpenRouter via variável de ambiente. |

## Critérios de aceite

1. Um evento coberto por procedimento gera sugestão em que 100% dos passos têm citação cujo trecho existe literalmente na base (verificado por código, não pelo LLM).
2. Um evento sem procedimento aplicável (cenário da suíte) é recusado, com motivo.
3. Não existe caminho na API que marque uma sugestão como aprovada sem registro de decisão humana.
4. A trilha de um evento reconstrói, em ordem, tudo o que aconteceu, e uma verificação de integridade detecta alteração manual de uma linha.
5. A suíte de avaliação tem de 20 a 30 categorias de cenários, roda em um comando e gera tabela com as métricas definidas em `03-avaliacao.md`.
6. A CI roda lint, testes unitários e de integração e o subconjunto de avaliação com LLM falso (determinístico) a cada push.
7. O README declara os dados como sintéticos e o sistema como não adequado para operação real.

## Premissas

- Horas: 20 h no total, 5 h por semana.
- Um único desenvolvedor, sem revisão externa. A qualidade depende de testes e checklists.
- Os procedimentos fictícios são escritos pela autora, em ao menos 10 arquivos.
- O OpenRouter está disponível e há créditos para a avaliação.
- O operador é identificado por um campo textual na requisição (sem login).

## Riscos

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Escrever os procedimentos consome mais tempo do que o previsto | Alta | Alto | Limitar a 10 procedimentos curtos no mínimo; guia em `04-base-de-conhecimento.md` |
| Estourar as 20 h | Alta | Alto | Roadmap com versão mínima; extras só depois do ponto de divulgação |
| Cenários de avaliação escritos pela mesma pessoa que escreveu os procedimentos enviesam as métricas | Alta | Médio | Declarar o viés; incluir cenários adversariais e ambíguos; não afirmar generalização |
| LLM cita trecho parafraseado e a validação literal rejeita sugestões boas | Média | Médio | Normalização de espaços e caixa antes da comparação; medir a taxa de rejeição na avaliação |
| Custo ou instabilidade do OpenRouter | Média | Baixo | `FakeLLM` para CI, cache de respostas na avaliação, limite de gasto |
| Conteúdo parecer real e ser confundido com orientação operativa | Baixa | Alto | Procedimentos com prefixo `FICT`, aviso no README e em cada resposta da API |
| Complexidade desnecessária (LangGraph, Redis) | Média | Médio | ADR-004 e roadmap tratam como extras |
