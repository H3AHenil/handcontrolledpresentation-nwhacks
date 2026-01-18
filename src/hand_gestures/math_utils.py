"""Vector and geometry utility functions."""

import math

Point2 = tuple[int, int]
Point3 = tuple[float, float, float]
Vec3 = tuple[float, float, float]


def dist2(a: Point2, b: Point2) -> float:
    """Euclidean distance between 2D points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist3(a: Point3, b: Point3) -> float:
    """Euclidean distance between 3D points."""
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2)


def clamp(v: float, lo: float, hi: float) -> float:
    """Clamp value to range [lo, hi]."""
    return max(lo, min(hi, v))


def mean_point2(points: list[Point2]) -> Point2:
    """Average of 2D points, returns integer coordinates."""
    x = sum(p[0] for p in points) / len(points)
    y = sum(p[1] for p in points) / len(points)
    return (int(x), int(y))


def mean_point3(points: list[Point3]) -> Point3:
    """Average of 3D points."""
    n = len(points)
    return (
        sum(p[0] for p in points) / n,
        sum(p[1] for p in points) / n,
        sum(p[2] for p in points) / n,
    )


def sub3(a: Vec3, b: Vec3) -> Vec3:
    """Vector subtraction: a - b."""
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def dot3(a: Vec3, b: Vec3) -> float:
    """Dot product of 3D vectors."""
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross3(a: Vec3, b: Vec3) -> Vec3:
    """Cross product of 3D vectors."""
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def norm3(a: Vec3) -> float:
    """Magnitude of 3D vector (with epsilon to avoid division by zero)."""
    return math.sqrt(dot3(a, a)) + 1e-9


def normalize3(a: Vec3) -> Vec3:
    """Normalize 3D vector to unit length."""
    n = norm3(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def angle_3pt_deg(a: Point3, b: Point3, c: Point3) -> float:
    """Angle at point B formed by points A-B-C, in degrees."""
    ba = sub3(a, b)
    bc = sub3(c, b)
    cos_ang = clamp(dot3(ba, bc) / (norm3(ba) * norm3(bc)), -1.0, 1.0)
    return math.degrees(math.acos(cos_ang))


def wrap_deg(angle: float) -> float:
    """Wrap angle to [-180, 180] range."""
    return (angle + 180.0) % 360.0 - 180.0


def angle_delta_deg(a0: float, a1: float) -> float:
    """Signed angular difference between two angles."""
    return wrap_deg(a1 - a0)


def yaw_pitch_from_vec(vx: float, vy: float, vz: float) -> tuple[float, float]:
    """Extract yaw and pitch angles from direction vector."""
    forward = max(1e-6, -vz)
    yaw = math.degrees(math.atan2(vx, forward))
    pitch = math.degrees(math.atan2(-vy, forward))
    return yaw, pitch


def update_hysteresis(active: bool, value: float, on_thr: float, off_thr: float) -> bool:
    """Hysteresis-based state update to prevent flickering."""
    if not active:
        return value <= on_thr
    return not (value >= off_thr)
