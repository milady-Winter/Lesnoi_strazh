# =============================================================
# sensor_simulator.py — Simula Arduino Nano con nuevos sensores
# VL53L0X (abajo) + TOF250 (adelante) + MAX6675 + KY-037
# Misma interfaz que SensorReader real
# =============================================================

import threading
import time
import random
import logging

logger = logging.getLogger(__name__)


class SensorSimulator:
    def __init__(self):
        # VL53L0X вниз
        self.dist_down:  int   = 300
        # TOF250 вперёд
        self.dist_fwd:   int   = 9999
        # MAX6675 термопара
        self.temperature: float = 18.0
        # KY-037 микрофон
        self.sound:      int   = 150

        # Флаги тревоги
        self.fire_detected:   bool = False
        self.person_detected: bool = False
        self.sound_alert:     bool = False

        self._thread:  threading.Thread | None = None
        self._running: bool = False
        self._tick:    int  = 0

    def start(self) -> bool:
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="SensorSim"
        )
        self._thread.start()
        logger.info("[SIM] SensorSimulator iniciado — VL53L0X+TOF250+MAX6675+KY037")
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        logger.info("[SIM] SensorSimulator detenido")

    def _loop(self):
        while self._running:
            self._tick += 1
            self._update()
            time.sleep(0.05)

    def _update(self):
        import config_sim as config

        # -- TOF250: препятствие на 30s --
        if 600 <= self._tick <= 660:
            self.dist_fwd = 150
            if self._tick == 600:
                logger.warning("[SIM] Препятствие TOF250: 1.5м вперёд")
        else:
            self.dist_fwd = 9999

        # -- MAX6675: пожар на 60s (temp резко растёт) --
        if 1200 <= self._tick <= 1350:
            self.temperature = 95.0 + random.uniform(-2, 2)
            self.fire_detected   = True
            self.person_detected = False
            if self._tick == 1200:
                logger.warning("[SIM] ПОЖАР: температура 95°C!")
        # -- Человек на 90s --
        elif 1800 <= self._tick <= 1900:
            self.temperature = 34.0 + random.uniform(-1, 1)
            self.fire_detected   = False
            self.person_detected = True
            if self._tick == 1800:
                logger.warning("[SIM] ЧЕЛОВЕК: температура 34°C")
        else:
            self.temperature     = 18.0 + random.uniform(-1, 1)
            self.fire_detected   = False
            self.person_detected = False

        # -- KY-037: крик на 90s --
        if 1800 <= self._tick <= 1900:
            self.sound       = 820 + random.randint(-20, 20)
            self.sound_alert = True
            if self._tick == 1800:
                logger.warning("[SIM] ЗВУК: крик! 820")
        else:
            self.sound       = 150 + random.randint(-20, 20)
            self.sound_alert = False

        # -- VL53L0X вниз — шум --
        self.dist_down = 300 + random.randint(-5, 5)

    def __str__(self):
        return (
            f"DOWN={self.dist_down}cm FWD={self.dist_fwd}cm "
            f"TEMP={self.temperature:.1f}°C SOUND={self.sound} "
            f"FIRE={self.fire_detected} PERSON={self.person_detected}"
        )
