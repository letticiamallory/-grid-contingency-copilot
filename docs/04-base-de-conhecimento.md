# 04 - Base de conhecimento

Guia para escrever 10 a 15 procedimentos operativos fictícios. Regras de conteúdo em ADR-007.

## Declaração de rascunhos assistidos

Os 12 procedimentos em `knowledge_base/` começaram como rascunhos gerados por LLM (Claude), a pedido da autora, a partir do template e dos temas deste guia (ADR-007). Cada arquivo tem `rascunho_assistido: true` no front-matter. A autora deve reescrever cada um com suas próprias palavras e então mudar o campo para `false`. Antes de publicar o repositório, nenhum arquivo deve continuar `true` sem que essa decisão seja deliberada e declarada no README.

Convenção adotada nos rascunhos: subseções usam `### 4.1 Título` (o ingestor divide por `##` e `###`); o aviso de ficção fica em um bloco `>` logo abaixo do front-matter e não é indexado.

## Regras rápidas

- Tudo é inventado: códigos, nomes de equipamentos, valores. Nada copiado, nada vindo de empregador atual ou anterior.
- Código no formato `PO-FICT-NNN`; campo `ficticio: true`; aviso no cabeçalho.
- Tamanho: 250 a 450 palavras por procedimento, 4 a 8 seções curtas, 5 a 12 passos numerados.
- Nível de detalhe: o suficiente para um passo ser verificável ("confirmar a posição dos disjuntores nas duas extremidades"), sem números de engenharia que pareçam limites reais. Se precisar de valor, use um claramente fictício e marcado (ex.: "limite fictício L1").
- Cada passo deve ser uma frase completa e citável, de preferência com um verbo de ação.
- Escreva ao menos 2 procedimentos com sobreposição parcial (para os cenários ambíguos) e 1 marcado como `status: revogado` (para C19).
- Escreva os procedimentos em arquivos Markdown separados em `knowledge_base/`.

Estimativa: 15 a 20 minutos por procedimento, cerca de 3 h para 10. O roadmap reserva esse tempo.

## Template

```markdown
---
code: PO-FICT-000
title: Título curto
version: "1.0"
status: vigente            # vigente | revogado
ficticio: true
applies_to: [tipo_de_evento_1, tipo_de_evento_2]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Uma ou duas frases.

## 2. Aplicabilidade
Quando este procedimento se aplica e quando não se aplica.

## 3. Condições iniciais
O que deve ter sido observado antes de começar.

## 4. Ações
4.1 Verificações iniciais
1. Passo.
2. Passo.

4.2 Ações de recomposição ou contenção
3. Passo.

## 5. Verificações finais
Como saber que a situação foi tratada.

## 6. Comunicação
A quem avisar (cargos fictícios, sem nomes de pessoas ou empresas).

## 7. Observações
Restrições, exceções, referências a outros procedimentos fictícios.
```

O ingestor divide por seção (e subseção). Cada chunk guarda o código, a versão e o título da seção. Evite seções com mais de ~200 palavras.

## 10 temas sugeridos

| Código | Tema |
|---|---|
| PO-FICT-001 | Linha de transmissão desligada por proteção de distância |
| PO-FICT-002 | Religamento automático sem sucesso |
| PO-FICT-003 | Transformador desligado por proteção diferencial |
| PO-FICT-004 | Sobrecarga em transformador |
| PO-FICT-005 | Perda de barramento |
| PO-FICT-006 | Subtensão em barra |
| PO-FICT-007 | Sobretensão em barra |
| PO-FICT-008 | Perda de comunicação com subestação |
| PO-FICT-009 | Atuação de proteção de falha de disjuntor |
| PO-FICT-010 | Variação de frequência fora da faixa |

Extras opcionais (até 15): 011 versão revogada do 001 (para C19); 012 procedimento geral de comunicação de ocorrências; 013 recomposição após perda de barramento (sobreposição com 005).

## Exemplos curtos (claramente fictícios)

### Exemplo 1

```markdown
---
code: PO-FICT-001
title: Linha desligada por proteção de distância
version: "1.0"
status: vigente
ficticio: true
applies_to: [line_trip_by_protection]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Orientar a resposta a um desligamento de linha por proteção de distância na rede fictícia Aurora.

## 2. Aplicabilidade
Aplica-se a linhas da rede Aurora de 230 kV fictício. Não se aplica a transformadores.

## 4. Ações
4.1 Verificações iniciais
1. Confirmar a posição dos disjuntores em ambas as extremidades da linha.
2. Registrar o horário, a zona de atuação e o resultado do religamento automático.
3. Verificar se há outros desligamentos próximos no mesmo intervalo.

4.2 Recomposição
4. Se o religamento automático foi bem-sucedido, manter a linha em observação por 30 minutos fictícios.
5. Se o religamento falhou, não religar manualmente antes de solicitar inspeção da linha.

## 6. Comunicação
Avisar o supervisor do turno fictício e a equipe de manutenção da rede Aurora.
```

### Exemplo 2

```markdown
---
code: PO-FICT-004
title: Sobrecarga em transformador
version: "1.0"
status: vigente
ficticio: true
applies_to: [transformer_overload]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Reduzir a carga de um transformador fictício acima do limite fictício L1.

## 4. Ações
1. Confirmar a leitura de carga em duas fontes de medição independentes.
2. Verificar se há transformador em paralelo disponível na mesma subestação.
3. Se houver, redistribuir a carga entre os transformadores antes de qualquer corte.
4. Se não houver, solicitar ao supervisor do turno fictício a avaliação de redução de carga.
5. Acompanhar a temperatura do óleo fictícia a cada 10 minutos até normalizar.
```

### Exemplo 3 (revogado, para o cenário C19)

```markdown
---
code: PO-FICT-011
title: Linha desligada por proteção de distância (versão antiga)
version: "0.9"
status: revogado
ficticio: true
applies_to: [line_trip_by_protection]
---

> Conteúdo fictício. Este procedimento foi revogado e substituído pelo PO-FICT-001.

## 4. Ações
1. Religar a linha imediatamente após o primeiro desligamento.
```

O retriever deve ignorar procedimentos `revogado` (filtro por `status`), e o cenário C19 verifica isso. O passo "religar imediatamente" também entra como `forbidden_steps`.

## Checklist de qualidade antes de ingerir

- [ ] Prefixo `PO-FICT-`, `ficticio: true` e aviso no topo.
- [ ] Sem nomes de empresas reais, subestações reais, sistemas reais ou pessoas.
- [ ] Sem trechos copiados de norma, manual ou procedimento de terceiros.
- [ ] Passos são frases completas, citáveis e sem referência a "ver acima".
- [ ] Valores numéricos são fictícios e identificados como tais.
- [ ] Ao menos 2 procedimentos com sobreposição parcial e 1 revogado.
- [ ] Rascunhos assistidos por LLM foram reescritos e estão declarados (ADR-007).
