# ADR-004: Orquestração do agente (LangGraph vs fluxo simples em código)

- Status: aceito
- Data: a preencher

## Contexto

O fluxo de geração é: recuperar, decidir se recusa, gerar, validar citações, persistir. Há uma chamada ao LLM e, no máximo, uma repetição (reformular a busca ou tentar o modelo de fallback). Não há loops abertos, ferramentas escolhidas pelo modelo, nem estado compartilhado entre sessões.

## Drivers de decisão

- Adequação ao fluxo real, que é essencialmente linear.
- Orçamento de 20 h.
- Testabilidade do caso de uso com fakes.
- Clareza para quem lê o código em poucos minutos.

## Opções consideradas

**A. Função de caso de uso em Python puro (sequência explícita, um `if` para recusa)**
- Prós: lê-se de cima a baixo; teste direto; sem dependência; o rastro de auditoria é gravado em pontos óbvios.
- Contras: se o fluxo crescer (várias rodadas de ferramenta, ramificações), a lógica de controle passa a ser escrita à mão.

**B. LangGraph (grafo de estados com nós para retrieve, generate, validate, refuse)**
- Prós: topologia explícita e visualizável; checkpoints; bom para ciclos e `human-in-the-loop` interno ao grafo.
- Contras: para cinco passos lineares, o grafo é cerimônia; o estado tipado e o runtime acrescentam conceitos; depurar um erro passa pelo framework; o `human-in-the-loop` deste projeto é uma decisão entre requisições HTTP, persistida no banco, e não uma pausa dentro de um grafo.

**C. Biblioteca de pipeline mais leve (LlamaIndex/Haystack)**
- Prós: componentes de RAG prontos.
- Contras: esconde justamente as partes que o projeto quer mostrar (citação, recusa, auditoria); acopla o domínio a uma abstração externa.

## Decisão

Opção A. O fluxo atual não justifica um grafo, e dizer o contrário seria escolher pela vitrine. A decisão de design que importa fica visível no código: um caso de uso, portas para o LLM e o retriever, e a regra de recusa no domínio.

LangGraph fica como extra opcional, com um critério objetivo para entrar: se for implementado um modo de reformulação iterativa da busca (agente que decide buscar de novo), o ciclo passa a justificar o grafo. Nesse caso, reimplementa-se o mesmo caso de uso como grafo, atrás da mesma porta, e a avaliação compara os dois.

## Consequências

- O projeto não demonstra LangGraph. Isso é aceito: a experiência prévia com LangGraph consta do currículo, e este repositório mostra outra competência (rigor de verificação e avaliação).
- Se o extra for feito, o ganho é um comparativo honesto (complexidade e resultado) em vez de uma adoção presumida.
- A porta `GenerateSuggestion` permite trocar a implementação sem tocar na API.
