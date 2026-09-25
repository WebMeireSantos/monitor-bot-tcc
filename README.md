# monitor-bot-tcc

Monitoramento independente de disponibilidade e latência do bot @golpesdetector_bot
(TCC — Detecção de Golpes Digitais no Telegram, OE4).

Roda a cada 15 minutos via GitHub Actions (`.github/workflows/monitor.yml`), manda uma
mensagem de teste pro bot via Telethon, mede o tempo de resposta, e registra o resultado
em `disponibilidade_log.csv`.

Serve pra dois critérios de aceitação do OE4 ao mesmo tempo:
- **Latência**: coluna `tempo_resposta_segundos` de cada linha com `sucesso=True`.
- **Disponibilidade**: `% de linhas com sucesso=True` sobre o total no período de 30 dias
  (2026-09-25 a 2026-10-25).

Repositório privado, separado do dataset público — este conteúdo é instrumentação
interna, não um entregável de dataset.
