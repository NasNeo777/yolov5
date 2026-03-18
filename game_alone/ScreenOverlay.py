import tkinter as tk
from PIL import Image, ImageTk
import cv2
import numpy as np
import ctypes
import io

# ─── Win32 DPI Awareness ───
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

class TransparentOverlay:
    """
    基于 Tkinter 的透明覆盖层。
    使用 -transparentcolor 实现极致透明和点击穿透。
    """
    def __init__(self, config):
        self.config = config
        self.root = tk.Tk()
        
        # 1. 获取屏幕尺寸
        self.screen_w = self.root.winfo_screenwidth()
        self.screen_h = self.root.winfo_screenheight()
        
        # 2. 窗口设置
        self.root.geometry(f"{self.screen_w}x{self.screen_h}+0+0")
        self.root.overrideredirect(True)  # 无边框
        self.root.attributes("-topmost", True)  # 置顶
        self.root.attributes("-transparentcolor", "black")  # 黑色背景透明
        self.root.configure(bg="black")
        
        # 3. 画布设置
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        
        # 4. 识别区域红框 (静态或动态)
        self.rect_x1 = (self.screen_w - config.width) // 2
        self.rect_y1 = (self.screen_h - config.height) // 2
        self.rect_x2 = self.rect_x1 + config.width
        self.rect_y2 = self.rect_y1 + config.height
        
        self.red_rect = self.canvas.create_rectangle(
            self.rect_x1, self.rect_y1, self.rect_x2, self.rect_y2, 
            outline="#FF3232", width=3
        )
        
        # 5. 状态文字
        self.status_text_id = self.canvas.create_text(
            15, 15, text="", fill="#32DC32", font=("微软雅黑", 12, "bold"), anchor="nw"
        )
        
        # 6. 头部瞄准框 (动态持有 ID)
        self.head_rect_id = None
        
        # 7. 画中画 (PiP) 显示组件
        self.pip_image_id = None
        self.pip_photo = None  # 必须持久引用 PhotoImage 否则会被垃圾回收
        self.pip_bg_id = None

        self.interval_ms = int(1000 / config.fps)
        self._update_loop()
        self.root.mainloop()

    def _update_loop(self):
        if self.config.isDes:
            self.root.destroy()
            return

        # --- 1. 更新状态文字 ---
        status = "Start" if self.config.isStarted else "Pause"
        fps_curr = self.config.shared_config.get("fps_current", 0)
        fps_str = f"{fps_curr:.1f}" if isinstance(fps_curr, float) else str(fps_curr)
        self.canvas.itemconfig(self.status_text_id, text=f" {status}  FPS: {fps_str} ")

        # --- 2. 更新头部瞄准框 ---
        head_data = self.config.shared_config.get("head_rect", None)
        if head_data and self.config.isStarted:
            hx1, hy1, hx2, hy2 = head_data
            # 还原到全屏坐标
            hx1 += self.rect_x1
            hy1 += self.rect_y1
            hx2 += self.rect_x1
            hy2 += self.rect_y1
            
            if self.head_rect_id:
                self.canvas.coords(self.head_rect_id, hx1, hy1, hx2, hy2)
            else:
                self.head_rect_id = self.canvas.create_rectangle(
                    hx1, hy1, hx2, hy2, outline="#FFDC00", width=2
                )
        else:
            if self.head_rect_id:
                self.canvas.delete(self.head_rect_id)
                self.head_rect_id = None

        # --- 3. 更新画中画 (PiP) ---
        frame_data = self.config.shared_config.get("frame_data", None)
        if frame_data and self.config.isStarted:
            try:
                # 字节流转 PIL
                image = Image.open(io.BytesIO(frame_data))
                
                # 缩放
                pip_w = 320
                ratio = pip_w / image.width
                pip_h = int(image.height * ratio)
                image = image.resize((pip_w, pip_h), Image.Resampling.LANCZOS)
                
                # 转为 PhotoImage
                self.pip_photo = ImageTk.PhotoImage(image)
                
                pip_x = 20
                pip_y = self.screen_h - pip_h - 20
                
                # 绘制/更新 背景框
                if not self.pip_bg_id:
                    self.pip_bg_id = self.canvas.create_rectangle(
                        pip_x-4, pip_y-4, pip_x+pip_w+4, pip_y+pip_h+4, fill="#323232", outline=""
                    )
                else:
                    self.canvas.coords(self.pip_bg_id, pip_x-4, pip_y-4, pip_x+pip_w+4, pip_y+pip_h+4)

                # 绘制/更新 图片
                if not self.pip_image_id:
                    self.pip_image_id = self.canvas.create_image(pip_x, pip_y, anchor="nw", image=self.pip_photo)
                else:
                    self.canvas.itemconfig(self.pip_image_id, image=self.pip_photo)
                    self.canvas.coords(self.pip_image_id, pip_x, pip_y)

            except Exception:
                pass
        else:
            if self.pip_image_id:
                self.canvas.delete(self.pip_image_id)
                self.pip_image_id = None
            if self.pip_bg_id:
                self.canvas.delete(self.pip_bg_id)
                self.pip_bg_id = None

        # 保持置顶（强化置顶逻辑，防止被抢占）
        self.root.attributes("-topmost", True)
        
        self.root.after(self.interval_ms, self._update_loop)

    def close_overlay(self):
        if self.root:
            self.root.destroy()
