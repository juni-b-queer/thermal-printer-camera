from picamera2 import Picamera2
def init_camera(main_size, preview_size=(504, 378)):
    camera = Picamera2()
    # camera.still_configuration.main.size = camera.sensor_resolution
    camera.still_configuration.main.size = main_size
    camera.still_configuration.main.format = "BGR888"

    camera.preview_configuration.main.size = preview_size
    camera.preview_configuration.main.format = "BGR888"
    camera.configure("preview")
    camera.start()
    return camera

def take_picture(camera, path):
    camera.switch_mode("still")
    camera.capture_file(path)
    camera.switch_mode("preview")