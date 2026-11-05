"""Shared rig names and physical rates."""
from math import radians

AXES = {"X": 0, "Y": 1, "Z": 2}
ROTATION_ORDERS = {"X": "XYZ", "Y": "YXZ", "Z": "ZXY"}
MOVEMENT_PRESETS = (
    ('QUARTZ', 'Tick once a second', 'Quartz motion, one step per second'),
    ('MECH6', 'Mechanical: 6 steps', 'Six steps per second'),
    ('MECH8', 'Mechanical: 8 steps', 'Eight steps per second'),
    ('SWEEP', 'Smooth sweep', 'Continuous movement without ticks'),
)
FACTORS = {"second": 1.0, "minute": 1.0 / 60.0, "hour": 1.0 / 720.0}
RATES = {name: radians(6) * factor for name, factor in FACTORS.items()}
START_H = "start_h"
START_M = "start_m"
START_S = "start_s"
SPEED = "speed"
TICK = "tick"
OFFSET = "offset"
TIME = "time"
CROWN_SOURCE = "_clock_crown_source"
CROWN_AXIS = "_clock_crown_axis"
CROWN_REST = "_clock_crown_zero"
CROWN_RATIO = "crown_ratio"
CROWN_SECONDS_PER_RADIAN = 1.0 / RATES['second']
REST = "_clock_rest"
REST_MODE = "_clock_rest_mode"
REST_ROTATION = "_clock_rest_rotation"
REST_DELTA = "_clock_rest_delta"
REST_DELTA_QUAT = "_clock_rest_delta_quat"
CONTROLLER = "_clock_controller"
PLAYBACK_BASE = "_clock_playback_base"
CONFIG_AUTO = "_clock_config_auto"
OWNER = "_clock_owner"
RIG_ID = "_clock_id"
DRIVEN_AXIS = "_clock_axis"
ROLE = "_clock_role"
RATE = "_clock_rate"
SOURCE = "_clock_source"
SOURCE_ZERO = "_clock_source_zero"
BASE = "_clock_base"
BIAS = "_clock_bias"
GEAR_SCHEMA = "_clock_gear_schema"
GEAR_RATIO = "_clock_gear_ratio"
SOURCE_AXIS = "_clock_source_axis"
GEAR_TEETH = "_clock_gear_teeth"
SOURCE_TEETH = "_clock_source_teeth"
DATE_REVERSE = "_clock_date_reverse"
TOOL_SETTINGS = "_clock_tool_settings"
PREVIEW = "_clock_preview"
HELPER = "_clock_helper"
HAND_PREFIX = "_hand_"
PHASE_PREFIX = "_phase_"
ROLE_KEYS = (ROLE, RATE, SOURCE, SOURCE_ZERO, BASE, BIAS, GEAR_SCHEMA, GEAR_RATIO, SOURCE_AXIS,
             GEAR_TEETH, SOURCE_TEETH, DATE_REVERSE)
HAND_KEYS = (REST, REST_MODE, REST_ROTATION, REST_DELTA, REST_DELTA_QUAT, CONTROLLER, OWNER, DRIVEN_AXIS, *ROLE_KEYS)
MODE = "time_mode"
ELAPSED = "animated_seconds"
STEPS = "steps_per_second"
BOUNCE = "tick_rebound"
DAMPING = "rebound_damping"
PRECISION = "_clock_precision"
CHRONO = "stopwatch_seconds"
RUNNING = "_stopwatch_running"
PAUSED = "_clock_paused"
DATE_START = "start_date"
DATE_BLEND = "date_transition"
CONFIG_AXIS = "_clock_config_axis"
CONFIG_REVERSE = "_clock_config_reverse"
TIME_EXPRESSION = "h*3600 + m*60 + s + (frame - off) * fb / fps * speed"
