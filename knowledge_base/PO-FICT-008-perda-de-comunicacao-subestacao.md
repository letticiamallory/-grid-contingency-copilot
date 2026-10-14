---
code: PO-FICT-008
title: Perda de comunicação com subestação
version: "1.0"
status: vigente
ficticio: true
rascunho_assistido: true
applies_to: [substation_comm_loss]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Orientar o operador quando o centro de operação fictício perde a comunicação com uma subestação da rede Aurora.

## 2. Aplicabilidade
Aplica-se à perda de telemetria e de comando de uma subestação. Não se aplica à perda de um único ponto de medição.

## 3. Condições iniciais
O sistema de supervisão fictício sinalizou falha de comunicação com a subestação e os dados desta passaram a ser marcados como inválidos.

## 4. Ações

### 4.1 Verificações iniciais
1. Confirmar se a perda atinge uma só subestação ou várias, o que pode indicar falha no canal comum.
2. Verificar se há ocorrência de rede, como desligamentos, nas proximidades da subestação.
3. Registrar o horário da perda e o último estado conhecido da subestação.

### 4.2 Contenção
4. Tentar o canal de comunicação alternativo fictício com a subestação.
5. Se não houver canal alternativo, acionar a equipe de campo fictícia para contato local com a subestação.
6. Enquanto não houver dados válidos, tratar o último estado conhecido como incerto e evitar comandos que dependam dele.

## 5. Verificações finais
A comunicação foi restabelecida, os dados são válidos e o estado real da subestação foi confrontado com o último estado conhecido.

## 6. Comunicação
Avisar o supervisor do turno fictício e a equipe de telecomunicações fictícia.

## 7. Observações
Perda de comunicação não significa perda de energia. Não presumir desligamento sem confirmação por outra fonte.
