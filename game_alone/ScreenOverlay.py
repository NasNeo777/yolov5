import ctypes
import ctypes.wintypes as wintypes
import time
import pygame
import io
import cv2
import numpy as np

# ─── Win32 常量 ───────────────────────────────────────────────────────────────
WS_EX_LAYERED      = 0x00080000
WS_EX_TRANSPARENT  = 0x00000020
WS_EX_TOPMOST      = 0x00000008
WS_EX_TOOLWINDOW   = 0x00000080
WS_EX_NOACTIVATE   = 0x08000000
WS_POPUP           = 0x80000000

GWL_EXSTYLE        = -20
LWA_COLORKEY       = 0x00000001

SetWindowLong      = ctypes.windll.user32.SetWindowLongW
SetLayeredWindowAttributes = ctypes.windll.user32.SetLayeredWindowAttributes
GetSystemMetrics   = ctypes.windll.user32.GetSystemMetrics
SetProcessDPIAware = ctypes.windll.user32.SetProcessDPIAware

# 让当前进程 DPI 感知，避免坐标缩放问题
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        SetProcessDPIAware()
    except Exception:
        pass


# 透明色：纯黑 (0, 0, 0) 将被 Win32 设为 colorkey 透明
TRANSPARENT_COLOR = (0, 0, 0)
# 绘制颜色
RED   = (255,  50,  50)
GREEN = (50,  220,  50)
WHITE = (255, 255, 255)
YELLOW = (255, 220,  0)


