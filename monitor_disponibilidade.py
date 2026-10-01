"""
Monitor de disponibilidade/latencia do bot em producao (OE4), independente do
Railway -- usa uma conta real do Telegram (via Telethon, mesma credencial da
coleta em 01-dataset/) pra mandar uma mensagem de teste pro bot e medir se e
quanto tempo ele demora pra responder. Cada execucao gera uma linha no log.

Rodar isso periodicamente (a cada ~15 min) durante os 30 dias de validacao
serve dois propositos ao mesmo tempo:
1. Gera as >=100 requisicoes reais exigidas pro criterio de latencia do OE4.
2. Cada tentativa sem resposta dentro do timeout conta como indisponibilidade
   -- da pra calcular a % de disponibilidade no fim dos 30 dias.

Uso local:
    python monitor_disponibilidade.py
    (le TELEGRAM_API_ID/API_HASH/SESSION_NAME de ../01-dataset/.env -- usa a sessao salva em arquivo)

Uso no GitHub Actions (repo monitor-bot-tcc, sem a pasta 01-dataset/ por perto):
    define TELEGRAM_API_ID / TELEGRAM_API_HASH / TELEGRAM_SESSION_STRING como Secrets --
    esse script detecta TELEGRAM_SESSION_STRING e usa StringSession em vez de arquivo.
"""

import asyncio
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(ENV_PATH)  # nao-op se o arquivo nao existir (ex.: rodando no GitHub Actions)

API_ID = int(os.environ["TELEGRAM_API_ID"])
API_HASH = os.environ["TELEGRAM_API_HASH"]

_SESSION_STRING = os.environ.get("TELEGRAM_SESSION_STRING")
if _SESSION_STRING:
    SESSAO = StringSession(_SESSION_STRING)
else:
    SESSAO = str(Path(__file__).parent / os.environ.get("TELEGRAM_SESSION_NAME", "monitor"))

BOT_USERNAME = "golpesdetector_bot"
TIMEOUT_SEGUNDOS = 40
LOG_PATH = Path(__file__).parent / "disponibilidade_log.csv"

# Validacao de 30 dias: 2026-09-25 a ~2026-10-25. O monitor para de logar
# (sem erro) depois dessa data, pra nao continuar rodando indefinidamente
# caso o agendamento automatico (GitHub Actions) nao seja desativado a tempo.
DATA_FIM_VALIDACAO = datetime(2026, 10, 26, tzinfo=timezone.utc)


async def checar_uma_vez() -> dict:
    """Usa client.conversation() (orientado a evento) em vez de ficar perguntando
    'chegou? chegou?' uma vez por segundo -- a versao anterior (polling manual com
    get_messages a cada 1s, ate 40x por checagem) provavelmente estava esbarrando
    em limitacao de taxa do Telegram pra contas de usuario comum, causando falsos
    negativos de indisponibilidade (confirmado: o bot NUNCA reiniciou no Railway
    durante o periodo em que essas falhas apareceram no log)."""
    client = TelegramClient(SESSAO, API_ID, API_HASH)
    await client.start()

    bot = await client.get_entity(BOT_USERNAME)
    agora = datetime.now(timezone.utc)
    texto_teste = f"[monitor] teste automatico {agora.isoformat()}"

    sucesso = False
    tempo_resposta = None
    erro = ""
    try:
        inicio = time.perf_counter()
        async with client.conversation(bot, timeout=TIMEOUT_SEGUNDOS) as conv:
            await conv.send_message(texto_teste)
            await conv.get_response()
        sucesso = True
        tempo_resposta = round(time.perf_counter() - inicio, 3)
    except asyncio.TimeoutError:
        pass  # sem resposta dentro do timeout -- conta como indisponibilidade real
    except FloodWaitError as e:
        erro = f"FloodWaitError: aguardar {e.seconds}s"

    await client.disconnect()
    return {
        "timestamp_utc": agora.isoformat(),
        "sucesso": sucesso,
        "tempo_resposta_segundos": tempo_resposta if tempo_resposta is not None else "",
        "erro": erro,  # so pra log/diagnostico no console -- nao vai pro CSV, mantem o schema estavel
    }


def registrar(resultado: dict) -> None:
    novo_arquivo = not LOG_PATH.exists()
    campos = ["timestamp_utc", "sucesso", "tempo_resposta_segundos"]
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        if novo_arquivo:
            escritor.writeheader()
        escritor.writerow(resultado)


def main() -> None:
    agora = datetime.now(timezone.utc)
    if agora > DATA_FIM_VALIDACAO:
        print(f"Fora da janela de validacao (terminou em {DATA_FIM_VALIDACAO.date()}) -- nao registrando.")
        return

    resultado = asyncio.run(checar_uma_vez())
    registrar(resultado)

    if resultado["sucesso"]:
        print(f"OK -- respondeu em {resultado['tempo_resposta_segundos']}s")
    elif resultado["erro"]:
        print(f"FALHA (erro do lado do monitor, nao necessariamente do bot): {resultado['erro']}")
    else:
        print(f"FALHA -- sem resposta em {TIMEOUT_SEGUNDOS}s (timestamp: {resultado['timestamp_utc']})")


if __name__ == "__main__":
    main()
