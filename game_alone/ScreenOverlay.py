import tkinter as tk


class TransparentOverlay:
    def __init__(self, config):
        self.root = tk.Tk()
        self.config = config
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")
        self.root.overrideredirect(True)  # 去除窗口装饰（边框、标题栏）
        self.root.attributes("-topmost", True)  # 窗口置顶
        self.root.attributes("-transparentcolor", "black")  # 设置黑色为透明
        self.root.configure(bg="black")  # 背景透明
        self.time = 1 / self.config.fps * 1000
        # 创建画布
        self.canvas = tk.Canvas(self.root, bg="black", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        # 全局参数
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()
        
        # 屏幕中心的识别区域边框
        self.rect_x1 = (self.screen_width - config.width) // 2
        self.rect_y1 = (self.screen_height - config.height) // 2
        self.rect_x2 = self.rect_x1 + config.width
        self.rect_y2 = self.rect_y1 + config.height

        self.canvas.create_rectangle(
            self.rect_x1, self.rect_y1, self.rect_x2, self.rect_y2, outline="red", width=5
        )

        # 创建动态标签（显示在左上角）
        self.label_text = self.canvas.create_text(
            10, 10,  # 左上角位置 (x, y)
            text="", fill="red", font=("Arial", 16), anchor="nw"  # anchor="nw" 设置左上对齐
        )
        
        # 记录头部框的 GUI 元素 ID
        self.head_rect_id = 0

        # 初始化标签
        self.update_ui()
        self.open_overlay()

    def get_label(self):
        if self.config.isRed:
            body = "是匪徒"
        else:
            body = "是警察"
        if self.config.isStarted:
            status = "启动"
        else:
            status = "暂停"
        return f" {status} fps: {self.config.fps_current}"

    def update_ui(self):
        # 1. 更新底部文字
        new_label = self.get_label()
        self.canvas.itemconfig(self.label_text, text=new_label)
        
        # 2. 更新头部瞄准区域的红框
        # YoloHead 返回的坐标是相对于截图区域（屏幕中心截取）的
        # 为了在全屏画布上画出它，需要加上识别区域左上角的偏移补偿
        head_data = self.config.shared_config.get("head_rect", None)
        
        # 如果当前有识别到目标并且存在之前的框，删掉它（为了重画活的）
        if self.head_rect_id != 0:
            self.canvas.delete(str(self.head_rect_id))
            self.head_rect_id = 0
            
        if head_data and self.config.isStarted:
            # head_data 是基于截图区域的 (x1, y1, x2, y2)
            # 所以加上 self.rect_x1 / self.rect_y1 (截取区域起点) 还原到全屏坐标系
            hx1, hy1, hx2, hy2 = head_data
            hx1 += self.rect_x1
            hx2 += self.rect_x1
            hy1 += self.rect_y1
            hy2 += self.rect_y1
            
            # 绘制红色的实心方块或红框
            self.head_rect_id = self.canvas.create_rectangle(
                hx1, hy1, hx2, hy2, outline="red", width=2
            )

        self.root.after(int(self.time), self.update_ui)  # 每秒60帧循环

    def open_overlay(self):
        self.root.mainloop()

    def close_overlay(self):
        """关闭窗口"""
        if self.root:
            self.root.destroy()

