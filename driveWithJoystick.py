import pygame
import time
import sys
import math
from spherov2 import scanner
from spherov2.types import Color
from spherov2.sphero_edu import SpheroEduAPI
from spherov2.commands.power import Power

# ==========================
# BUTTON MAPPING
# ==========================
BUTTONS = {
    '1': 0,
    '2': 1,
    '3': 2,
    '4': 3,
    'L1': 4,
    'R1': 5,
    'L2': 6,
    'R2': 7,
    'SELECT': 8,
    'START': 9,
    # Add directional buttons and B/A for Konami Code
    'UP': 10,
    'DOWN': 11,
    'LEFT': 12,
    'RIGHT': 13,
    'B': 14,
    'A': 15
}

LED_PATTERNS = {1: '1', 2: '2', 3: '3', 4: '4', 5: '5'}

BATTERY_CHECK_INTERVAL = 30
HEADING_ADJUSTMENT = 5


# Konami Code Sequence
KONAMI_CODE = [
    BUTTONS['UP'], BUTTONS['UP'],
    BUTTONS['DOWN'], BUTTONS['DOWN'],
    BUTTONS['LEFT'], BUTTONS['RIGHT'],
    BUTTONS['LEFT'], BUTTONS['RIGHT'],
    BUTTONS['B'], BUTTONS['A']
]

