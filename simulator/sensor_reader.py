# =============================================================
# sensor_reader.py — Чтение данных с Arduino Nano
#
# Arduino отправляет строку каждые 50мс:
#   "DIST_DOWN:150,DIST_FWD:300,TEMP:25.4,SOUND:512\n"
#
# Сенсоры подключённые к Arduino:
#   VL53L0X  → I2C 0x29 → высота вниз
#   TOF250   → UART     → расстояние вперёд
#   MAX6675  → SPI      → температура °C
#   KY-037   → A1       → звук 0-1023
# =============================================================

import threading
import logging
import time
import serial
import config

logger = logging.getLogger(__name__)


class SensorReader:
    def __init__(self):
        self.dist_down:   int   = 9999   # VL53L0X см
        self.dist_fwd:    int   = 9999   # TOF250 см
        self.temperature: float = 0.0    # MAX6675 °C
        self.sound:       int   = 0      # KY-037 0-1023

        # Флаги тревоги
        self.fire_detected:   bool = False  # темп > FIRE_TEMP_THRESHOLD
        self.person_detected: bool = False  # темп > PERSON_TEMP_THRESHOLD
        self.sound_alert:     bool = False  # звук > SOUND_THRESHOLD

        self._serial:  serial.Serial | None = None
        self._thread:  threading.Thread | None = None
        self._running: bool = False
        self._lock = threading.Lock()

    # ----------------------------------------------------------
    # Публичный интерфейс
    # ----------------------------------------------------------

    def start(self) -> bool:
        try:
            self._serial = serial.Serial(
                port=config.ARDUINO_PORT,
                baudrate=config.BAUD_ARDUINO,
                timeout=1.0
            )
            logger.info(f"Порт Arduino открыт: {config.ARDUINO_PORT}")
        except serial.SerialException as e:
            logger.error(f"Не удалось открыть Arduino: {e}")
            return False

        self._running = True
        self._thread = threading.Thread(
            target=self._read_loop, daemon=True, name="SensorReader"
        )
        self._thread.start()
        return True

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._serial and self._serial.is_open:
            self._serial.close()
        logger.info("SensorReader остановлен")

    # ----------------------------------------------------------
    # Поток чтения
    # ----------------------------------------------------------

    def _read_loop(self):
        logger.info("SensorReader запущен")
        while self._running:
            try:
                if not self._serial or not self._serial.is_open:
                    time.sleep(0.1)
                    continue
                raw = self._serial.readline()
                if raw:
                    self._parse(raw.decode("ascii", errors="ignore").strip())
            except serial.SerialException as e:
                logger.warning(f"Ошибка serial: {e}")
                time.sleep(0.5)
            except Exception as e:
                logger.warning(f"Ошибка SensorReader: {e}")

    def _parse(self, line: str):
        """
        Парсит строку:
          DIST_DOWN:150,DIST_FWD:300,TEMP:25.4,SOUND:512
        """
        try:
            parts = {}
            for token in line.split(","):
                if ":" not in token:
                    continue
                key, val = token.split(":", 1)
                parts[key.strip()] = val.strip()

            with self._lock:
                if "DIST_DOWN" in parts:
                    self.dist_down = int(parts["DIST_DOWN"])
                if "DIST_FWD" in parts:
                    self.dist_fwd = int(parts["DIST_FWD"])
                if "TEMP" in parts:
                    self.temperature = float(parts["TEMP"])
                    self.fire_detected   = self.temperature > config.FIRE_TEMP_THRESHOLD
                    self.person_detected = (
                        config.PERSON_TEMP_THRESHOLD < self.temperature <= config.FIRE_TEMP_THRESHOLD
                    )
                if "SOUND" in parts:
                    self.sound = int(parts["SOUND"])
                    self.sound_alert = self.sound > config.SOUND_THRESHOLD

        except (ValueError, KeyError) as e:
            logger.debug(f"Ошибка парсинга '{line}': {e}")

    def __str__(self):
        return (
            f"DOWN={self.dist_down}cm FWD={self.dist_fwd}cm "
            f"TEMP={self.temperature:.1f}°C SOUND={self.sound} "
            f"FIRE={self.fire_detected} PERSON={self.person_detected} "
            f"SOUND_ALERT={self.sound_alert}"
        )
