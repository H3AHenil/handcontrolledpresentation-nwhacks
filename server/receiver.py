import cv2
import socket
import numpy as np
import struct
import time
import threading
from typing import Dict, Optional, Tuple, TypedDict, Union
from dataclasses import dataclass


# ==========================================
# Part 1: 必要工具函数 (Utility Functions)
# ==========================================

@dataclass(frozen=True)
class FisheyeCalibration:
    K: np.ndarray
    D: np.ndarray


def undistort_fisheye(frame_bgr: np.ndarray, calib: FisheyeCalibration, *, balance: float = 0.0,
                      new_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
    """鱼眼畸变矫正 (如果需要使用，请在主循环中定义 K 和 D)"""
    h, w = frame_bgr.shape[:2]
    if new_size is None:
        new_w, new_h = w, h
    else:
        new_w, new_h = new_size
    K = np.asarray(calib.K, dtype=np.float64)
    D = np.asarray(calib.D, dtype=np.float64).reshape(-1, 1)
    new_K = cv2.fisheye.estimateNewCameraMatrixForUndistortRectify(K, D, (w, h), np.eye(3), balance=balance,
                                                                   new_size=(new_w, new_h))
    map1, map2 = cv2.fisheye.initUndistortRectifyMap(K, D, np.eye(3), new_K, (new_w, new_h), cv2.CV_16SC2)
    return cv2.remap(frame_bgr, map1, map2, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT)


def approximate_fov_crop(frame_bgr: np.ndarray, target_hfov_deg: float, *,
                         original_hfov_deg: float = 160.0) -> np.ndarray:
    """线性广角裁剪 (防止竖条问题)"""
    if target_hfov_deg <= 0 or target_hfov_deg >= original_hfov_deg:
        return frame_bgr

    h, w = frame_bgr.shape[:2]
    scale = target_hfov_deg / original_hfov_deg
    keep_w = int(w * scale)
    keep_w = max(1, min(w, keep_w))
    x0 = (w - keep_w) // 2
    return frame_bgr[:, x0:x0 + keep_w]


# ==========================================
# Part 2: 多线程接收核心 (Threaded Receiver)
# ==========================================

PORT = 9999


class FrameBuffer(TypedDict):
    chunks: Dict[int, bytes]
    total: int
    probe_ts: float
    create_time: float


class LowLatencyReceiver:
    def __init__(self, port: int = PORT, wide_angle_crop: bool = False):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Allow reuse of address/port even if in TIME_WAIT state
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('0.0.0.0', port))
        # 4MB receive buffer to prevent packet loss at system level
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4 * 1024 * 1024)

        # 共享数据: (图像帧, 延迟ms)
        self.latest_bundle: Optional[Tuple[np.ndarray, float]] = None
        self.lock = threading.Lock()
        self.running = True

        # 配置
        self.wide_angle_crop = wide_angle_crop

        # 启动后台接收线程
        self.thread = threading.Thread(target=self._receive_worker)
        self.thread.daemon = True
        self.thread.start()
        print(f"🚀 低延迟接收线程已启动 (端口 {port})")

    def _receive_worker(self):
        """
        后台线程工作逻辑：
        1. 循环收包
        2. 解析探针 (Probe)
        3. 拼包 & 解码
        4. 执行裁剪 (可选)
        5. 更新最新帧 (丢弃旧帧)
        """
        buffer: Dict[int, FrameBuffer] = {}

        while self.running:
            try:
                # 阻塞接收 (不会卡主界面)
                data, _ = self.sock.recvfrom(65536)

                # --- 协议头智能解析 ---
                has_probe = False
                ts = 0.0
                frame_id = 0
                packet_id = 0
                total_packets = 0
                payload = b''

                # 尝试解析 11字节头 (探针模式: double + 3 bytes)
                if len(data) >= 11:
                    try:
                        ts_val, fid, pid, total = struct.unpack("dBBB", data[:11])
                        # 简单验证时间戳是否合理 (比如大于2020年的时间戳)
                        if ts_val > 1600000000:
                            ts = ts_val
                            frame_id, packet_id, total_packets = fid, pid, total
                            payload = data[11:]
                            has_probe = True
                    except:
                        pass

                # 如果不是探针，尝试解析 3字节头 (普通模式)
                if not has_probe:
                    if len(data) >= 3:
                        frame_id, packet_id, total_packets = struct.unpack("BBB", data[:3])
                        payload = data[3:]
                    else:
                        continue
                # -----------------------

                if frame_id not in buffer:
                    buffer[frame_id] = {
                        'chunks': {},
                        'total': int(total_packets),
                        'probe_ts': 0.0,
                        'create_time': time.time()
                    }

                # 记录该帧的时间戳 (取收到的第一个带探针的包)
                if has_probe and buffer[frame_id]['probe_ts'] == 0.0:
                    buffer[frame_id]['probe_ts'] = ts

                buffer[frame_id]['chunks'][int(packet_id)] = payload

                # 检查帧是否完整
                if len(buffer[frame_id]['chunks']) == buffer[frame_id]['total']:
                    # 按顺序拼接
                    sorted_chunks = [buffer[frame_id]['chunks'][i] for i in range(buffer[frame_id]['total']) if
                                     i in buffer[frame_id]['chunks']]

                    if len(sorted_chunks) == buffer[frame_id]['total']:
                        full_data = b''.join(sorted_chunks)
                        np_arr = np.frombuffer(full_data, np.uint8)

                        # 解码 (OpenCV C++底层，速度极快)
                        frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                        if frame is not None:
                            # 1. 执行必要的功能：裁剪 (如果在主线程做会增加显示延迟，所以在这里做)
                            if self.wide_angle_crop:
                                frame = approximate_fov_crop(frame, target_hfov_deg=100.0, original_hfov_deg=160.0)

                            # 2. 计算延迟
                            latency = -1.0
                            send_ts = buffer[frame_id]['probe_ts']
                            if send_ts > 0.0:
                                # 延迟 = 当前接收时间 - 发送时间
                                latency = (time.time() - send_ts) * 1000.0

                            # 3. 线程安全地更新最新帧
                            with self.lock:
                                self.latest_bundle = (frame, latency)

                    # 激进清理：拼完一帧后清空 Buffer，防止积压
                    buffer.clear()

                # 垃圾回收：清理超过 0.5s 的陈旧数据
                now = time.time()
                to_del = [fid for fid in buffer if now - buffer[fid]['create_time'] > 0.5]
                for fid in to_del: del buffer[fid]

            except Exception:
                continue

    def get_latest(self) -> Tuple[Optional[np.ndarray], float]:
        """主线程调用：获取当前最新的一帧"""
        with self.lock:
            if self.latest_bundle:
                return self.latest_bundle
            return None, -1.0

    def stop(self):
        self.running = False
        self.sock.close()


