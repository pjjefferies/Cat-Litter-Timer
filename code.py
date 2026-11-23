import time
import board
import alarm
import displayio
import terminalio
import digitalio
import neopixel
from adafruit_display_text import label

# Replace with the driver for your specific 24-pin e-Ink display:
import adafruit_ssd1680

# --- CONFIGURATION ---
TIMER_MINUTES = 3  # Default countdown duration
FLASH_COUNT = 10  # Number of LED flashes when time is up
BUTTON_PIN = board.D5  # External button wired to GND

# --- HARDWARE SETUP ---
displayio.release_displays()

# Kill NeoPixel power immediately to save battery
np_power = digitalio.DigitalInOut(board.NEOPIXEL_POWER)
np_power.direction = digitalio.Direction.OUTPUT
np_power.value = False

# Onboard Red LED on D13 for low-power flashing
red_led = digitalio.DigitalInOut(board.D13)
red_led.direction = digitalio.Direction.OUTPUT

# Initialize 24-pin ThinkInk SPI bus (pins are pre-defined on this board)
spi = board.SPI()
epd_cs = board.EPD_CS
epd_dc = board.EPD_DC
epd_reset = board.EPD_RESET
epd_busy = board.EPD_BUSY

display_bus = displayio.FourWire(
    spi, command=epd_dc, chip_select=epd_cs, reset=epd_reset, baudrate=1000000
)
# Adjust width/height to match your specific e-Ink panel (e.g., 250x122 for 2.13")
display = adafruit_ssd1680.SSD1680(
    display_bus, width=250, height=122, busy_pin=epd_busy, rotation=270
)


def update_screen(main_text, sub_text=""):
    """Draws text to the e-Ink display and waits for refresh to complete."""
    group = displayio.Group()

    # White background
    bg_bitmap = displayio.Bitmap(display.width, display.height, 1)
    bg_palette = displayio.Palette(1)
    bg_palette[0] = 0xFFFFFF
    group.append(displayio.TileGrid(bg_bitmap, pixel_shader=bg_palette))

    # Main timer readout
    main_label = label.Label(terminalio.FONT, text=main_text, color=0x000000, scale=4)
    main_label.anchor_point = (0.5, 0.4)
    main_label.anchored_position = (display.width // 2, display.height // 2)
    group.append(main_label)

    # Subtext instruction
    if sub_text:
        sub_label = label.Label(terminalio.FONT, text=sub_text, color=0x000000, scale=1)
        sub_label.anchor_point = (0.5, 0.9)
        sub_label.anchored_position = (display.width // 2, display.height - 10)
        group.append(sub_label)

    display.root_group = group
    # Respect minimum refresh interval required by e-Ink controllers
    time.sleep(display.time_to_refresh + 0.1)
    display.refresh()
    while display.busy:
        time.sleep(0.1)


def flash_alert():
    """Flashes both the red D13 LED and bright NeoPixel to signal completion."""
    np_power.value = True
    pixel = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.5)

    for _ in range(FLASH_COUNT):
        red_led.value = True
        pixel[0] = (255, 0, 0)
        time.sleep(0.25)
        red_led.value = False
        pixel[0] = (0, 0, 0)
        time.sleep(0.25)

    pixel.deinit()
    np_power.value = False


# --- MAIN TIMER LOOP ---
remaining_minutes = TIMER_MINUTES

while remaining_minutes > 0:
    update_screen(f"{remaining_minutes}m", "Press button to reset")

    # Configure wake triggers: 60 seconds OR button press (active low)
    time_alarm = alarm.time.TimeAlarm(monotonic_time=time.monotonic() + 60)
    pin_alarm = alarm.pin.PinAlarm(pin=BUTTON_PIN, value=False, pull=True)

    # Light sleep preserves RAM and variables while lowering current draw
    triggered = alarm.light_sleep_until_alarms(time_alarm, pin_alarm)

    if isinstance(triggered, alarm.pin.PinAlarm):
        # Button pressed: reset countdown and debounce
        remaining_minutes = TIMER_MINUTES
        time.sleep(0.3)
    else:
        # 60 seconds elapsed
        remaining_minutes -= 1

# --- TIMER EXPIRED ---
update_screen("TIME UP!", "Press button to restart")
flash_alert()

# Enter lowest-power sleep (no TimeAlarm) until button is pressed.
# Waking from deep sleep automatically restarts code.py from the top.
wake_button = alarm.pin.PinAlarm(pin=BUTTON_PIN, value=False, pull=True)
alarm.exit_and_deep_sleep_until_alarms(wake_button)
