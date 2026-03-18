import sys
import ctypes
import multiprocessing
from multiprocessing import Process

from game_alone.ListenerKeybord import ListenerKeybord
from game_alone.NasGameConfig import NasGameConfig
from game_alone.ScreenOverlay import TransparentOverlay
from game_alone.SeeScreen import SeeScreen


def is_admin():
    """检查当前是否以管理员权限运行"""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def run_as_admin():
    """以管理员权限重新启动自身"""
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, " ".join(sys.argv), None, 1
    )


class BigBoss:
    def __init__(self):
        self.instance = NasGameConfig()

    def run(self):
        pk = Process(target=ListenerKeybord, args=(self.instance,), name='Keyboard')
        pl = Process(target=SeeScreen, args=(self.instance,), name='Loop')
        pt = Process(target=TransparentOverlay, args=(self.instance,), name='Rect')
        # 启动进程
        pk.start()
        pl.start()
        pt.start()
        # 等待进程完成
        pk.join()
        pl.join()
        pt.join()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    if not is_admin():
        print("未检测到管理员权限，正在请求提权...")
        run_as_admin()
        sys.exit()
    print("已以管理员权限运行")
    BigBoss().run()
