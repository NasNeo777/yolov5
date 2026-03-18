import ctypes
import ctypes.wintypes as wintypes
import time
import math
import struct

# ── Windows SendInput 结构体定义（鼠标相对移动）──────────────────────────────
MOUSEEVENTF_MOVE = 0x0001
INPUT_MOUSE      = 0

class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx',          ctypes.c_long),
        ('dy',          ctypes.c_long),
        ('mouseData',   ctypes.c_ulong),
        ('dwFlags',     ctypes.c_ulong),
        ('time',        ctypes.c_ulong),
        ('dwExtraInfo', ctypes.POINTER(ctypes.c_ulong)),
    ]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [('mi', MOUSEINPUT)]

class INPUT(ctypes.Structure):
    _fields_ = [
        ('type',   ctypes.c_ulong),
        ('_input', _INPUT_UNION),
    ]

def _send_input_move(dx: int, dy: int):
    """通过 Windows SendInput API 发送相对鼠标移动"""
    inp = INPUT()
    inp.type = INPUT_MOUSE
    # Union 字段访问方式不同，直接通过 _input.mi 访问
    inp._input.mi.dx = dx
    inp._input.mi.dy = dy
    inp._input.mi.mouseData = 0
    inp._input.mi.dwFlags = MOUSEEVENTF_MOVE
    inp._input.mi.time = 0
    inp._input.mi.dwExtraInfo = ctypes.pointer(ctypes.c_ulong(0))
    ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(inp))


class PIDController:
    """简单 PID 控制器，用于平滑鼠标移动"""

    def __init__(self, kp=0.25, ki=0.0, kd=0.15, max_output=30):
        # 调低 kp (原 0.45) 降低跟枪速度，避免 COD 内灵敏度过高导致视角乱飞过冲
        # 调高 kd (原 0.08) 增加阻尼，稳定准星不反复横跳
        # 调低 max_output (原 60) 限制单次移动最大像素，防止镜头瞬间甩飞
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
        self.integral_x = max(-15, min(15, self.integral_x + error_x))
        self.integral_y = max(-15, min(15, self.integral_y + error_y))
        i_x = self.ki * self.integral_x
        i_y = self.ki * self.integral_y

        # 微分项 (对抗抖动)
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
        import os
        self.ok = False
        self.ads = ads
        # 优先用脚本文件同目录的绝对路径，防止多进程工作目录漂移
        dll_candidates = [
            os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logitech.driver.dll'),
            os.path.join(os.getcwd(), 'logitech.driver.dll'),
        ]
        dll_path = None
        for p in dll_candidates:
            if os.path.exists(p):
                dll_path = p
                break
        if dll_path is None:
            print(f'[MouseUtils] 初始化失败, 找不到 logitech.driver.dll，搜索路径: {dll_candidates}')
            return
        try:
            self.driver = ctypes.CDLL(dll_path)
            result = self.driver.device_open()
            self.ok = (result == 1)
            if not self.ok:
                print(f'[MouseUtils] device_open() 返回 {result}，未成功连接罗技驱动（G HUB 是否运行？）')
            else:
                print(f'[MouseUtils] 罗技驱动初始化成功: {dll_path}')
        except Exception as e:
            print(f'[MouseUtils] 加载 DLL 异常: {e}')

        # 使用平滑参数创建 PID 控制器 (max_output=20 限制COD中单次平滑甩枪极值)
        self.pid = PIDController(kp=0.20, ki=0.0, kd=0.15, max_output=20)
        # 距离阈值：放到 10 个像素，在 COD 这种需要跟枪的游戏中容错更高
        self.aim_threshold = 10
        # True = 罗技DLL moveR；False = Windows SendInput
        # COD Ricochet 反作弊可能屏蔽 DLL，可改为 False 测试 SendInput
        self.use_dll = False
        self._move_call_cnt = 0

    def move(self, x: float, y: float):
        """通过 PID 控制器平滑移动鼠标并自动射击"""
        if not self.ok and self.use_dll:
            return  # 驱动未就绪，直接跳过
        if x == 0 and y == 0:
            return
        # 首次调用打印一次，确认 move() 确实被执行到
        self._move_call_cnt += 1
        if self._move_call_cnt == 1:
            print(f'[MouseUtils] move() 首次调用 x={x:.1f} y={y:.1f}  use_dll={self.use_dll}')

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
            # 1. 通过 PID 计算平滑基础步长
            dx, dy = self.pid.compute(tx, ty)
            
            # 2. 加入微量抖动 (大幅削减，之前噪音太大导致乱跑)
            import random
            jitter_factor = min(0.5, dist / 200.0) 
            
            noise_x = random.uniform(-0.5, 0.5) * jitter_factor
            noise_y = random.uniform(-0.8, 0.8) * jitter_factor
            
            final_dx = dx + noise_x
            final_dy = dy + noise_y
            
            # 强制步长减半 (很多 FPS 游戏的鼠标输入会把 dx/dy 当作角度放大)
            final_dx = final_dx * 0.45
            final_dy = final_dy * 0.45

            if abs(final_dx) >= 1 or abs(final_dy) >= 1:
                self._do_move(int(final_dx), int(final_dy))

    def _do_move(self, x: int, y: int):
        """执行实际的相对移动
        use_dll=True  → 罗技驱动 moveR（驱动层，穿透性强）
        use_dll=False → Windows SendInput（无需罗技驱动，可测试是否被 COD 屏蔽）
        """
        # 每 60 次打印一次，避免刷屏
        self._move_dbg_cnt = getattr(self, '_move_dbg_cnt', 0) + 1
        if self._move_dbg_cnt % 60 == 1:
            print(f'[MouseUtils] _do_move dx={x} dy={y}  use_dll={self.use_dll}')

        if self.use_dll and self.ok:
            # ① 罗技驱动层（默认）
            self.driver.moveR(x, y, True)
        else:
            # ② Windows SendInput（切换测试用）
            _send_input_move(x, y)

    def _shoot(self):
        """执行点击（真实按下释放时长模拟）"""
        import random
        # 1. 扳机反应延迟 (Trigger Delay)
        # 准星虽然到了头上，但真人开枪往往有几十毫秒的确认延迟
        time.sleep(random.uniform(0.01, 0.05))
        
        self.driver.mouse_down(1)
        
        # 2. 按键保持时长 (Click Duration)
        # 真人点击鼠标左键，绝对按压时间通常在 30ms 到 80ms 之间，绝不是瞬间发生
        click_duration = random.uniform(0.03, 0.08)
        time.sleep(click_duration)
        
        self.driver.mouse_up(1)

    def press(self, code):
        self.driver.mouse_down(code)

    def release(self, code):
        self.driver.mouse_up(code)

