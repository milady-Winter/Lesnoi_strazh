# =============================================================
# config_sim.py — Конфигурация симулятора SITL
# SpeedyBee F405 V3 | Mission Planner SITL
# =============================================================

# FC виртуальный — TCP Mission Planner
FC_PORT = "tcp:127.0.0.1:5760"
BAUD_FC = 115200

# Маршрут — Сибирь
PATROL_ROUTE = [
    {"lat": 56.0184, "lon": 92.8672, "alt": 10},
    {"lat": 56.0190, "lon": 92.8680, "alt": 10},
    {"lat": 56.0196, "lon": 92.8672, "alt": 10},
]
CHARGING_BASES = [
    {"lat": 56.0180, "lon": 92.8665, "aruco_id": 0},
]

# Сенсоры — те же пороги
OBSTACLE_DISTANCE_CM   = 200
MIN_ALTITUDE_CM        = 50
FIRE_TEMP_THRESHOLD    = 80
PERSON_TEMP_THRESHOLD  = 30
AMBIENT_TEMP_EXPECTED  = 15
SOUND_THRESHOLD        = 700

# Полёт — меньше высота для симулятора
CRUISE_ALTITUDE        = 10
CONFIRM_ALTITUDE       = 5
BATTERY_RETURN         = 20
WAYPOINT_HOVER_SEC     = 3
INVESTIGATE_HOVER_SEC  = 5
NO_MARKER_TIMEOUT_SEC  = 10
LANDING_PIXEL_TO_METER = 0.005
LANDING_REARM_ALTITUDE = 2

# Порты (не используются в симуляторе)
ARDUINO_PORT = "COM3"
BAUD_ARDUINO = 115200

# Сокеты
LANDING_SOCKET_PORT = 5005
FIRE_SOCKET_PORT    = 5006

# Telegram — пусто в симуляторе
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_CHAT_ID   = ""

# БД
DB_PATH = "sim_fires.db"

# Режимы
MANUAL_MODE = "STABILIZE"
AUTO_MODE   = "GUIDED"
