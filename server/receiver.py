import cv2
import socket
import numpy as np
import struct
import time
from typing import Dict, Generator, Optional, TypedDict, Tuple, Union
from dataclasses import dataclass


# ==========================================
# Part 1: Utility Functions (保留原样)
# ==========================================

@dataclass(frozen=True)
class FisheyeCalibration:
    K: np.ndarray
    D: np.ndarray


def undistort_fisheye(frame_bgr: np.ndarray, calib: FisheyeCalibration, *, balance: float = 0.0,
                      new_size: Optional[Tuple[int, int]] = None) -> np.ndarray:
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
    if target_hfov_deg <= 0 or target_hfov_deg >= original_hfov_deg:
        return frame_bgr

    h, w = frame_bgr.shape[:2]
    scale = target_hfov_deg / original_hfov_deg
    keep_w = int(w * scale)
    keep_w = max(1, min(w, keep_w))
    x0 = (w - keep_w) // 2
    return frame_bgr[:, x0:x0 + keep_w]


# ==========================================
# Part 2: UDP Core Logic (增加探针处理)
# ==========================================

PORT = 9999


class _FrameBuffer(TypedDict):
    chunks: Dict[int, bytes]
    total: int
    time: float
    probe_ts: float  # 新增: 记录该帧的发送端时间戳


def create_udp_socket(port: int = PORT, rcvbuf_bytes: int = 4 * 1024 * 1024) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(('0.0.0.0', port))
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, int(rcvbuf_bytes))
    return sock


def frames_from_udp(
        sock: socket.socket,
        *,
        packet_size: int = 65536,
        frame_timeout_s: float = 1.0,
        drop_incomplete_on_yield: bool = True,
        wide_angle_crop: bool = False,
        target_hfov_deg: float = 100.0,
        original_hfov_deg: float = 160.0,
) -> Generator[Tuple[np.ndarray, float], None, None]:
    """
    修改后的 Generator:
    Yields:
        Tuple[np.ndarray, float]: (图像帧, 延迟毫秒数)
        如果未启用探针，延迟返回 -1.0
    """
    buffer: Dict[int, _FrameBuffer] = {}

    while True:
        try:
            data, _addr = sock.recvfrom(packet_size)
        except OSError:
            continue

        # ---------------------------------------------------------
        # 协议头解析逻辑 (自动兼容是否开启探针)
        # ---------------------------------------------------------
        # 情况 A: 带有探针 (8字节double + 3字节头 = 11字节)
        if len(data) >= 11:
            # 尝试解析前11个字节
            try:
                # 'd' = double (8 bytes), 'B' = unsigned char (1 byte)
                ts, frame_id, packet_id, total_packets = struct.unpack("dBBB", data[:11])
                payload = data[11:]
                has_probe = True
            except struct.error:
                # 解析失败，回退到情况 B
                has_probe = False

        # 情况 B: 无探针 (3字节头)
        if len(data) >= 3 and (not 'has_probe' in locals() or not has_probe):
            # 再次检查，防止误判
            # 如果C++没开探针，这里只有3字节头
            if len(data) < 11:
                frame_id, packet_id, total_packets = struct.unpack("BBB", data[:3])
                payload = data[3:]
                ts = 0.0
                has_probe = False
            else:
                # 这是一种罕见情况，可能包长度很大但不是探针，假设它是无探针模式
                frame_id, packet_id, total_packets = struct.unpack("BBB", data[:3])
                payload = data[3:]
                ts = 0.0
                has_probe = False

        if len(data) < 3: continue

        # ---------------------------------------------------------

        if frame_id not in buffer:
            # 初始化 buffer，记录 probe_ts (如果是该帧的第一个包)
            buffer[frame_id] = _FrameBuffer(
                chunks={},
                total=int(total_packets),
                time=time.time(),
                probe_ts=ts if has_probe else 0.0
            )

        # 如果当前包有时间戳且 buffer 里还没记录（或者更新为更精确的），可以更新
        if has_probe and buffer[frame_id]['probe_ts'] == 0.0:
            buffer[frame_id]['probe_ts'] = ts

        chunks = buffer[frame_id]['chunks']
        chunks[int(packet_id)] = payload

        if len(chunks) == buffer[frame_id]['total']:
            sorted_chunks = [chunks[i] for i in range(buffer[frame_id]['total']) if i in chunks]

            if len(sorted_chunks) == buffer[frame_id]['total']:
                full_data = b''.join(sorted_chunks)
                np_arr = np.frombuffer(full_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if img is not None:
                    if wide_angle_crop:
                        img = approximate_fov_crop(img, target_hfov_deg, original_hfov_deg=original_hfov_deg)

                    # --- 计算延迟 ---
                    latency = -1.0
                    send_ts = buffer[frame_id]['probe_ts']
                    if send_ts > 0.0:
                        # 延迟 = 当前接收时间 - 发送时间 (注意：需要设备时间大致同步)
                        # 如果是同一局域网，NTP误差通常在几毫秒内，或者只看相对波动
                        latency = (time.time() - send_ts) * 1000.0

                    yield img, latency

            if drop_incomplete_on_yield:
                buffer.clear()
            else:
                del buffer[frame_id]

        # Clean up old frames
        now = time.time()
        to_delete = [fid for fid, meta in buffer.items() if now - meta['time'] > frame_timeout_s]
        for fid in to_delete:
            del buffer[fid]


# ==========================================
# Part 3: Main Program (Rendering Probe Info)
# ==========================================

if __name__ == "__main__":
    sock = create_udp_socket(PORT)
    print(f"✅ Listening on port {PORT}...")
    print(f"📺 Mode: Full Wide-Angle (1640x1232)")
    print("Press 'q' to exit.")

    try:
        # 获取 generator
        stream_gen = frames_from_udp(
            sock,
            wide_angle_crop=False,
            original_hfov_deg=160.0
        )

        # 循环获取 (img, latency)
        for frame, latency in stream_gen:

            # --- 渲染探针信息 ---
            text_color = (0, 255, 0)  # 绿色
            info_text = "Latency: N/A"

            if latency >= 0:
                info_text = f"Latency: {latency:.1f} ms"
                # 如果延迟过高，变红
                if latency > 100:
                    text_color = (0, 0, 255)
                elif latency > 50:
                    text_color = (0, 255, 255)  # 黄色

            # 在左上角绘制黑色背景框以便阅读
            cv2.rectangle(frame, (5, 5), (220, 40), (0, 0, 0), -1)
            cv2.putText(frame, info_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, text_color, 2)

            # --- 显示 ---
            # Resize for display convenience (optional, to fit screen)
            display_frame = cv2.resize(frame, (820, 616))
            cv2.imshow('Wide Angle Stream', display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        cv2.destroyAllWindows()