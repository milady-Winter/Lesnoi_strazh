# Симулятор — Лесной страж

## Требования
1. Установить Mission Planner:
   https://firmware.ardupilot.org/Tools/MissionPlanner/MissionPlanner-latest.msi

2. Установить зависимости:
   pip install -r requirements_sim.txt

## Запуск

### Шаг 1 — Запустить SITL в Mission Planner
   Simulation → MultiRotor → Start
   Дрон должен появиться на карте

### Шаг 2 — Запустить симулятор (Terminal 1)
   python main_sim.py

### Шаг 3 — Симулировать пожар (Terminal 2)
   python fire_simulator.py
   python fire_simulator.py --angle 35 --delay 10

### Шаг 4 — Симулировать посадку (Terminal 3)
   python landing_simulator.py

## Файлы
- config_sim.py       → настройки (FC по UDP вместо UART)
- main_sim.py         → точка входа симулятора
- sensor_simulator.py → заменяет Arduino Nano
- fire_simulator.py   → заменяет Николаса
- landing_simulator.py→ заменяет Машу

## Что тестируется
- Взлёт и маршрут патрулирования
- Обнаружение пожара и расследование
- Возврат на базу при низком заряде
- Точная посадка по ArUco
- Переключение ручной/автономный режим