class TransparentOverlay:
    """
    基于 pygame + Win32 Layered Window 的透明覆盖层。
    可在使命召唤等独占全屏游戏上方正常显示。
    """

    def __init__(self, config):
        self.config = config

        # ── 获取真实屏幕分辨率（DPI 感知后的物理像素）──
        self.screen_w = GetSystemMetrics(0)
        self.screen_h = GetSystemMetrics(1)

        # ── 识别区域在全屏中的起点 ──
        self.rect_x1 = (self.screen_w - config.width)  // 2
        self.rect_y1 = (self.screen_h - config.height) // 2
        self.rect_x2 = self.rect_x1 + config.width
        self.rect_y2 = self.rect_y1 + config.height

        self.frame_interval = 1.0 / config.fps

        # ── 初始化 pygame ──
        pygame.init()
        # NOFRAME + SHOWN，不要 FULLSCREEN（否则会抢占独占全屏）
        self.screen = pygame.display.set_mode(
            (self.screen_w, self.screen_h),
            pygame.NOFRAME
        )
        pygame.display.set_caption("overlay")

        # ── 拿到 pygame 窗口的 HWND ──
        import ctypes
        hwnd_info = pygame.display.get_wm_info()
        self.hwnd = hwnd_info["window"]

        # ── 设置 Win32 窗口样式：分层 + 透明点击穿透 + 置顶 + 不激活 ──
        ex_style = (WS_EX_LAYERED | WS_EX_TRANSPARENT |
                    WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE)
        SetWindowLong(self.hwnd, GWL_EXSTYLE, ex_style)

        # 把 TRANSPARENT_COLOR (0,0,0) 设为 colorkey 透明（alpha=0 表示不用整体透明度）
        colorkey_rgb = (
            TRANSPARENT_COLOR[2] |
            (TRANSPARENT_COLOR[1] << 8) |
            (TRANSPARENT_COLOR[0] << 16)
        )
        SetLayeredWindowAttributes(self.hwnd, colorkey_rgb, 0, LWA_COLORKEY)

        # ── 把窗口移到 (0,0) 并保持最顶 ──
        HWND_TOPMOST = -1
        SWP_NOMOVE = 0x0002
        SWP_NOSIZE = 0x0001
        ctypes.windll.user32.SetWindowPos(
            self.hwnd, HWND_TOPMOST, 0, 0,
            self.screen_w, self.screen_h,
            0
        )

        # ── 字体 ──
        self.font = pygame.font.SysFont("Arial", 20, bold=True)

        self._run()

    # ──────────────────────────────────────────────────────────────────────────
    def _run(self):
        clock = pygame.time.Clock()

        while not self.config.isDes:
            # 处理系统事件，否则窗口会无响应
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return

            self._draw()
            pygame.display.flip()
            clock.tick(self.config.fps)

        pygame.quit()

    # ──────────────────────────────────────────────────────────────────────────
    def _draw(self):
        # 用透明色填充背景（这部分会被 colorkey 变透明）
        self.screen.fill(TRANSPARENT_COLOR)

        # 1. 画识别区域红框（屏幕中心捕获区）
        pygame.draw.rect(
            self.screen, RED,
            pygame.Rect(self.rect_x1, self.rect_y1, self.config.width, self.config.height),
            3  # 边框宽度
        )

        # 2. 画头部瞄准框
        head_data = self.config.shared_config.get("head_rect", None)
        if head_data and self.config.isStarted:
            hx1, hy1, hx2, hy2 = head_data
            # head_data 坐标相对于截取区域，加上偏移还原到全屏坐标
            hx1 += self.rect_x1
            hy1 += self.rect_y1
            hx2 += self.rect_x1
            hy2 += self.rect_y1
            w = hx2 - hx1
            h = hy2 - hy1
            pygame.draw.rect(
                self.screen, YELLOW,
                pygame.Rect(hx1, hy1, w, h),
                2
            )

        # 3. 画中画 (Picture-in-Picture) 实时显示 AI 处理画面
        frame_data = self.config.shared_config.get("frame_data", None)
        if frame_data and self.config.isStarted:
            try:
                # 字节流转 numpy, 再解码回图像
                nparr = np.frombuffer(frame_data, np.uint8)
                frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if frame is not None:
                    # OpenCV 默认是 BGR，为了 Pygame 正常显示颜色需转为 RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    # 将 ndarray 转为 pygame.Surface
                    # cv2 图像 shape 是 (H, W, C)，pygame surfarray.make_surface 需要的是 (W, H, C)，所以做个转置
                    frame_surf = pygame.surfarray.make_surface(frame_rgb.swapaxes(0, 1))
                    
                    # 取缩小比例，比如宽度固定 320
                    pip_w = 320
                    ratio = pip_w / frame_surf.get_width()
                    pip_h = int(frame_surf.get_height() * ratio)
                    
                    pip_surf = pygame.transform.scale(frame_surf, (pip_w, pip_h))
                    
                    # 放在屏幕左下角
                    pip_x = 20
                    pip_y = self.screen_h - pip_h - 20
                    
                    # 画个背景框
                    pygame.draw.rect(self.screen, (50, 50, 50), (pip_x-4, pip_y-4, pip_w+8, pip_h+8))
                    self.screen.blit(pip_surf, (pip_x, pip_y))
            except Exception as e:
                pass

        # 4. 左上角状态文字
        status_text = self._get_status_text()
        text_surf = self.font.render(status_text, True, GREEN)
        # 防止文字背景色(0,0,0)被透明掉：给文字区域铺一层深灰底
        bg_rect = pygame.Rect(5, 5, text_surf.get_width() + 10, text_surf.get_height() + 6)
        pygame.draw.rect(self.screen, (20, 20, 20), bg_rect)
        self.screen.blit(text_surf, (10, 8))

    # ──────────────────────────────────────────────────────────────────────────
    def _get_status_text(self):
        status = "Start" if self.config.isStarted else "Pause"
        fps = self.config.shared_config.get("fps_current", 0)
        fps_str = f"{fps:.1f}" if isinstance(fps, float) else str(fps)
        return f" {status}  FPS: {fps_str} "

    # ──────────────────────────────────────────────────────────────────────────
    def close_overlay(self):
        pygame.quit()
