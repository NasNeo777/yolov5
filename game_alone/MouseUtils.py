import ctypes
import time
import math


class PIDController:
    """简单 PID 控制器，用于平滑鼠标移动"""

    def __init__(self, kp=0.5, ki=0.0, kd=0.1, max_output=50):
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.max_output = max_output
        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0

    def compute(self, error_x, error_y):
        # 比例项
        p_x = self.kp * error_x
        p_y = self.kp * error_y

        # 积分项（限幅防止积分饱和）
        self.integral_x = max(-30, min(30, self.integral_x + error_x))
        self.integral_y = max(-30, min(30, self.integral_y + error_y))
        i_x = self.ki * self.integral_x
        i_y = self.ki * self.integral_y

        # 微分项
        d_x = self.kd * (error_x - self.prev_error_x)
        d_y = self.kd * (error_y - self.prev_error_y)
        self.prev_error_x = error_x
        self.prev_error_y = error_y

        # 输出限幅
        out_x = max(-self.max_output, min(self.max_output, p_x + i_x + d_x))
        out_y = max(-self.max_output, min(self.max_output, p_y + i_y + d_y))
        return int(out_x), int(out_y)

    def reset(self):
        self.prev_error_x = 0
        self.prev_error_y = 0
        self.integral_x = 0
        self.integral_y = 0


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

        self.pid = PIDController(kp=0.45, ki=0.0, kd=0.08, max_output=60)
        # 距离阈值：小于此值认为已瞄准，直接击发
        self.aim_threshold = 5

    def move(self, x: float, y: float):
        """通过 PID 控制器平滑移动鼠标并自动射击"""
        if x == 0 and y == 0:
            return

        # 应用 ads 缩放
        tx = x * self.ads
        ty = y * self.ads

        dist = math.hypot(tx, ty)

        if dist < self.aim_threshold:
            # 已经很接近目标，直接一步到位并击发
            self.pid.reset()
            self._do_move(int(tx), int(ty))
            self._shoot()
        else:
            # 通过 PID 计算平滑步长
            dx, dy = self.pid.compute(tx, ty)
            if dx != 0 or dy != 0:
                self._do_move(dx, dy)

    def _do_move(self, x: int, y: int):
        """执行实际的相对移动"""
        self.driver.moveR(x, y, True)

    def _shoot(self):
        """执行点击（短连按）"""
        self.driver.mouse_down(1)
        self.driver.mouse_down(1)
        self.driver.mouse_up(1)

    def press(self, code):
        self.driver.mouse_down(code)

    def release(self, code):
        self.driver.mouse_up(code)

