# ADR-008: Estratégia de avaliação

- Status: aceito
- Data: a preencher

## Contexto

"Funciona" não basta para sistema que sugere ações com citação. É preciso medir se o procedimento certo foi recuperado, se as citações são fiéis, se o sistema recusa quando deve e se inventa conteúdo. Uma única pessoa escreve os procedimentos e os cenários, o que cria viés.

## Drivers de decisão

- Métricas separadas por etapa (recuperação, geração, recusa), para localizar a falha.
- Execução reprodutível e barata.
- Comparação honesta entre 2 modelos e entre com/sem RAG.
- Admitir e reduzir o viés do autor único.

## Opções consideradas

**A. Conjunto de cenários próprio (YAML) com ground truth e métricas programáticas**
- Prós: controle total; métricas objetivas onde possível (procedimento esperado, citações válidas, recusa esperada); roda em CI com `FakeLLM` e fora dela com modelos reais.
- Contras: tamanho pequeno (cerca de 60 a 90 cenários), com intervalo de confiança largo; viés do autor.

**B. LLM-as-judge para tudo**
- Prós: cobre fidelidade semântica sem rotulagem manual.
- Contras: o juiz erra e tem vieses; resultado não verificável sem calibração.

**C. Frameworks de avaliação (Ragas, DeepEval, promptfoo)**
- Prós: métricas prontas.
- Contras: caixas-pretas para métricas que o projeto quer definir; dependência pesada. Podem inspirar, mas as definições ficam no repositório.

**D. Avaliação só manual**
- Prós: mais fiel.
- Contras: não repetível; não entra em CI.

## Decisão

Combinação de A com B limitado:

- Cenários em YAML com ground truth (ver `03-avaliacao.md`), de 20 a 30 categorias, com ao menos 2 cenários por categoria.
- Métricas programáticas: recuperação (Recall@k e MRR do procedimento correto), fidelidade da citação (fração de citações válidas por verificação literal), recusa correta (precisão e recall da recusa), e taxa de alucinação definida operacionalmente (passo cuja citação falha, mais passos que contradizem a lista de "passos proibidos" do cenário).
- Fidelidade semântica por juiz LLM apenas em amostra, com 20 julgamentos conferidos manualmente para reportar a concordância juiz x humana.
- Comparação: 2 modelos x {com RAG, sem RAG}, mesma temperatura (0) e mesma versão de prompt, 3 repetições por cenário para medir variância, fallback desligado.
- Parte dos cenários (ao menos 30%) é escrita antes dos procedimentos que testam, a partir de um resumo do evento, e outra parte depois, para reduzir o viés. Uma terceira pessoa revisando cenários seria o ideal (próximo passo).
- Intervalos de confiança por bootstrap, com o número de cenários exibido ao lado de cada métrica. Diferenças menores que o intervalo não são reportadas como vitória.

## Consequências

- Os resultados dizem pouco sobre generalização: servem para comparar configurações dentro do mesmo conjunto, e o README afirma isso.
- O custo por rodada é de 2 modelos x 2 configurações x cerca de 70 cenários x 3 repetições; o cache de respostas por hash de entrada evita pagar duas vezes por reexecuções.
- O limiar de recusa é calibrado em metade dos cenários e medido na outra metade, para evitar ajuste ao teste.
- A CI executa só o subconjunto determinístico (FakeLLM e verificação de citação); a avaliação com modelos reais é manual e seus relatórios são versionados em `eval/reports/`.
