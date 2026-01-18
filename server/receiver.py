import cv2
import socket
import numpy as np
import struct
import time
from typing import Dict, Generator, Optional, TypedDict, Tuple
from dataclasses import dataclass


# ==========================================
# Part 1: Utility Functions (Fixed Crop Logic)
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
    """
    [Fixed] Simple center crop.
    For fisheye lens, we use simple linear ratio instead of tan() to prevent the image from becoming a narrow strip.
    """
    if target_hfov_deg <= 0 or target_hfov_deg >= original_hfov_deg:
        return frame_bgr

    h, w = frame_bgr.shape[:2]

    # Fix: Use linear ratio calculation (Target / Original)
    # If target is 100 degrees and original is 160 degrees, keep the middle 100/160 = 62.5% width
    scale = target_hfov_deg / original_hfov_deg

    keep_w = int(w * scale)
    keep_w = max(1, min(w, keep_w))

    x0 = (w - keep_w) // 2
    return frame_bgr[:, x0:x0 + keep_w]


# ==========================================
# Part 2: UDP Core Logic
# ==========================================

PORT = 9999


class _FrameBuffer(TypedDict):
    chunks: Dict[int, bytes]
    total: int
    time: float


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
        wide_angle_crop: bool = False,  # Crop disabled by default
        target_hfov_deg: float = 100.0,
        original_hfov_deg: float = 160.0,
) -> Generator[np.ndarray, None, None]:
    buffer: Dict[int, _FrameBuffer] = {}

    while True:
        try:
            data, _addr = sock.recvfrom(packet_size)
        except OSError:
            continue

        if len(data) < 3: continue

        frame_id, packet_id, total_packets = struct.unpack("BBB", data[:3])
        payload = data[3:]

        if frame_id not in buffer:
            buffer[frame_id] = _FrameBuffer(chunks={}, total=int(total_packets), time=time.time())

        chunks = buffer[frame_id]['chunks']
        chunks[int(packet_id)] = payload

        if len(chunks) == buffer[frame_id]['total']:
            sorted_chunks = [chunks[i] for i in range(buffer[frame_id]['total']) if i in chunks]

            if len(sorted_chunks) == buffer[frame_id]['total']:
                full_data = b''.join(sorted_chunks)
                np_arr = np.frombuffer(full_data, np.uint8)
                img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

                if img is not None:
                    # Only crop if wide_angle_crop is True
                    if wide_angle_crop:
                        img = approximate_fov_crop(img, target_hfov_deg, original_hfov_deg=original_hfov_deg)
                    yield img

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
# Part 3: Main Program (Configuration)
# ==========================================

if __name__ == "__main__":
    sock = create_udp_socket(PORT)
    print(f"✅ Listening on port {PORT}...")
    print(f"📺 Mode: Full Wide-Angle Raw Image (No Crop)")
    print("Press 'q' to exit.")

    try:
        # Core fix: Set wide_angle_crop=False
        stream_gen = frames_from_udp(
            sock,
            wide_angle_crop=False,  # <--- Set to False to ensure full frame
            original_hfov_deg=160.0
        )

        for frame in stream_gen:
            # Resize for display convenience on computer screen (optional)
            display_frame = cv2.resize(frame, (820, 616))

            cv2.imshow('Wide Angle Stream', display_frame)

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
        cv2.destroyAllWindows()