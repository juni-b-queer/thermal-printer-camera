from picamera2 import Picamera2
import pygame
from datetime import datetime
import sys
from gpiozero import Button
import board
import neopixel
import threading

import modules.image_control as image_control
import modules.neopixel_control as neopixel_control
import utils.colors as colors
import modules.configuration as configuration
from modules.configuration import CONFIG_METADATA
from time import time
from escpos.printer import Serial


config_path = "/home/pi/Desktop/picamera/config.json"
config = configuration.load_config(config_path)

if 'flash_color' in config and isinstance(config['flash_color'], str):
    if config['flash_color'].startswith('0x'):
        config['flash_color'] = int(config['flash_color'], 16)
    else:
        config['flash_color'] = int(config['flash_color'])


COUNTDOWN = config['countdown']
PHOTO_INTERVAL = config['photo_interval']
SHOW_FLASH = config['show_flash']
FLASH_COLOR = config['flash_color']

config_menu_page = 0
ITEMS_PER_PAGE = 3


takingPicture = False
last_blink_time = 0
led_state = False
photo_count = 0
photo_sequence_start = 0
waiting_for_first = False
printing = False
printThread = False
flashOn = False
lastPicturePath='/home/pi/Desktop/picamera/pics/1.bmp'
color_selection_active = False

config_menu_active = False
config_editing = None
modified_config = None

# button setup
btnShutter = Button(6)
btnPrint = Button(5)
pixels = neopixel.NeoPixel(board.D12, 17)

display_width = 640
display_height = 480

pygame.init()
display_res = (640, 480)
screen = pygame.display.set_mode(display_res, pygame.FULLSCREEN)

# Set desired preview size in the pygame window
preview_size = (504, 378)

# Set actual camera resolution (capture size)
camera = Picamera2()
# camera.still_configuration.main.size = camera.sensor_resolution
camera.still_configuration.main.size = (1920, 1440)
camera.still_configuration.main.format = "BGR888"

camera.preview_configuration.main.size = preview_size
camera.preview_configuration.main.format = "BGR888"
camera.configure("preview")
camera.start()

# Font setup
font = pygame.font.SysFont("Arial", 24)
options_font = pygame.font.SysFont("Arial", 28)
config_font = pygame.font.SysFont("Arial", 36)
config_title_font = pygame.font.SysFont("Arial", 42)


# Mode variable and names
mode = 0  # 0 = Picture, 1 = Photobooth, 2 = Photobooth Two
mode_names = ["Picture", "Photobooth", "Configure"]

# Define button rectangles
button_rects = {
    0: pygame.Rect(504, 0, 136, 126),  # Red
    1: pygame.Rect(504, 126, 136, 126),  # Green
    2: pygame.Rect(504, 252, 136, 126)  # Blue
}

# Button colors by mode index
button_colors = {
    0: "red",
    1: "green",
    2: "blue"
}

button_labels = {
    0: "Picture",
    1: "Photobooth",
    2: "Configure"
}


# Button functions
def on_red_button():
    global mode
    mode = 0
    print("Red button pressed! Mode set to 0 (Picture).")


def on_green_button():
    global mode
    mode = 1
    print("Green button pressed! Mode set to 1 (Photobooth).")


def on_blue_button():
    global mode, config_menu_active, modified_config, config_menu_page
    mode = 2
    config_menu_active = True
    config_menu_page = 0  # Reset to first page
    # Create a copy of current config for tracking changes
    modified_config = dict(configuration.load_config(config_path))
    print("Blue button pressed! Mode set to 2 (Configure).")


def handle_button_click(pos):
    if button_rects[0].collidepoint(pos):
        on_red_button()
    elif button_rects[1].collidepoint(pos):
        on_green_button()
    elif button_rects[2].collidepoint(pos):
        on_blue_button()