# ==========================
# SPHERO CONTROLLER CLASS
# ==========================
class SpheroController:
    def __init__(self, joystick, color, player_id, toy_name=None):
        self.joystick = joystick
        self.color = color
        self.player_id = player_id
        self.toy_name = toy_name

        self.toy = None
        self.api = None

        self.speed = 50
        self.base_heading = 0
        self.is_running = True
        self.calibration_mode = False
        self.game_on = False
        self.last_battery_check = time.time()
        self.game_start_time = time.time()

        # Konami Code attributes
        self.konami_index = 0
        self.cheat_mode = False

    # ==========================
    # DISCOVERY & CONNECTION
    # ==========================
    def discover_toy(self):
        try:
            if self.toy_name:
                print(f"Searching for Sphero named '{self.toy_name}'...")
                self.toy = scanner.find_toy(toy_name=self.toy_name)
            else:
                print("Searching for nearest Sphero...")
                toys = scanner.find_toys()
                if toys:
                    self.toy = toys[0]
                else:
                    raise Exception("No Sphero toys found.")
            print(f"Connected to '{self.toy.name}'")
        except Exception as e:
            print(f"Error discovering toy: {e}")

    def connect(self):
        if not self.toy:
            print("No toy to connect to.")
            return None
        try:
            self.api = SpheroEduAPI(self.toy)
            print("API connected successfully.")
            return self.api
        except Exception as e:
            print(f"Error connecting to toy API: {e}")
            return None

    # ==========================
    # MOVEMENT & CALIBRATION
    # ==========================
    def move(self, heading, speed):
        self.api.set_heading(heading % 360)
        self.api.set_speed(speed)

    def toggle_calibration(self, x_axis):
        if not self.calibration_mode:
            self.enter_calibration(x_axis)
        else:
            self.exit_calibration()

    def enter_calibration(self, x_axis):
        self.calibration_mode = True
        self.api.set_speed(0)
        self.api.set_front_led(Color(255, 0, 0))

        if x_axis < -0.7:
            self.base_heading -= HEADING_ADJUSTMENT
        elif x_axis > 0.7:
            self.base_heading += HEADING_ADJUSTMENT

        self.api.set_heading(self.base_heading)
        print(f"Calibrating... base heading = {self.base_heading}")

    def exit_calibration(self):
        self.calibration_mode = False
        self.api.set_front_led(Color(0, 255, 0))
        self.base_heading %= 360
        self.game_on = True
        self.game_start_time = time.time()
        print("Calibration complete.")

    # ==========================
    # BATTERY MONITORING
    # ==========================
    def check_battery(self):
        try:
            voltage = Power.get_battery_voltage(self.toy)
            print(f"Player {self.player_id} battery: {voltage:.2f} V")

            color = Color(0, 255, 0)
            if voltage < 4.1:
                color = Color(255, 255, 0)
            if voltage < 3.9:
                color = Color(255, 100, 0)
            if voltage < 3.7:
                color = Color(255, 0, 0)

            self.api.set_front_led(color)
        except Exception as e:
            print(f"Battery check failed: {e}")

    # ==========================
    # KONAMI CODE CHEAT MODE
    # ==========================
    def check_konami_code(self):
        for btn_name, btn_id in BUTTONS.items():
            if self.joystick.get_button(btn_id):
                expected_btn = KONAMI_CODE[self.konami_index]
                if btn_id == expected_btn:
                    self.konami_index += 1
                    if self.konami_index == len(KONAMI_CODE):
                        self.activate_cheat_mode()
                        self.konami_index = 0
                else:
                    self.konami_index = 0

    def activate_cheat_mode(self):
        self.cheat_mode = True
        self.speed = 255
        print("Cheat mode activated! Unlimited speed.")
        self.api.set_front_led(Color(255, 0, 255))  # Purple LED

    # ==========================
    # CONTROL LOOP
    # ==========================
    def control_loop(self):
        with self.api:
            self.display_number()

            while self.is_running:
                pygame.event.pump()
                current_time = time.time()

                if current_time - self.last_battery_check >= 30:
                    self.check_battery()
                    self.last_battery_check = current_time

                x_axis = self.joystick.get_axis(0)
                y_axis = self.joystick.get_axis(1)

                # Check for Konami Code
                self.check_konami_code()

                # Speed presets (skip if cheat mode)
                if not self.cheat_mode:
                    if self.joystick.get_button(BUTTONS['1']):
                        self.speed = 50
                        self.color = Color(255, 200, 0)
                    elif self.joystick.get_button(BUTTONS['2']):
                        self.speed = 70
                        self.color = Color(255, 100, 0)
                    elif self.joystick.get_button(BUTTONS['3']):
                        self.speed = 100
                        self.color = Color(255, 50, 0)
                    elif self.joystick.get_button(BUTTONS['4']):
                        self.speed = 200
                        self.color = Color(255, 0, 0)

                # Movement control
                if self.calibration_mode:
                    self.enter_calibration(x_axis)
                elif abs(y_axis) > 0.7:
                    heading = self.base_heading if y_axis < 0 else (self.base_heading + 180)
                    self.move(heading, self.speed)
                elif abs(x_axis) > 0.7:
                    heading = self.base_heading + (22 if x_axis > 0 else -22)
                    self.move(heading, 0)
                else:
                    self.api.set_speed(0)

                # Auto-straighten in cheat mode
                if self.cheat_mode and abs(y_axis) > 0.7 and abs(x_axis) < 0.2:
                    current_heading = self.api.get_heading()
                    delta = current_heading - self.base_heading
                    if abs(delta) > 3:
                        correction = -delta * 0.2
                        self.base_heading += correction
                        self.api.set_heading(self.base_heading)

                self.display_number()
                time.sleep(0.02)

    def display_number(self):
        try:
            char = LED_PATTERNS.get(self.player_id, '?')
            self.api.set_matrix_character(char, self.color)
        except Exception as e:
            print(f"Failed to display player number: {e}")


# ==========================
# MAIN
# ==========================
def main(toy_name, joystick_id, player_id):
    pygame.init()
    pygame.joystick.init()

    if pygame.joystick.get_count() == 0:
        print("No joystick detected.")
        return

    joystick = pygame.joystick.Joystick(joystick_id)
    joystick.init()

    sphero = SpheroController(joystick, Color(255, 0, 0), player_id, toy_name)
    sphero.discover_toy()
    if sphero.connect():
        sphero.control_loop()


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python sphero_controller.py <toy_name> <joystick_id> <player_id>")
        sys.exit(1)

    toy_name, joystick_id, player_id = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    print(f"Connecting to {toy_name} (Joystick {joystick_id}, Player {player_id})...")
    main(toy_name, joystick_id, player_id)
