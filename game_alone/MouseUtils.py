import ctypes


class MouseUtils:
    def __init__(self, ads=0.95):
        try:
            self.ads = ads
            self.driver = ctypes.CDLL(f'./logitech.driver.dll')
            self.ok = self.driver.device_open() == 1
            if not self.ok:
                print('初始化失败, 未安装罗技驱动')
        except FileNotFoundError:
            print('初始化失败, 缺少文件')

    def move(self, x: int, y: int):
        if (x == 0) & (y == 0):
            return
        ax = int(x * self.ads)
        ay = int(y * self.ads)

        self.driver.moveR(ax, ay, True)
        self.press(1)
        self.press(1)
        self.release(1)

    def press(self, code):
        self.driver.mouse_down(code)

    def release(self, code):
        self.driver.mouse_up(code)
