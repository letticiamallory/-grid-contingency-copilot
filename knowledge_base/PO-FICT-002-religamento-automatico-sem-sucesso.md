---
code: PO-FICT-002
title: Religamento automático sem sucesso
version: "1.0"
status: vigente
ficticio: true
rascunho_assistido: true
applies_to: [line_reclosing_failed, line_trip_by_protection]
---

> Conteúdo fictício para demonstração. Não usar em operação real.

## 1. Objetivo
Definir a conduta quando uma linha da rede fictícia Aurora permanece aberta após a tentativa de religamento automático.

## 2. Aplicabilidade
Aplica-se quando o religamento automático foi tentado e a linha voltou a abrir ou não fechou. Não se aplica a linhas sem religamento automático habilitado.

## 3. Condições iniciais
A proteção atuou, o religamento automático foi tentado e a linha está aberta. O PO-FICT-001 já foi iniciado ou está em andamento.

## 4. Ações

### 4.1 Contenção
1. Manter a linha aberta e impedir qualquer religamento manual até a liberação da manutenção.
2. Registrar quantas tentativas de religamento ocorreram e o intervalo entre elas.
3. Verificar se existe caminho alternativo de transmissão para a carga atendida pela linha.

### 4.2 Acionamento
4. Solicitar à equipe de manutenção da rede Aurora a inspeção da linha, informando a zona de atuação da proteção.
5. Informar ao supervisor do turno fictício a condição de carregamento das linhas vizinhas.

### 4.3 Liberação
6. Somente após a liberação formal da manutenção, avaliar o religamento manual com a anuência do supervisor do turno.
7. Após o religamento manual, manter observação reforçada por 60 minutos fictícios.

## 5. Verificações finais
A liberação da manutenção está registrada, a linha está fechada e não houve nova atuação de proteção durante a observação.

## 6. Comunicação
Avisar o supervisor do turno fictício e a equipe de manutenção a cada mudança de estado da linha.

## 7. Observações
Este procedimento complementa o PO-FICT-001. Em caso de divergência sobre religamento manual, prevalece a regra mais restritiva.
