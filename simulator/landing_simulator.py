# =============================================================
# landing_simulator.py — Simula código de Маша (ArUco posadka)
# Envía correcciones de posición a main_sim.py por UDP
#
# Uso:
#   python landing_simulator.py
# =============================================================

import socket
import json
import time
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [SIM-LAND] %(message)s"
)
logger = logging.getLogger(__name__)

LANDING_PORT = 5005


def send(sock, dx, dy, angle, status):
    payload = {
        "dx":     round(dx, 1),
        "dy":     round(dy, 1),
        "angle":  round(angle, 1),
        "status": status,
    }
    sock.sendto(json.dumps(payload).encode(), ("127.0.0.1", LANDING_PORT))
    logger.info(f"📡 {payload}")


def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    logger.info("Landing simulator iniciado")
    logger.info("Envía correcciones ArUco a puerto 5005\n")

    print("Opciones:")
    print("  1 — Simular aterrizaje automático (dron se centra solo)")
    print("  2 — Control manual (tú introduces dx dy)")
    print("  3 — Simular marcador perdido y recuperado")
    opcion = input("\nElige opción [1/2/3]: ").strip()

    # ----------------------------------------------------------
    # Opción 1: Aterrizaje automático simulado
    # ----------------------------------------------------------
    if opcion == "1":
        logger.info("Simulando aterrizaje automático...")
        input("Presiona Enter cuando el dron esté en estado LANDING...")

        dx, dy = 90.0, 70.0
        angle = 15.0
        step = 0

        while True:
            step += 1

            # Reducir error gradualmente (simula corrección)
            dx    *= 0.80
            dy    *= 0.80
            angle *= 0.85

            if abs(dx) < 10 and abs(dy) < 10:
                # Centrado — dar LAND
                for _ in range(5):
                    send(sock, dx, dy, angle, "LAND")
                    time.sleep(0.1)
                logger.info("✅ LAND enviado — aterrizaje completado")
                break
            else:
                send(sock, dx, dy, angle, "ADJUSTING")

            time.sleep(0.1)  # 10 Hz

    # ----------------------------------------------------------
    # Opción 2: Control manual
    # ----------------------------------------------------------
    elif opcion == "2":
        logger.info("Control manual — introduce valores")
        logger.info("Formato: dx dy  (ejemplo: 30 -15)")
        logger.info("Escribe 'land' para aterrizar, 'q' para salir\n")

        while True:
            try:
                line = input("dx dy > ").strip().lower()
                if line == "q":
                    break
                if line == "land":
                    send(sock, 0, 0, 0, "LAND")
                    logger.info("✅ LAND enviado")
                    break
                if line == "none":
                    send(sock, 0, 0, 0, "NO_MARKER")
                    continue

                parts = line.split()
                dx = float(parts[0])
                dy = float(parts[1])
                send(sock, dx, dy, 0.0, "ADJUSTING")

            except (ValueError, IndexError):
                print("  Formato incorrecto. Usa: dx dy  o  land  o  none")
            except KeyboardInterrupt:
                break

    # ----------------------------------------------------------
    # Opción 3: Marcador perdido y recuperado
    # ----------------------------------------------------------
    elif opcion == "3":
        logger.info("Simulando pérdida y recuperación de marcador...")
        input("Presiona Enter para iniciar...")

        # 5 segundos sin marcador
        logger.info("📵 Marcador perdido por 5s...")
        for _ in range(50):
            send(sock, 0, 0, 0, "NO_MARKER")
            time.sleep(0.1)

        # Marcador recuperado — aterrizaje normal
        logger.info("📡 Marcador recuperado — centrando...")
        dx, dy = 60.0, 40.0
        while abs(dx) > 10 or abs(dy) > 10:
            dx *= 0.80
            dy *= 0.80
            send(sock, dx, dy, 5.0, "ADJUSTING")
            time.sleep(0.1)

        for _ in range(5):
            send(sock, 0, 0, 0, "LAND")
            time.sleep(0.1)
        logger.info("✅ LAND enviado")

    sock.close()
    logger.info("Simulador de posadka terminado")


if __name__ == "__main__":
    main()