def draw_buttons():
    for i in range(3):
        rect = button_rects[i]
        color = button_colors[i]
        pygame.draw.rect(screen, color, rect)

        # Add white outline if it's the active mode
        if i == mode:
            pygame.draw.rect(screen, "white", rect, 4)  # 4px border

        # Label
        label = button_labels[i]
        text_surface = font.render(label, True, (255, 255, 255))
        text_rect = text_surface.get_rect(center=rect.center)
        screen.blit(text_surface, text_rect)


def draw_bottom_bar():
    pygame.draw.rect(screen, "white", (0, 378, 640, 102))
    center = 480 - (102 / 2)

    current_time = time()

    if takingPicture:
        if mode == 0:
            time_since_last = current_time - photo_sequence_start
            time_to_next = max(0, COUNTDOWN - time_since_last)
            countdown_text = f"First photo in: {time_to_next:.1f}s"
            countdown_surface = font.render(countdown_text, True, (0, 0, 0))
            screen.blit(countdown_surface, (10, center))


        elif mode == 1:
            # Show current photo number and countdown to next
            time_since_last = current_time - photo_sequence_start
            time_to_next = max(0, PHOTO_INTERVAL - time_since_last)
            countdown_text = f"Photo {photo_count + 1}/4 - Next in: {time_to_next:.1f}s"
            countdown_surface = font.render(countdown_text, True, (0, 0, 0))
            screen.blit(countdown_surface, (10, center))
    else:
        # Regular mode display when not taking pictures
        mode_label = button_labels[mode]
        mode_surface = font.render(f"Mode: {mode_label}", True, (0, 0, 0))
        screen.blit(mode_surface, (10, center))

    # Time on right (always show)
    now = datetime.now().strftime("%D %H:%M")
    time_surface = font.render(now, True, (0, 0, 0))
    time_rect = time_surface.get_rect(topright=(630, center))
    screen.blit(time_surface, time_rect)