# ==========================================
# Part 3: 主程序 (渲染与显示)
# ==========================================

if __name__ == "__main__":
    # 初始化接收器
    # wide_angle_crop=False 表示保留全广角 (1640x1232 或 820x616)
    receiver = LowLatencyReceiver(PORT, wide_angle_crop=False)

    print(f"✅ 接收端就绪 (多线程优化 + 探针支持)")
    print(f"📺 等待 1640x1232 或 820x616 视频流...")

    try:
        while True:
            # 1. 获取最新帧 (非阻塞，瞬间完成)
            frame, latency = receiver.get_latest()

            if frame is not None:
                # 2. 渲染探针信息 (HUD)
                text_color = (0, 255, 0)  # 绿色
                info_text = "Latency: N/A"

                if latency >= 0:
                    info_text = f"Lat: {latency:.1f} ms"
                    # 根据延迟变色
                    if latency > 100:
                        text_color = (0, 0, 255)  # 红
                    elif latency > 50:
                        text_color = (0, 255, 255)  # 黄

                # 绘制黑色背景框 + 文字
                cv2.rectangle(frame, (5, 5), (240, 45), (0, 0, 0), -1)
                cv2.putText(frame, info_text, (15, 35), cv2.FONT_HERSHEY_SIMPLEX,
                            0.8, text_color, 2)

                # 3. 显示
                # 为了在电脑屏幕上看不撑满，可以缩放显示 (这不影响原始数据)
                # 如果是 1640x1232，建议缩小一半看；如果是 820x616，可以直接看
                display_h, display_w = frame.shape[:2]
                if display_w > 1000:
                    display_frame = cv2.resize(frame, (display_w // 2, display_h // 2))
                else:
                    display_frame = frame

                cv2.imshow('Ultra Low Latency Stream', display_frame)

            # 4. 响应按键 (因为有后台接收线程，这里的 waitKey 不会造成网络拥堵)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        pass
    finally:
        receiver.stop()
        cv2.destroyAllWindows()