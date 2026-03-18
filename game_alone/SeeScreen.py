import time
import winsound
from PIL import ImageGrab
import numpy as np
import cv2

from game_alone.MouseUtils import MouseUtils
from game_alone.ScreenOverlay import TransparentOverlay
from game_alone.YoloHead import YoloHead


class SeeScreen:
    def __init__(self, config):
        self.config = config
        self.width = self.config.width
        self.height = self.config.height
        self.fps = self.config.fps
        self.screen_center = None

        if not self.screen_center:
            self.get_screen_center()
        self.yolo = YoloHead(self.config.model_path, (self.width, self.height), self.config)
        self.mouse = MouseUtils(self.config.ads)
        self.start_monitoring()

    def get_screen_center(self):
        """获取屏幕中心的坐标"""
        screen = ImageGrab.grab()
        screen_width, screen_height = screen.size
        center_x = screen_width // 2
        center_y = screen_height // 2
        self.screen_center = (center_x, center_y)

        self.frame_count = 0
        self.start_time = time.time()

    def capture_center_area(self):
        """捕获屏幕中心指定宽度和高度的区域"""
        if not self.screen_center:
            self.get_screen_center()
        center_x, center_y = self.screen_center
        left = center_x - self.width // 2
        top = center_y - self.height // 2
        right = center_x + self.width // 2
        bottom = center_y + self.height // 2
        # 截取屏幕中心区域
        screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
        return screenshot

    def start_monitoring(self):
        """实时监视屏幕中央区域"""
        print("join")
        
        while not self.config.isDes:
            screenshot = self.capture_center_area()
            frame = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGR2RGB)

            if self.config.isStarted:
                pre = self.yolo.call(frame)
                
                # 把画好框的画面存进共享内存（为了效率，先转成 JPG 字节流，避免跨进程传巨大 numpy 数组）
                # 注意 YOLO deal 返回的 frame 已经是画了框的图像
                _, img_encoded = cv2.imencode('.jpg', pre["frame"], [cv2.IMWRITE_JPEG_QUALITY, 60])
                self.config.set_frame_data(img_encoded.tobytes())

                if pre["shoot"]:
                    self.mouse.move(pre["x"], pre["y"])
                    if "head_rect" in pre:
                        self.config.set_head_rect(pre["head_rect"])
                else:
                    self.config.set_head_rect(None)
            else:
                self.config.set_head_rect(None)
                self.config.set_frame_data(None)

            # 计算 FPS
            self.frame_count += 1
            elapsed_time = time.time() - self.start_time
            if elapsed_time >= 1:
                fps = self.frame_count / elapsed_time
                self.config.shared_config["fps_current"] = fps
                self.frame_count = 0
                self.start_time = time.time()

