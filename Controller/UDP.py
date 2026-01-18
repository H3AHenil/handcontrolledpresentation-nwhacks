import socket
from typing import Literal


class UDPRemoteController:
    """UDP 远程控制器 Python 接口"""

    def __init__(self, port: int = 8080, broadcast_addr: str = "255.255.255.255"):
        self.port = port
        self.broadcast_addr = broadcast_addr
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    def _send(self, command: str):
        """发送命令"""
        self.sock.sendto(command.encode('utf-8'), (self.broadcast_addr, self.port))

    def set_port(self, port: int):
        """更改端口"""
        self.port = port

    # 点击操作
    def left_click(self):
        """左键点击"""
        self._send("LeftClick")

    def right_click(self):
        """右键点击"""
        self._send("RightClick")

    # 移动操作
    def move_relative(self, dx: int, dy: int):
        """相对移动"""
        self._send(f"Move:{dx},{dy}")

    def move_absolute(self, screen: int, x: int, y: int):
        """绝对移动到指定屏幕的坐标"""
        self._send(f"Abs:{screen},{x},{y}")

    # 滚轮操作
    def scroll(self, delta: int):
        """滚轮滚动，正值向上，负值向下"""
        self._send(f"Scroll:{delta}")

    # 缩放操作
    def zoom(self, steps: int):
        """缩放（Ctrl+滚轮），正值放大，负值缩小"""
        self._send(f"Zoom:{steps}")

    def zoom_in(self, steps: int = 1):
        """放大"""
        self.zoom(steps)

    def zoom_out(self, steps: int = 1):
        """缩小"""
        self.zoom(-steps)

    # 捏合手势
    def pinch(self, direction: Literal["in", "out"], steps: int):
        """
        捏合手势缩放
        :param direction: "in" 缩小, "out" 放大
        :param steps: 强度/步数
        """
        dir_value = 1 if direction == "out" else -1
        self._send(f"Pinch:{dir_value},{steps}")

    def pinch_in(self, steps: int = 1):
        """捏合缩小"""
        self.pinch("in", steps)

    def pinch_out(self, steps: int = 1):
        """捏合放大"""
        self.pinch("out", steps)

    def send_raw(self, command: str):
        """发送原始协议命令"""
        self._send(command)

    def close(self):
        """关闭连接"""
        self.sock.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
