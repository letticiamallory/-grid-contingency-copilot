# ADR-007: Dados sintéticos e política de conteúdo

- Status: aceito
- Data: a preencher

## Contexto

O projeto será público e trata de um domínio sensível (infraestrutura crítica). A autora tem vínculos profissionais, atuais ou anteriores, que impõem restrições de confidencialidade e de propriedade intelectual. O repositório não pode conter nada que pareça orientação operativa real nem material de terceiros.

## Drivers de decisão

- Zero risco de vazamento ou de uso de material confidencial ou de empregadores.
- Zero risco de o conteúdo ser tomado como procedimento real.
- Conteúdo suficientemente realista para a avaliação ser significativa.
- Custo de produção do conteúdo dentro do orçamento.

## Opções consideradas

**A. Procedimentos escritos do zero, fictícios, com marcadores explícitos (escolhida)**
- Prós: controle total da origem; fácil provar que é autoral.
- Contras: custo de escrita; o realismo depende do que a autora sabe de forma pública; viés dos cenários (ver ADR-008).

**B. Resumos de documentos públicos (normas, procedimentos de rede publicados por operadores)**
- Prós: realismo.
- Contras: risco de reprodução; questões de licença e atualização; dificulta afirmar que é "sintético". Permitido apenas como inspiração de estrutura, sem trechos.

**C. Gerar os procedimentos com LLM**
- Prós: rapidez e volume.
- Contras: texto genérico e homogêneo; risco de reproduzir material memorizado; perde a autoria. Aceito apenas para gerar rascunhos de eventos de teste, sempre revisados.

**D. Material de empregadores, mesmo anonimizado**
- Descartada. Anonimizar não elimina o risco.

## Decisão

Opção A, com a seguinte política.

**Pode entrar no repositório:**
- Procedimentos e eventos escritos pela autora, com nomes, códigos, tensões e equipamentos inventados.
- Estrutura geral de um procedimento (objetivo, condições, passos, verificações), por ser prática comum e genérica.
- Referências a conceitos públicos (proteção, religamento, seccionamento) em nível didático.
- Rascunhos assistidos por LLM, reescritos e revisados pela autora, e declarados como tais no `04-base-de-conhecimento.md`.

**Não pode entrar:**
- Qualquer trecho, nome de documento, código de procedimento, nomenclatura de subestação, nome de sistema ou dado de empregadores atuais ou anteriores.
- Trechos copiados de normas, manuais ou procedimentos de operadores públicos ou privados.
- Dados reais de rede, mesmo públicos, em formato que pareça telemetria operacional.
- Valores numéricos que possam ser tomados como limites operativos reais; os números são fictícios e marcados como tal.
- Afirmações de que o projeto replica ou reproduz solução de terceiros.

**Marcadores obrigatórios:** todos os procedimentos têm o prefixo `PO-FICT-`, o campo `ficticio: true` no front-end matter e o aviso no cabeçalho. Toda resposta da API inclui o campo `disclaimer`. O README e a licença repetem o aviso.

**Verificação:** um teste de CI falha se um procedimento não tiver os marcadores. Uma revisão manual final, com checklist de política, é obrigatória antes de publicar o repositório.

## Consequências

- O realismo é limitado: o sistema não prova desempenho sobre procedimentos reais, e o README diz isso.
- A autora deve manter, fora do repositório, qualquer rascunho que tenha dúvida de origem. Na dúvida, o conteúdo não entra.
- Contribuições externas devem seguir a mesma política (registrada no `CONTRIBUTING.md`).