def draw_config_menu():
    global config_menu_active, config_editing, modified_config, config_menu_page, color_selection_active

    screen.fill((240, 240, 240))

    if color_selection_active:
        screen.fill((240, 240, 240))

        # Draw color grid
        colors_per_row = 5
        square_size = 90  # Slightly smaller to fit 4 in a row
        spacing = 20
        start_x = (display_width - (colors_per_row * (square_size + spacing))) // 2
        start_y = 30  # Start higher up since we removed the header
        x = start_x
        y = start_y

        for color_name, color_value in CONFIG_METADATA["flash_color"]["options"].items():
            # Draw color square
            color_rect = pygame.Rect(x, y, square_size, square_size)
            r = (color_value >> 16) & 0xFF
            g = (color_value >> 8) & 0xFF
            b = color_value & 0xFF
            pygame.draw.rect(screen, (r, g, b), color_rect)
            pygame.draw.rect(screen, (0, 0, 0), color_rect, 3)

            # Highlight selected color
            if color_value == modified_config["flash_color"]:
                pygame.draw.rect(screen, (255, 255, 255), color_rect, 5)

            # Draw color name
            name_text = options_font.render(color_name, True, (0, 0, 0))
            name_rect = name_text.get_rect(center=(x + square_size // 2, y + square_size + 20))
            screen.blit(name_text, name_rect)

            x += square_size + spacing
            if x + square_size > display_width - start_x:
                x = start_x
                y += square_size + spacing + 30  # Extra space for labels

        # Draw back button at bottom
        back_rect = pygame.Rect(20, display_height - 80, 150, 60)
        pygame.draw.rect(screen, (200, 200, 200), back_rect)
        back_text = config_font.render("Back", True, (0, 0, 0))
        screen.blit(back_text, (55, display_height - 70))

        # Draw save button if changes were made
        if modified_config != configuration.load_config(config_path):
            save_rect = pygame.Rect(190, display_height - 80, 150, 60)
            pygame.draw.rect(screen, (100, 200, 100), save_rect)
            save_text = config_font.render("Save", True, (0, 0, 0))
            screen.blit(save_text, (225, display_height - 70))

    else:
        # Draw regular config menu
        total_pages = (len(modified_config) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
        title = config_title_font.render(f"Configuration Menu ({config_menu_page + 1}/{total_pages})", True, (0, 0, 0))
        screen.blit(title, (20, 30))

        # Calculate which items to show on current page
        items = list(modified_config.items())
        start_idx = config_menu_page * ITEMS_PER_PAGE
        end_idx = min(start_idx + ITEMS_PER_PAGE, len(items))
        current_page_items = items[start_idx:end_idx]

        y_pos = 120
        for key, value in current_page_items:
            # Draw option label
            option_text = config_font.render(f"{key}:", True, (0, 0, 0))
            screen.blit(option_text, (20, y_pos))

            if CONFIG_METADATA[key]["type"] == "bool":
                # Draw checkbox
                checkbox_rect = pygame.Rect(280, y_pos - 5, 45, 45)
                if value:
                    pygame.draw.rect(screen, (100, 200, 100), checkbox_rect)
                    pygame.draw.rect(screen, (255, 255, 255), checkbox_rect, 3)
                else:
                    pygame.draw.rect(screen, (255, 255, 255), checkbox_rect)
                    pygame.draw.rect(screen, (0, 0, 0), checkbox_rect, 3)

            elif CONFIG_METADATA[key]["type"] == "select" and key == "flash_color":
                # Draw current color preview with label
                color_rect = pygame.Rect(280, y_pos - 5, 180, 45)
                r = (value >> 16) & 0xFF
                g = (value >> 8) & 0xFF
                b = value & 0xFF
                pygame.draw.rect(screen, (r, g, b), color_rect)
                pygame.draw.rect(screen, (0, 0, 0), color_rect, 3)

                # Add "Click to change" text
                change_text = font.render("Click to change", True, (0, 0, 0))
                screen.blit(change_text, (470, y_pos + 5))

            else:
                # Handle numeric options
                if CONFIG_METADATA[key]["type"] == "float":
                    value_str = f"{value:.2f}"
                else:
                    value_str = str(value)

                value_rect = pygame.Rect(280, y_pos - 5, 180, 45)
                pygame.draw.rect(screen, (200, 200, 200), value_rect)
                value_text = config_font.render(value_str, True, (0, 0, 0))
                screen.blit(value_text, (290, y_pos))

                if config_editing == key:
                    # Draw control buttons
                    plus_rect = pygame.Rect(470, y_pos - 5, 45, 45)
                    pygame.draw.rect(screen, (150, 150, 150), plus_rect)
                    plus_text = config_font.render("+", True, (0, 0, 0))
                    screen.blit(plus_text, (485, y_pos))

                    minus_rect = pygame.Rect(525, y_pos - 5, 45, 45)
                    pygame.draw.rect(screen, (150, 150, 150), minus_rect)
                    minus_text = config_font.render("-", True, (0, 0, 0))
                    screen.blit(minus_text, (540, y_pos))

                    check_rect = pygame.Rect(580, y_pos - 5, 45, 45)
                    pygame.draw.rect(screen, (150, 150, 150), check_rect)
                    check_text = config_font.render("✓", True, (0, 0, 0))
                    screen.blit(check_text, (590, y_pos))

            y_pos += 75

        # Draw navigation buttons if there are multiple pages
        if total_pages > 1:
            if config_menu_page > 0:
                prev_rect = pygame.Rect(20, display_height - 150, 150, 60)
                pygame.draw.rect(screen, (200, 200, 200), prev_rect)
                prev_text = config_font.render("Previous", True, (0, 0, 0))
                screen.blit(prev_text, (35, display_height - 140))

            if config_menu_page < total_pages - 1:
                next_rect = pygame.Rect(190, display_height - 150, 150, 60)
                pygame.draw.rect(screen, (200, 200, 200), next_rect)
                next_text = config_font.render("Next", True, (0, 0, 0))
                screen.blit(next_text, (225, display_height - 140))

        # Draw Back and Save buttons
        back_rect = pygame.Rect(20, display_height - 80, 150, 60)
        pygame.draw.rect(screen, (200, 200, 200), back_rect)
        back_text = config_font.render("Back", True, (0, 0, 0))
        screen.blit(back_text, (55, display_height - 70))

        if modified_config != configuration.load_config(config_path):
            save_rect = pygame.Rect(190, display_height - 80, 150, 60)
            pygame.draw.rect(screen, (100, 200, 100), save_rect)
            save_text = config_font.render("Save", True, (0, 0, 0))
            screen.blit(save_text, (225, display_height - 70))

def handle_config_menu_click(pos):
    global config_menu_active, config_editing, modified_config, mode, config
    global COUNTDOWN, PHOTO_INTERVAL, SHOW_FLASH, FLASH_COLOR, config_menu_page
    global color_selection_active

    if color_selection_active:
        # Handle clicks on color selection page
        # Check back button first
        if pygame.Rect(20, display_height - 80, 150, 60).collidepoint(pos):
            color_selection_active = False
            return

        # Check save button if changes were made
        if modified_config != configuration.load_config(config_path):
            if pygame.Rect(190, display_height - 80, 150, 60).collidepoint(pos):
                save_config = modified_config.copy()
                if "flash_color" in save_config:
                    if isinstance(save_config["flash_color"], str):
                        save_config["flash_color"] = int(save_config["flash_color"], 16)
                configuration.save_config(save_config,config_path)
                color_selection_active = False
                config_menu_active = False
                config_editing = None
                config_menu_page = 0
                config = configuration.load_config(config_path)
                COUNTDOWN = config['countdown']
                PHOTO_INTERVAL = config['photo_interval']
                SHOW_FLASH = config['show_flash']
                FLASH_COLOR = config['flash_color']
                mode = 0
                return

        # Handle color selection grid clicks
        colors_per_row = 5
        square_size = 90
        spacing = 20
        start_x = (display_width - (colors_per_row * (square_size + spacing))) // 2
        start_y = 30
        x = start_x
        y = start_y

        for color_name, color_value in CONFIG_METADATA["flash_color"]["options"].items():
            color_rect = pygame.Rect(x, y, square_size, square_size)
            if color_rect.collidepoint(pos):
                modified_config["flash_color"] = color_value
                return

            x += square_size + spacing
            if x + square_size > display_width - start_x:
                x = start_x
                y += square_size + spacing + 30

        return

    # Handle regular config menu clicks
    # Handle pagination buttons
    total_pages = (len(modified_config) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE
    if total_pages > 1:
        if config_menu_page > 0:
            if pygame.Rect(20, display_height - 150, 150, 60).collidepoint(pos):
                config_menu_page -= 1
                config_editing = None
                return

        if config_menu_page < total_pages - 1:
            if pygame.Rect(190, display_height - 150, 150, 60).collidepoint(pos):
                config_menu_page += 1
                config_editing = None
                return

    # Get current page items
    items = list(modified_config.items())
    start_idx = config_menu_page * ITEMS_PER_PAGE
    end_idx = min(start_idx + ITEMS_PER_PAGE, len(items))
    current_page_items = items[start_idx:end_idx]

    # Handle configuration options on current page
    y_pos = 120
    for key, value in current_page_items:
        if CONFIG_METADATA[key]["type"] == "bool":
            checkbox_rect = pygame.Rect(280, y_pos - 5, 45, 45)
            if checkbox_rect.collidepoint(pos):
                modified_config[key] = not modified_config[key]
                return

        elif CONFIG_METADATA[key]["type"] == "select" and key == "flash_color":
            # Handle color preview click - opens color selection page
            if pygame.Rect(280, y_pos - 5, 180, 45).collidepoint(pos):
                color_selection_active = True
                return

        else:
            # Handle numeric options
            value_rect = pygame.Rect(280, y_pos - 5, 180, 45)
            if value_rect.collidepoint(pos):
                config_editing = key
                return

            if config_editing == key:
                increment = CONFIG_METADATA[key]["increment"]
                value_type = CONFIG_METADATA[key]["type"]

                # Plus button
                if pygame.Rect(470, y_pos - 5, 45, 45).collidepoint(pos):
                    if value_type == "float":
                        modified_config[key] = round(modified_config[key] + increment, 2)
                    else:
                        modified_config[key] = modified_config[key] + increment
                    return

                # Minus button
                if pygame.Rect(525, y_pos - 5, 45, 45).collidepoint(pos):
                    if value_type == "float":
                        modified_config[key] = round(modified_config[key] - increment, 2)
                    else:
                        modified_config[key] = max(1, modified_config[key] - increment)
                    return

                # Check button
                if pygame.Rect(580, y_pos - 5, 45, 45).collidepoint(pos):
                    config_editing = None
                    return

        y_pos += 75

    # Handle back button
    if pygame.Rect(20, display_height - 80, 150, 60).collidepoint(pos):
        config_menu_active = False
        config_editing = None
        config_menu_page = 0
        mode = 0
        return

    # Handle save button
    if modified_config != configuration.load_config(config_path):
        if pygame.Rect(190, display_height - 80, 150, 60).collidepoint(pos):
            save_config = modified_config.copy()
            if "flash_color" in save_config:
                if isinstance(save_config["flash_color"], str):
                    save_config["flash_color"] = int(save_config["flash_color"], 16)
            configuration.save_config(save_config,config_path)
            config_menu_active = False
            config_editing = None
            config_menu_page = 0
            config = configuration.load_config(config_path)
            COUNTDOWN = config['countdown']
            PHOTO_INTERVAL = config['photo_interval']
            SHOW_FLASH = config['show_flash']
            FLASH_COLOR = config['flash_color']
            mode = 0
            return


# Camera functions
def takePicture(imageName):
    # set picture size to 1920x1080
    camera.switch_mode("still")

    # Capture the image
    camera.capture_file(imageName)

    # Switch back to preview mode
    camera.switch_mode("preview")


def handle_photo_sequence(num_photos=1, combine_photos=False):
    global takingPicture, waiting_for_first, photo_count, photo_sequence_start, led_state, last_blink_time, flashOn

    time_to_picture = COUNTDOWN

    if num_photos > 1:
        time_to_picture = PHOTO_INTERVAL

    current_time = time()

    # Initialize sequence if we're just starting
    if photo_count == 0 and not waiting_for_first:
        photo_sequence_start = current_time
        waiting_for_first = True
        last_blink_time = current_time
        if num_photos > 1:
            neopixel_control.fineControlRing(pixels, [colors.BLUE])

    # Flash bright ring right before photo
    elif time_to_picture - 0.5 <= current_time - photo_sequence_start < time_to_picture and flashOn == False:
        if SHOW_FLASH:
            neopixel_control.setRing(pixels, FLASH_COLOR)
            flashOn = True

    # Take photo when interval is reached
    elif waiting_for_first and current_time - photo_sequence_start >= time_to_picture:
        waiting_for_first = False
        photo_count = 1
        neopixel_control.setLED(pixels, colors.OFF)

        photo_filename = f"/home/pi/Desktop/picamera/pics/{'pb_' if num_photos > 1 else ''}{photo_count}.jpg"
        takePicture(photo_filename)

        current_time = time()
        photo_sequence_start = current_time
        last_blink_time = current_time
        led_state = False
        neopixel_control.setRing(pixels, colors.OFF)
        flashOn = False

        if num_photos > 1:
            neopixel_control.fineControlRing(pixels, [colors.BLUE for i in range(photo_count + 1)])

    # Handle subsequent photos for multi-photo sequence
    elif photo_count > 0 and current_time - photo_sequence_start >= time_to_picture:
        neopixel_control.setLED(pixels, colors.OFF)
        photo_count += 1

        photo_filename = f"/home/pi/Desktop/picamera/pics/{'pb_' if num_photos > 1 else ''}{photo_count}.jpg"
        takePicture(photo_filename)

        current_time = time()
        photo_sequence_start = current_time
        last_blink_time = current_time
        led_state = False

        if num_photos > 1:
            neopixel_control.setRing(pixels, colors.OFF)
            flashOn = False
            neopixel_control.fineControlRing(pixels, [colors.BLUE for i in range(photo_count + 1)])


    # Handle LED blinking during countdown
    else:
        if current_time - photo_sequence_start >= time_to_picture - COUNTDOWN:
            blink_interval = 0.25  # Fast blink in final countdown
        else:
            blink_interval = 0.5  # Slower blink during initial wait

        if current_time - last_blink_time >= blink_interval:
            led_state = not led_state
            neopixel_control.setLED(pixels, colors.RED if led_state else colors.OFF)
            last_blink_time = current_time

    if photo_count >= num_photos:
        takingPicture = False
        photo_count = 0
        waiting_for_first = False
        neopixel_control.setRing(pixels, colors.OFF)
        flashOn = False
        neopixel_control.setLED(pixels, colors.OFF)
        path = ""
        if combine_photos and num_photos > 1:
            paths = [f"/home/pi/Desktop/picamera/pics/pb_{i}.jpg" for i in range(1, num_photos + 1)]
            image_control.combineImages(paths)
            path = "/home/pi/Desktop/picamera/pics/combined_photos.bmp"
        elif num_photos == 1:
            image_control.convertJpgToBmp("/home/pi/Desktop/picamera/pics/1.jpg")
            path = "/home/pi/Desktop/picamera/pics/1.bmp"

        startPrintThread(path)

def startPrintThread(path):
    global printing, printThread, lastPicturePath
    lastPicturePath = path
    printing = True
    printThread = threading.Thread(target=printBmp, args=(path,))
    printThread.start()

def printBmp(path):
    print('print bmp')
    neopixel_control.setLED(pixels, colors.BLUE)
    p = Serial(devfile='/dev/ttyS0', baudrate=9600, bytesize=8, parity='N', stopbits=1, timeout=1.00, dsrdtr=True)
    p.image(path)
    p.textln('')
    p.textln(datetime.now().strftime("%D %H:%M"))
    p.textln('')
    p.textln('')
    p.close()
    neopixel_control.setLED(pixels, colors.OFF)
    return True


# Main loop


while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if mode == 2 and config_menu_active:
                handle_config_menu_click(event.pos)
            else:
                handle_button_click(event.pos)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_q:
                pygame.quit()
                sys.exit()

    if btnShutter.is_pressed and takingPicture == False:
        print('shutter')
        # image_control.convertImg()
        takingPicture = True
        neopixel_control.setLED(pixels, colors.RED)

    if btnPrint.is_pressed and takingPicture == False:
        print('print')
        if printing and printThread:
            print('printing and printThread')
            if not printThread.is_alive():
                printing = False
                printThread = None

        if lastPicturePath != "" and printing == False:
            printing = True
            startPrintThread(lastPicturePath)
            
    if takingPicture:
        if mode == 0:
            handle_photo_sequence(num_photos=1, combine_photos=False)
        elif mode == 1:
            handle_photo_sequence(num_photos=config['photobooth_count'], combine_photos=True)

    if mode == 2 and config_menu_active:
        draw_config_menu()
    else:
        # Existing camera preview and button drawing code
        array = camera.capture_array()
        img = pygame.image.frombuffer(array.data, preview_size, 'RGB')
        screen.blit(img, (0, 0))
        draw_buttons()
        draw_bottom_bar()

    pygame.display.update()
