import time
import keyboard
import mouse

class ListenerKeybord:
    def __init__(self, config):
        self.config = config
        self.call()

    def _toggle(self, _):
        self.config.toogle()

    def _set_red(self, _):
        self.config.setRed()
        
    def _set_blue(self, _):
        self.config.setBlue()

    def _destroy(self, _):
        self.config.destroy()

    def call(self):
        # 使用 keyboard 模块绑定按键 (即使在后台也能全局监听)
        keyboard.on_press_key('shift', self._toggle)
        keyboard.on_press_key('f3', self._toggle)
        keyboard.on_press_key('f2', self._set_red)
        keyboard.on_press_key('f1', self._set_blue)
        keyboard.on_press_key('end', self._destroy)

        # 使用 mouse 模块绑定中键
        mouse.on_middle_click(self.config.toogle)

        # 保持主线程运行，直到 config._is_destroyed 为 True
        while not self.config.isDes:
            time.sleep(0.1)
            
        # 退出前清理所有的钩子
        keyboard.unhook_all()
        mouse.unhook_all()

