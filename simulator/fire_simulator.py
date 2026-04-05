# =============================================================
# fire_simulator.py — Simula código de Nicolás
# Envía detección de fuego a main_sim.py por UDP
#
# Uso:
#   python fire_simulator.py
#   python fire_simulator.py --angle 35 --delay 15
# =============================================================

import socket
import json
import time
import argparse
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIM-FIRE] %(message)s"
)
logger = logging.getLogger(__name__)

FIRE_PORT = 5006


def send_fire(sock, angle: float, confidence: float):
    payload = {
        "fire":       True,
        "angle":      round(angle, 1),
        "confidence": round(confidence, 2),
    }
    data = json.dumps(payload).encode("utf-8")
    sock.sendto(data, ("127.0.0.1", FIRE_PORT))
    logger.info(f"🔥 Enviado → {payload}")


def send_clear(sock):
    payload = {"fire": False, "angle": 0.0, "confidence": 0.0}
    sock.sendto(json.dumps(payload).encode(), ("127.0.0.1", FIRE_PORT))
    logger.info("✅ Sin fuego enviado")


def main():
    parser = argparse.ArgumentParser(description="Simulador de detección de fuego")
    parser.add_argument("--angle",      type=float, default=25.0,
                        help="Ángulo del fuego en grados (default: 25)")
    parser.add_argument("--confidence", type=float, default=0.92,
                        help="Confianza del modelo 0-1 (default: 0.92)")
    parser.add_argument("--delay",      type=int,   default=20,
                        help="Segundos antes de enviar fuego (default: 20)")
    parser.add_argument("--repeat",     type=int,   default=6,
                        help="Cuántas veces repetir la señal (default: 6)")
    args = parser.parse_args()

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    logger.info(f"Simulador iniciado — enviará fuego en {args.delay}s")
    logger.info(f"Ángulo={args.angle}°  Confianza={args.confidence}")
    logger.info("Presiona Ctrl+C para cancelar\n")

    # Esperar antes de simular
    for remaining in range(args.delay, 0, -1):
        print(f"\r  Fuego en {remaining:2d}s...", end="", flush=True)
        time.sleep(1)
    print()

    # Enviar señal de fuego varias veces
    for i in range(args.repeat):
        send_fire(sock, args.angle, args.confidence)
        time.sleep(1.0)

    # Señal de fin
    send_clear(sock)
    logger.info("Simulación de fuego terminada")
    sock.close()


if __name__ == "__main__":
    main()
