import time
import ctypes

# GetAsyncKeyState 通过轮询读取按键状态，不依赖 Windows Hook，
# 可以绕过独占全屏游戏（如 COD）对 keyboard hook 的屏蔽
GetAsyncKeyState = ctypes.windll.user32.GetAsyncKeyState

# 虚拟键码
VK_SHIFT      = 0x10
VK_F1         = 0x70
VK_F2         = 0x71
VK_F3         = 0x72
VK_END        = 0x23
VK_MBUTTON    = 0x04   # 鼠标中键


def _is_pressed(vk):
    """检测某个虚拟键是否刚被按下（最高位为1表示按下，最低位为1表示自上次调用被按过）"""
    return GetAsyncKeyState(vk) & 0x8001  # 0x8001 = 当前按下 OR 上次检查后按过


class ListenerKeybord:
    def __init__(self, config):
        self.config = config
        print("[Listener] 键盘监听启动 (GetAsyncKeyState 轮询模式)")
        print("[Listener] Shift / F3 = 启/停  |  F2 = 匪徒  |  F1 = 警察  |  End = 退出  |  鼠标中键 = 启/停")
        self.call()

    def call(self):
        # 用于记录上一帧各键的状态，实现"边沿触发"（只在按下瞬间触发一次）
        prev = {k: False for k in [VK_SHIFT, VK_F1, VK_F2, VK_F3, VK_END, VK_MBUTTON]}

        while not self.config.isDes:
            for vk, action in [
                (VK_SHIFT,   self.config.toogle),
                (VK_F3,      self.config.toogle),
                (VK_F2,      self.config.setRed),
                (VK_F1,      self.config.setBlue),
                (VK_END,     self.config.destroy),
                (VK_MBUTTON, self.config.toogle),
            ]:
                # 最高位为 1 表示当前按住
                curr = bool(GetAsyncKeyState(vk) & 0x8000)
                # 只在 False->True 边沿触发，防止长按触发多次
                if curr and not prev[vk]:
                    print(f"[Listener] 检测到按键 vk=0x{vk:02X}")
                    action()
                prev[vk] = curr

            time.sleep(0.02)   # 50 Hz 轮询，延迟约 20ms，对游戏来说足够快
