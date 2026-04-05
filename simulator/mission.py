# =============================================================
# mission.py — Главная логика полёта (конечный автомат)
# Состояния: IDLE→TAKEOFF→PATROL→INVESTIGATE→RETURN→LANDING
# =============================================================

import time
import json
import socket
import sqlite3
import logging
import threading
import requests
from enum import Enum, auto
from dataclasses import dataclass

import config
from sensor_reader import SensorReader
from flight_controller import FlightController

logger = logging.getLogger(__name__)


class State(Enum):
    IDLE        = auto()
    TAKEOFF     = auto()
    PATROL      = auto()
    INVESTIGATE = auto()
    RETURN      = auto()
    LANDING     = auto()
    EMERGENCY   = auto()


@dataclass
class FireDetection:
    detected:   bool  = False
    angle:      float = 0.0
    confidence: float = 0.0


@dataclass
class LandingCorrection:
    dx:     float = 0.0
    dy:     float = 0.0
    angle:  float = 0.0
    status: str   = "NO_MARKER"


class Mission:
    def __init__(self, fc: FlightController, sensors: SensorReader):
        self.fc      = fc
        self.sensors = sensors
        self.state   = State.IDLE

        self._fire    = FireDetection()
        self._landing = LandingCorrection()
        self._fire_lock    = threading.Lock()
        self._landing_lock = threading.Lock()

        self._waypoint_idx = 0
        self._running      = False
        self._init_db()

    # ----------------------------------------------------------
    # Запуск / остановка
    # ----------------------------------------------------------

    def start(self):
        self._running = True
        self._run_state_machine()

    def stop(self):
        self._running = False
        logger.warning("Миссия остановлена оператором")

    # ----------------------------------------------------------
    # Конечный автомат
    # ----------------------------------------------------------

    def _run_state_machine(self):
        logger.info("Миссия запущена")
        while self._running:
            try:
                if   self.state == State.IDLE:        self._state_idle()
                elif self.state == State.TAKEOFF:     self._state_takeoff()
                elif self.state == State.PATROL:      self._state_patrol()
                elif self.state == State.INVESTIGATE: self._state_investigate()
                elif self.state == State.RETURN:      self._state_return()
                elif self.state == State.LANDING:     self._state_landing()
                elif self.state == State.EMERGENCY:   self._state_emergency()
            except Exception as e:
                logger.error(f"Ошибка в {self.state}: {e}", exc_info=True)
                self._transition(State.EMERGENCY)

    def _transition(self, new_state: State):
        logger.info(f"Переход: {self.state.name} → {new_state.name}")
        self.state = new_state

    # ----------------------------------------------------------
    # IDLE
    # ----------------------------------------------------------

    def _state_idle(self):
        logger.info("IDLE: Проверка систем...")
        pos = self.fc.get_position()
        if pos is None:
            logger.error("IDLE: Нет GPS. Ожидание...")
            time.sleep(5)
            return
        logger.info(f"IDLE: GPS OK {pos}. Старт через 3с...")
        time.sleep(3)
        self._transition(State.TAKEOFF)

    # ----------------------------------------------------------
    # TAKEOFF
    # ----------------------------------------------------------

    def _state_takeoff(self):
        logger.info(f"TAKEOFF: Взлёт до {config.CRUISE_ALTITUDE}м")
        if not self.fc.arm():
            logger.error("TAKEOFF: ARM не удался")
            time.sleep(5)
            return
        time.sleep(1)
        if not self.fc.takeoff(config.CRUISE_ALTITUDE):
            self._transition(State.EMERGENCY)
            return
        deadline = time.time() + 60
        while time.time() < deadline:
            alt = self.fc.get_altitude()
            if alt >= config.CRUISE_ALTITUDE - 2:
                logger.info("TAKEOFF: Высота достигнута")
                self._transition(State.PATROL)
                return
            time.sleep(1)
        self._transition(State.EMERGENCY)

    # ----------------------------------------------------------
    # PATROL
    # ----------------------------------------------------------

    def _state_patrol(self):
        route = config.PATROL_ROUTE
        if not route:
            self._transition(State.RETURN)
            return

        wp = route[self._waypoint_idx % len(route)]
        logger.info(f"PATROL: Точка {self._waypoint_idx + 1}/{len(route)}")

        # Проверка батареи
        batt = self.fc.get_battery()
        if 0 <= batt < config.BATTERY_RETURN:
            logger.warning("PATROL: Низкий заряд! Возврат.")
            self._transition(State.RETURN)
            return

        self.fc.goto(wp["lat"], wp["lon"], wp["alt"])
        self.fc.hover()

        deadline = time.time() + config.WAYPOINT_HOVER_SEC
        while time.time() < deadline:
            # Перехват ручного управления
            current_mode = self.fc.get_mode()
            if current_mode == config.MANUAL_MODE:
                logger.info("PATROL: Пилот взял управление — пауза")
                self._wait_for_auto_mode()
                continue

            # Детектор огня (Николас)
            with self._fire_lock:
                fire = FireDetection(**vars(self._fire))
            if fire.detected and fire.confidence >= 0.7:
                logger.warning(f"PATROL: ИИ обнаружил огонь! Угол={fire.angle}°")
                self._transition(State.INVESTIGATE)
                return

            # Термопара MAX6675
            if self.sensors.fire_detected:
                logger.warning(f"PATROL: Термопара! TEMP={self.sensors.temperature:.1f}°C")
                self._transition(State.INVESTIGATE)
                return

            # Микрофон KY-037
            if self.sensors.sound_alert:
                logger.info(f"PATROL: Звуковой сигнал! SOUND={self.sensors.sound}")
                # Не переходим сразу — просто логируем, ждём подтверждение от ИИ

            # Препятствие TOF250
            if self.sensors.dist_fwd < config.OBSTACLE_DISTANCE_CM:
                logger.warning(f"PATROL: Препятствие {self.sensors.dist_fwd}см! Подъём.")
                pos = self.fc.get_position()
                if pos:
                    self.fc.goto(pos[0], pos[1], self.fc.get_altitude() + 5)

            time.sleep(0.2)

        self._waypoint_idx += 1

    # ----------------------------------------------------------
    # INVESTIGATE
    # ----------------------------------------------------------

    def _state_investigate(self):
        logger.info("INVESTIGATE: Расследование")

        with self._fire_lock:
            fire_angle = self._fire.angle

        if abs(fire_angle) > 5:
            logger.info(f"INVESTIGATE: Разворот на {fire_angle}°")
            self.fc.set_yaw(fire_angle, relative=True)

        pos = self.fc.get_position()
        if pos:
            self.fc.goto(pos[0], pos[1], config.CONFIRM_ALTITUDE)

        self.fc.hover()
        fire_confirmed   = False
        person_detected  = False
        deadline = time.time() + config.INVESTIGATE_HOVER_SEC

        while time.time() < deadline:
            # Подтверждение термопарой
            if self.sensors.fire_detected:
                logger.info(f"INVESTIGATE: Пожар подтверждён! TEMP={self.sensors.temperature:.1f}°C")
                fire_confirmed = True
                break
            # Обнаружение человека
            if self.sensors.person_detected:
                logger.info(f"INVESTIGATE: Человек! TEMP={self.sensors.temperature:.1f}°C")
                person_detected = True
            # Звук — крик человека
            if self.sensors.sound_alert:
                logger.info(f"INVESTIGATE: Звук! SOUND={self.sensors.sound}")
                person_detected = True
            time.sleep(0.3)

        gps = self.fc.get_position()
        if fire_confirmed and gps:
            self._save_event_to_db("fire", gps[0], gps[1], self.sensors.temperature)
            self._send_telegram_alert("fire", gps[0], gps[1])
        elif person_detected and gps:
            self._save_event_to_db("person", gps[0], gps[1], self.sensors.temperature)
            self._send_telegram_alert("person", gps[0], gps[1])
        else:
            logger.info("INVESTIGATE: Ложная тревога")

        # Подняться обратно
        pos = self.fc.get_position()
        if pos:
            self.fc.goto(pos[0], pos[1], config.CRUISE_ALTITUDE)

        with self._fire_lock:
            self._fire = FireDetection()

        self._transition(State.PATROL)

    # ----------------------------------------------------------
    # RETURN
    # ----------------------------------------------------------

    def _state_return(self):
        logger.info("RETURN: Ищу ближайшую базу...")
        pos = self.fc.get_position()
        if not pos or not config.CHARGING_BASES:
            self._transition(State.EMERGENCY)
            return

        base = min(
            config.CHARGING_BASES,
            key=lambda b: FlightController._haversine(pos[0], pos[1], b["lat"], b["lon"])
        )
        self.fc.goto(base["lat"], base["lon"], config.CRUISE_ALTITUDE)
        self.fc.goto(base["lat"], base["lon"], 5)
        self.fc.hover()
        self._transition(State.LANDING)

    # ----------------------------------------------------------
    # LANDING — точная посадка по ArUco (Маша)
    # ----------------------------------------------------------

    def _state_landing(self):
        logger.info("LANDING: Активация точной посадки ArUco")
        no_marker_start = None

        while True:
            with self._landing_lock:
                corr = LandingCorrection(**vars(self._landing))

            if corr.status == "NO_MARKER":
                if no_marker_start is None:
                    no_marker_start = time.time()
                    logger.warning("LANDING: Маркер не найден...")
                elif time.time() - no_marker_start > config.NO_MARKER_TIMEOUT_SEC:
                    logger.warning("LANDING: Маркер потерян. Подъём и повтор.")
                    alt = self.fc.get_altitude()
                    pos = self.fc.get_position()
                    if pos:
                        self.fc.goto(pos[0], pos[1], alt + config.LANDING_REARM_ALTITUDE)
                    no_marker_start = None
                time.sleep(0.1)
                continue

            no_marker_start = None

            if corr.status == "LAND":
                logger.info("LANDING: Маша говорит LAND!")
                self.fc.land()
                time.sleep(5)
                self.fc.disarm()
                logger.info("LANDING: Посадка завершена")
                self._transition(State.IDLE)
                return

            dx_m = -corr.dx * config.LANDING_PIXEL_TO_METER
            dy_m = -corr.dy * config.LANDING_PIXEL_TO_METER
            logger.debug(f"LANDING: dx={dx_m:.3f}м dy={dy_m:.3f}м")
            self.fc.move_body(dx_m, dy_m)
            time.sleep(0.1)

    # ----------------------------------------------------------
    # EMERGENCY
    # ----------------------------------------------------------

    def _state_emergency(self):
        logger.error("EMERGENCY: Аварийная посадка!")
        self.fc.land()
        time.sleep(5)
        self.fc.disarm()
        self._running = False

    # ----------------------------------------------------------
    # Ожидание ручного режима
    # ----------------------------------------------------------

    def _wait_for_auto_mode(self):
        logger.info("Ожидание возврата AUTO режима от пилота...")
        while self._running:
            mode = self.fc.get_mode()
            if mode == config.AUTO_MODE:
                logger.info("AUTO режим восстановлен — продолжаем миссию")
                return
            time.sleep(0.5)

    # ----------------------------------------------------------
    # Внешние данные
    # ----------------------------------------------------------

    def update_fire_detection(self, data: dict):
        with self._fire_lock:
            self._fire.detected   = data.get("fire", False)
            self._fire.angle      = data.get("angle", 0.0)
            self._fire.confidence = data.get("confidence", 0.0)

    def update_landing_correction(self, data: dict):
        with self._landing_lock:
            self._landing.dx     = data.get("dx", 0.0)
            self._landing.dy     = data.get("dy", 0.0)
            self._landing.angle  = data.get("angle", 0.0)
            self._landing.status = data.get("status", "NO_MARKER")

    # ----------------------------------------------------------
    # БД и Telegram
    # ----------------------------------------------------------

    def _init_db(self):
        import os
        db_dir = os.path.dirname(config.DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        with sqlite3.connect(config.DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT DEFAULT (datetime('now')),
                    type      TEXT,
                    lat       REAL,
                    lon       REAL,
                    temp      REAL
                )
            """)
        logger.info(f"DB: {config.DB_PATH}")

    def _save_event_to_db(self, event_type: str, lat: float, lon: float, temp: float):
        try:
            with sqlite3.connect(config.DB_PATH) as conn:
                conn.execute(
                    "INSERT INTO events (type,lat,lon,temp) VALUES (?,?,?,?)",
                    (event_type, lat, lon, temp)
                )
            logger.info(f"БД: {event_type} lat={lat} lon={lon} temp={temp}°C")
        except Exception as e:
            logger.error(f"Ошибка БД: {e}")

    def _send_telegram_alert(self, event_type: str, lat: float, lon: float):
        if not config.TELEGRAM_BOT_TOKEN or "YOUR" in config.TELEGRAM_BOT_TOKEN:
            return
        icons = {"fire": "🔥", "person": "🧭"}
        names = {"fire": "ПОЖАР ОБНАРУЖЕН", "person": "ЧЕЛОВЕК ОБНАРУЖЕН"}
        try:
            url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
            msg = (
                f"{icons.get(event_type,'⚠️')} {names.get(event_type,'ТРЕВОГА')}\n"
                f"Координаты: {lat:.6f}, {lon:.6f}\n"
                f"https://maps.google.com/?q={lat},{lon}"
            )
            requests.post(url, json={"chat_id": config.TELEGRAM_CHAT_ID, "text": msg}, timeout=5)
            logger.info("Telegram алерт отправлен")
        except Exception as e:
            logger.error(f"Telegram ошибка: {e}")
