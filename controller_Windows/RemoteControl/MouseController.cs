using System;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl;

public class MouseController
{
    // Import user32.dll
    [DllImport("user32.dll")]
    private static extern void mouse_event(uint dwFlags, int dx, int dy, uint dwData, int dwExtraInfo);

    [DllImport("user32.dll")]
    private static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern bool GetCursorPos(out POINT lpPoint);

    // Keyboard events (used for Ctrl + wheel zoom)
    [DllImport("user32.dll")]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const byte VK_CONTROL = 0x11;

    // Mouse event constants
    private const uint MOUSEEVENTF_MOVE = 0x0001;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;
    private const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    private const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    private const uint MOUSEEVENTF_ABSOLUTE = 0x8000;
    private const uint MOUSEEVENTF_WHEEL = 0x0800;

    // Windows standard wheel delta per tick
    private const int WHEEL_DELTA = 120;

    // Coordinate struct
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
    }

    [DllImport("user32.dll")]
    private static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumProc lpfnEnum, IntPtr dwData);

    private delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);

    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFOEX lpmi);

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Auto)]
    private struct MONITORINFOEX
    {
        public int cbSize;
        public RECT rcMonitor;
        public RECT rcWork;
        public uint dwFlags;

        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string szDevice;
    }

    private static bool TryGetMonitorRectByIndex(int index, out RECT rect)
    {
        rect = default;
        if (index < 0) return false;

        var current = 0;
        var found = false;
        var resultRect = default(RECT);

        bool Callback(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData)
        {
            if (current == index)
            {
                var mi = new MONITORINFOEX { cbSize = Marshal.SizeOf<MONITORINFOEX>() };
                if (GetMonitorInfo(hMonitor, ref mi))
                {
                    resultRect = mi.rcMonitor;
                    found = true;
                    return false; // stop
                }
            }

            current++;
            return true;
        }

        EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, Callback, IntPtr.Zero);
        if (!found) return false;

        rect = resultRect;
        return true;
    }

    /// <summary>
    /// Simulate relative mouse movement (trackpad-like behavior).
    /// </summary>
    /// <param name="deltaX">Delta on the X axis</param>
    /// <param name="deltaY">Delta on the Y axis</param>
    public static void MoveRelative(int deltaX, int deltaY)
    {
        mouse_event(MOUSEEVENTF_MOVE, deltaX, deltaY, 0, 0);
    }

    /// <summary>
    /// Simulate absolute mouse positioning (tablet / mapping mode).
    /// </summary>
    public static void MoveAbsolute(int x, int y)
    {
        SetCursorPos(x, y);
    }

    /// <summary>
    /// Absolute positioning by screen index.
    /// screenIndex: 0,1,2... (enumeration order depends on Windows)
    /// x/y are pixel coordinates within that screen (0..width-1 / 0..height-1).
    /// </summary>
    public static void MoveAbsoluteOnScreen(int screenIndex, int x, int y)
    {
        if (!TryGetMonitorRectByIndex(screenIndex, out var rect))
        {
            // If the screen is not found, fall back to virtual desktop coordinates
            MoveAbsolute(x, y);
            return;
        }

        // Clamp to screen bounds
        var width = rect.Right - rect.Left;
        var height = rect.Bottom - rect.Top;
        if (width <= 0 || height <= 0)
        {
            MoveAbsolute(x, y);
            return;
        }

        x = Math.Clamp(x, 0, width - 1);
        y = Math.Clamp(y, 0, height - 1);

        var vx = rect.Left + x;
        var vy = rect.Top + y;
        MoveAbsolute(vx, vy);
    }

    /// <summary>
    /// Simulate a left click.
    /// </summary>
    public static void LeftClick()
    {
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0);
    }

    /// <summary>
    /// Simulate a right click.
    /// </summary>
    public static void RightClick()
    {
        mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0);
        mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0);
    }

    /// <summary>
    /// Simulate a mouse wheel scroll.
    /// </summary>
    /// <param name="scrollAmount">Positive = up, negative = down (typically 120 per notch)</param>
    public static void Scroll(int scrollAmount)
    {
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, (uint)scrollAmount, 0);
    }

    /// <summary>
    /// Simulate "zoom" via Ctrl + wheel.
    /// Many apps (browsers/images/Office/etc.) map Ctrl+Wheel to zoom in/out.
    /// </summary>
    /// <param name="steps">Wheel steps: &gt;0 zoom in (wheel up), &lt;0 zoom out (wheel down)</param>
    public static void Zoom(int steps)
    {
        if (steps == 0) return;

        // Avoid sending an excessively large value in one go
        steps = Math.Clamp(steps, -50, 50);

        // Hold Ctrl
        keybd_event(VK_CONTROL, 0, 0, UIntPtr.Zero);
        try
        {
            Scroll(steps * WHEEL_DELTA);
        }
        finally
        {
            // Release Ctrl
            keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
        }
    }

    public static bool PinchZoomGesture(int direction, int steps)
    {
        // Use current mouse cursor position as the pinch center
        // (most apps zoom around the pointer)
        if (!GetCursorPos(out var pt))
            return false;

        // Touch injection requires screen coordinates (virtual desktop)
        direction = direction >= 0 ? 1 : -1;
        steps = Math.Clamp(steps, 1, 50);

        return TouchInjection.InjectPinchAtScreenPoint(pt.X, pt.Y, direction, steps);
    }
}