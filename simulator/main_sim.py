# =============================================================
# main_sim.py — Punto de entrada para simulación SITL
# Igual que main.py pero usa:
#   - config_sim.py  (FC por UDP)
#   - SensorSimulator (sin Arduino físico)
# =============================================================

import json
import socket
import logging
import threading
import sys
import time

# Usar config del simulador
import config_sim as config

# Importar módulos del dron (desde carpeta padre)
sys.path.insert(0, "..")
from sensor_simulator import SensorSimulator
from flight_controller import FlightController
from mission import Mission

# ----------------------------------------------------------
# Logging
# ----------------------------------------------------------
import sys, io
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(
            io.TextIOWrapper(
                sys.stdout.buffer,
                encoding="utf-8",
                errors="replace"
            )
        ),
        logging.FileHandler("sim.log", encoding="utf-8"),
    ]
)
logger = logging.getLogger("main_sim")


# ----------------------------------------------------------
# Sockets — igual que main.py
# ----------------------------------------------------------

def listen_fire_socket(mission: Mission, stop_event: threading.Event):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", config.FIRE_SOCKET_PORT))
        sock.settimeout(1.0)
        logger.info(f"🔥 Escuchando fire_simulator en puerto {config.FIRE_SOCKET_PORT}")
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(1024)
                payload = json.loads(data.decode("utf-8"))
                mission.update_fire_detection(payload)
                logger.info(f"🔥 Fuego recibido: {payload}")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error socket fuego: {e}")


def listen_landing_socket(mission: Mission, stop_event: threading.Event):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("0.0.0.0", config.LANDING_SOCKET_PORT))
        sock.settimeout(1.0)
        logger.info(f"📡 Escuchando landing_simulator en puerto {config.LANDING_SOCKET_PORT}")
        while not stop_event.is_set():
            try:
                data, addr = sock.recvfrom(1024)
                payload = json.loads(data.decode("utf-8"))
                mission.update_landing_correction(payload)
                logger.debug(f"📡 Landing: {payload}")
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Error socket landing: {e}")


# ----------------------------------------------------------
# Main
# ----------------------------------------------------------

def main():
    logger.info("=" * 55)
    logger.info("  ЛЕСНОЙ СТРАЖ — Modo Simulador SITL")
    logger.info("  Conectando a Mission Planner en udp:127.0.0.1:14550")
    logger.info("=" * 55)

    stop_event = threading.Event()

    # 1. Sensores simulados
    sensors = SensorSimulator()
    if not sensors.start():
        logger.error("No se pudo iniciar SensorSimulator")
        sys.exit(1)
    logger.info("✅ SensorSimulator iniciado")
    time.sleep(0.5)

    # 2. FC — conectar al SITL
    fc = FlightController()
    if not fc.connect():
        logger.error(
            "❌ No se pudo conectar al FC simulado.\n"
            "   Asegúrate de que Mission Planner SITL esté corriendo.\n"
            "   Simulation → MultiRotor → Start"
        )
        sensors.stop()
        sys.exit(1)
    logger.info("✅ FlightController conectado al SITL")

    # 3. Misión
    mission = Mission(fc=fc, sensors=sensors)

    # 4. Sockets externos
    fire_thread = threading.Thread(
        target=listen_fire_socket,
        args=(mission, stop_event),
        daemon=True, name="FireSocket"
    )
    landing_thread = threading.Thread(
        target=listen_landing_socket,
        args=(mission, stop_event),
        daemon=True, name="LandingSocket"
    )
    fire_thread.start()
    landing_thread.start()
    logger.info("✅ Sockets iniciados (puertos 5005 y 5006)")

    # 5. Misión en hilo separado
    mission_thread = threading.Thread(
        target=mission.start,
        daemon=False, name="Mission"
    )
    mission_thread.start()
    logger.info("✅ Misión iniciada\n")
    logger.info("  Ctrl+C → parada segura")
    logger.info("  Corre fire_simulator.py en otra terminal para simular fuego")
    logger.info("  Corre landing_simulator.py para simular aterrizaje\n")

    # 6. Esperar Ctrl+C
    try:
        while mission_thread.is_alive():
            mission_thread.join(timeout=1)
    except KeyboardInterrupt:
        logger.warning("Ctrl+C — parando simulación...")
        mission.stop()
        stop_event.set()

    mission_thread.join(timeout=10)
    sensors.stop()
    logger.info("Simulación terminada.")


if __name__ == "__main__":
    main()
