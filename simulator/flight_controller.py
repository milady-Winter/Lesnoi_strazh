# =============================================================
# flight_controller.py — Управление FC RDU Baikal через MAVLink
#
# UART2 → /dev/ttyAMA0 @ 57600 бод
#
# Использование:
#   fc = FlightController()
#   fc.connect()
#   fc.arm()
#   fc.takeoff(30)
#   fc.goto(55.7560, 37.6180, 30)
#   fc.land()
#   fc.disarm()
# =============================================================

import time
import logging
import math

from pymavlink import mavutil

import config

logger = logging.getLogger(__name__)


class FlightController:
    def __init__(self):
        self._conn = None
        self._home_lat: float = 0.0
        self._home_lon: float = 0.0

    # ----------------------------------------------------------
    # Подключение
    # ----------------------------------------------------------

    def connect(self) -> bool:
        """Подключиться к FC по UART. Возвращает True если успешно."""
        try:
            logger.info(f"Подключение к FC: {config.FC_PORT} @ {config.BAUD_FC}")
            self._conn = mavutil.mavlink_connection(
                config.FC_PORT,
                baud=config.BAUD_FC
            )
            # Ждём heartbeat — подтверждение связи
            logger.info("Ожидание heartbeat от FC...")
            self._conn.wait_heartbeat(timeout=15)
            logger.info(
                f"FC найден: system={self._conn.target_system} "
                f"component={self._conn.target_component}"
            )

            # Запросить стрим телеметрии
            self._request_data_stream()
            time.sleep(1)

            # Сохранить домашнюю позицию
            pos = self.get_position()
            if pos:
                self._home_lat, self._home_lon = pos
            return True

        except Exception as e:
            logger.error(f"Не удалось подключиться к FC: {e}")
            return False

    def _request_data_stream(self):
        """Запросить телеметрию с FC."""
        self._conn.mav.request_data_stream_send(
            self._conn.target_system,
            self._conn.target_component,
            mavutil.mavlink.MAV_DATA_STREAM_ALL,
            4,   # 4 Гц
            1    # включить
        )

    # ----------------------------------------------------------
    # Базовые команды
    # ----------------------------------------------------------

    def arm(self) -> bool:
        """Разблокировать моторы."""
        logger.info("ARM моторов")
        return self._command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=1  # 1=arm
        )

    def disarm(self) -> bool:
        """Заблокировать моторы."""
        logger.info("DISARM моторов")
        return self._command_long(
            mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM,
            param1=0  # 0=disarm
        )

    def takeoff(self, altitude: float) -> bool:
        """Взлететь до altitude метров (AGL)."""
        logger.info(f"TAKEOFF до {altitude}м")
        # Переключить в режим GUIDED
        self._set_mode("GUIDED")
        time.sleep(0.5)
        return self._command_long(
            mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            param7=altitude
        )

    def land(self) -> bool:
        """Посадка на текущей позиции."""
        logger.info("LAND")
        return self._set_mode("LAND")

    def hover(self):
        """Зависнуть — переключить в LOITER."""
        logger.info("HOVER (LOITER)")
        self._set_mode("LOITER")

    # ----------------------------------------------------------
    # Навигация
    # ----------------------------------------------------------

    def goto(self, lat: float, lon: float, alt: float, groundspeed: float = 5.0) -> bool:
        """Лететь к GPS точке. Ждёт прибытия (±2м)."""
        logger.info(f"GOTO lat={lat} lon={lon} alt={alt}м")
        self._set_mode("GUIDED")

        self._conn.mav.set_position_target_global_int_send(
            0,                          # time_boot_ms
            self._conn.target_system,
            self._conn.target_component,
            mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
            0b0000111111111000,         # маска: только позиция
            int(lat * 1e7),
            int(lon * 1e7),
            alt,
            0, 0, 0,                    # vx, vy, vz
            0, 0, 0,                    # afx, afy, afz
            0, 0                        # yaw, yaw_rate
        )

        # Ждём прибытия
        return self._wait_arrival(lat, lon, alt, tolerance_m=2.0, timeout=120)

    def set_yaw(self, angle_deg: float, relative: bool = False):
        """
        Развернуться на угол (градусы).
        relative=True → угол относительно текущего курса.
        relative=False → абсолютный угол от севера.
        """
        logger.info(f"SET_YAW angle={angle_deg}° relative={relative}")
        self._command_long(
            mavutil.mavlink.MAV_CMD_CONDITION_YAW,
            param1=abs(angle_deg),
            param2=20,  # скорость поворота °/с
            param3=1 if angle_deg >= 0 else -1,
            param4=1 if relative else 0
        )
        time.sleep(2)  # дать время на поворот

    def move_body(self, dx: float, dy: float, dz: float = 0.0):
        """
        Сдвинуться относительно себя на dx, dy, dz метров.
        dx — вперёд/назад, dy — вправо/влево, dz — вверх/вниз (минус = вверх).
        Используется для точной коррекции посадки.
        """
        self._conn.mav.set_position_target_local_ned_send(
            0,  # time_boot_ms
            self._conn.target_system,
            self._conn.target_component,
            mavutil.mavlink.MAV_FRAME_BODY_OFFSET_NED,
            0b0000111111111000,  # маска: только позиция
            dx, dy, dz,
            0, 0, 0,   # скорость
            0, 0, 0,   # ускорение
            0, 0       # yaw, yaw_rate
        )

    # ----------------------------------------------------------
    # Телеметрия
    # ----------------------------------------------------------

    def get_battery(self) -> int:
        """Возвращает процент заряда батареи (0–100). -1 если нет данных."""
        msg = self._conn.recv_match(type="BATTERY_STATUS", blocking=True, timeout=3)
        if msg:
            return msg.battery_remaining  # -1 если неизвестно
        return -1

    def get_position(self) -> tuple[float, float] | None:
        """Возвращает (lat, lon) или None."""
        for _ in range(10):
            msg = self._conn.recv_match(
                type="GLOBAL_POSITION_INT",
                blocking=True,
                timeout=1
            )
            if msg and (msg.lat != 0 or msg.lon != 0):
                return msg.lat / 1e7, msg.lon / 1e7
        return None

    def get_altitude(self) -> float:
        """Возвращает высоту AGL в метрах. 0 если нет данных."""
        msg = self._conn.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=3)
        if msg:
            return msg.relative_alt / 1000.0  # мм → метры
        return 0.0

    # ----------------------------------------------------------
    # Вспомогательные методы
    # ----------------------------------------------------------

    def _set_mode(self, mode_name: str) -> bool:
        mode_id = self._conn.mode_mapping().get(mode_name)
        if mode_id is None:
            logger.error(f"Режим '{mode_name}' не найден в FC")
            return False
        self._conn.mav.set_mode_send(
            self._conn.target_system,
            mavutil.mavlink.MAV_MODE_FLAG_CUSTOM_MODE_ENABLED,
            mode_id
        )
        return True

    def _command_long(self, command, param1=0, param2=0, param3=0,
                      param4=0, param5=0, param6=0, param7=0) -> bool:
        self._conn.mav.command_long_send(
            self._conn.target_system,
            self._conn.target_component,
            command,
            0,  # confirmation
            param1, param2, param3, param4, param5, param6, param7
        )
        # Ждём ACK
        ack = self._conn.recv_match(type="COMMAND_ACK", blocking=True, timeout=5)
        if ack and ack.result == mavutil.mavlink.MAV_RESULT_ACCEPTED:
            return True
        logger.warning(f"Команда {command} не принята: {ack}")
        return False

    def _wait_arrival(self, lat, lon, alt, tolerance_m=2.0, timeout=120) -> bool:
        """Ждать пока дрон не достигнет точки (lat, lon) с погрешностью tolerance_m."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            pos = self.get_position()
            cur_alt = self.get_altitude()
            if pos:
                dist = self._haversine(pos[0], pos[1], lat, lon)
                alt_diff = abs(cur_alt - alt)
                if dist < tolerance_m and alt_diff < 2.0:
                    logger.info(f"Точка достигнута (dist={dist:.1f}м, alt_err={alt_diff:.1f}м)")
                    return True
            time.sleep(0.5)
        logger.warning("Таймаут ожидания прибытия в точку")
        return False

    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2) -> float:
        """Расстояние между двумя GPS точками в метрах."""
        R = 6371000  # радиус Земли в метрах
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
