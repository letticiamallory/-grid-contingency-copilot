# 06 - Riscos e limitações

## Aviso de uso

Este projeto é uma demonstração técnica com dados e procedimentos fictícios. Ele não foi validado por especialistas em operação de sistemas elétricos, não deve orientar nenhuma decisão operativa real e não deve ser conectado a sistemas de operação. As sugestões, mesmo com citação válida, podem estar erradas ou ser inadequadas.

## Riscos técnicos

| Risco | Descrição | Mitigação | Residual |
|---|---|---|---|
| Citação válida, passo errado | A verificação é literal; o passo pode não decorrer do trecho | Medição por juiz em amostra; lista de passos proibidos; aprovação humana | Permanece. É a limitação central |
| Paráfrase rejeitada | Citação correta com pequena diferença de texto é descartada | Normalização; medir a taxa de descarte | Perda de recall aceita |
| Limiar de recusa mal calibrado | Recusa demais ou de menos | Calibração separada do teste; relatar a troca | Depende do conjunto pequeno |
| Variância do LLM | Respostas diferentes entre execuções | Temperatura 0, 3 repetições, intervalos de confiança | Alguma variância permanece |
| Injeção de prompt via atributos do evento | Texto no evento tenta mudar o comportamento | Atributos entram como dados delimitados; categoria C20 na avaliação; a verificação de citação limita o dano | Não eliminado |
| Dependência do OpenRouter | Indisponibilidade, mudança de modelo | Porta de LLM, versionamento do modelo nos relatórios, erro 503 explícito | Resultados antigos podem não ser reproduzíveis |
| Auditoria não é imutável de fato | Quem tem superusuário do banco pode reescrever a cadeia inteira | Hash detecta alteração parcial; ancoragem externa como próximo passo | Não protege contra administrador |
| Concorrência na cadeia de hash | Duas escritas simultâneas podem bifurcar a cadeia | Lock consultivo por evento | Testar explicitamente |
| Embeddings acoplados ao modelo | Troca exige reindexar | `content_hash` e modelo registrado na ingestão | Custo de reindexação |
| Sem autenticação | Qualquer um pode aprovar | Declarado; operador como texto | Fora do escopo |

## Riscos de conteúdo

| Risco | Mitigação |
|---|---|
| Material de empregador entrar no repositório | Política do ADR-007; checklist de publicação; na dúvida, não entra |
| Procedimento fictício parecer real | Prefixo `PO-FICT`, `ficticio: true`, aviso em cada resposta e no README |
| Reprodução de trechos de normas ou manuais | Procedimentos escritos do zero; rascunhos de LLM reescritos |
| Texto de apoio sugerir equivalência com projeto de terceiros | Posicionamento: inspirado em desafios públicos do setor |
| Valores numéricos tomados como limites reais | Valores fictícios e identificados como tal |
| Viés do autor único nos cenários | Cenários escritos antes da base, separação calibração/teste, resultado dito como não generalizável |

## O que o sistema não faz

- Não opera, comanda ou envia ordens a equipamento algum.
- Não lê telemetria nem integra com SCADA, EMS ou historiadores.
- Não decide: não há aprovação automática.
- Não valida a correção técnica de engenharia dos procedimentos.
- Não garante que a sugestão esteja completa; pode omitir passos que o procedimento prevê.
- Não lida com procedimentos em outros idiomas, imagens, tabelas ou diagramas.
- Não identifica nem autentica usuários.
- Não oferece alta disponibilidade, backup ou recuperação de desastre.
- Não mede latência sob carga; foi pensado para um operador.
- Não aprende com as decisões dos operadores (as rejeições são registradas, mas não retroalimentam o sistema).

## Limitações da avaliação

- Poucas dezenas de cenários, escritos por uma pessoa, sobre uma base de 10 a 15 procedimentos escritos pela mesma pessoa.
- A métrica de alucinação é um limite inferior.
- Os resultados valem para os modelos e versões da data da execução.
- Juiz LLM, quando usado, só vale com a concordância humana reportada.
- Comparação entre modelos mede aderência ao formato e à citação tanto quanto "conhecimento".
