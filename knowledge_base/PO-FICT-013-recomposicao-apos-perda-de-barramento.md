---
code: PO-FICT-013
title: Recomposição após perda de barramento
version: "1.0"
status: vigente
ficticio: true
rascunho_assistido: true
applies_to: [busbar_loss]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Orientar a recomposição de um barramento da rede fictícia Aurora depois da resposta inicial à sua perda.

## 2. Aplicabilidade
Aplica-se depois que a manutenção liberou o barramento. A resposta inicial à perda é tratada no PO-FICT-005. Este procedimento não se aplica se a causa da perda ainda não foi identificada.

## 3. Condições iniciais
O barramento está desenergizado, a manutenção liberou formalmente o equipamento e a causa da perda está registrada.

## 4. Ações

### 4.1 Preparação
1. Confirmar a liberação formal da manutenção antes de qualquer manobra.
2. Confirmar que todos os disjuntores ligados ao barramento estão abertos.
3. Definir com o supervisor do turno fictício a ordem de recomposição dos circuitos.

### 4.2 Energização
4. Energizar o barramento por uma única fonte, sem circuitos de carga conectados.
5. Verificar a tensão do barramento antes de seguir.
6. Fechar os circuitos de carga um de cada vez, verificando a tensão e o carregamento após cada manobra.

## 5. Verificações finais
Todos os circuitos previstos estão restabelecidos, sem nova atuação de proteção, e o barramento opera com tensão e carregamento normais.

## 6. Comunicação
Avisar o supervisor do turno fictício a cada etapa concluída e a área de planejamento fictícia ao final.

## 7. Observações
Quando houver conflito entre este procedimento e o PO-FICT-005 sobre fechar disjuntores no barramento, vale o PO-FICT-005 até a liberação formal da manutenção.
