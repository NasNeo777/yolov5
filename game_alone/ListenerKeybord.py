from pynput.keyboard import Listener as KeyboardListener, Key
from pynput.mouse import Listener as MouseListener, Button


class ListenerKeybord:
    def __init__(self, config):
        self.config = config
        self.call()

    def release(self, key):
        pass

    def press(self, key):
        if key == Key.shift:
            self.config.toogle()
        if key == Key.f3:
            self.config.toogle()
        if key == Key.end:
            self.config.destroy()
        elif key == Key.f2:
            self.config.setRed()
        elif key == Key.f1:
            self.config.setBlue()

    def on_click(self, x, y, button, pressed):
        if pressed and button == Button.middle:
            self.config.toogle()

    def call(self):
        with KeyboardListener(on_release=self.release, on_press=self.press) as k_listener, \
                MouseListener(on_click=self.on_click) as m_listener:
            k_listener.join()
            m_listener.join()
