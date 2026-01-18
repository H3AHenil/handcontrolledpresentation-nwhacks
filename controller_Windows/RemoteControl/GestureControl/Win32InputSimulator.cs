using System;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Low-level Win32 API wrapper for input simulation using P/Invoke.
/// Provides methods for cursor control, mouse events, keyboard events, and system actions.
/// </summary>
public static class Win32InputSimulator
{
    #region P/Invoke Declarations
    
    // ==================== user32.dll imports ====================
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool SetCursorPos(int X, int Y);
    
    [DllImport("user32.dll", SetLastError = true)]
    public static extern bool GetCursorPos(out POINT lpPoint);
    
    [DllImport("user32.dll")]
    private static extern void mouse_event(uint dwFlags, int dx, int dy, int dwData, IntPtr dwExtraInfo);
    
    [DllImport("user32.dll")]
    private static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, IntPtr dwExtraInfo);
    
    [DllImport("user32.dll")]
    private static extern int GetSystemMetrics(int nIndex);
    
    [DllImport("user32.dll")]
    private static extern IntPtr GetForegroundWindow();
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern uint SendInput(uint nInputs, INPUT[] pInputs, int cbSize);
    
    [DllImport("user32.dll")]
    private static extern IntPtr GetMessageExtraInfo();
    
    [DllImport("user32.dll")]
    private static extern int ShowCursor(bool bShow);
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr LoadCursor(IntPtr hInstance, int lpCursorName);
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr SetCursor(IntPtr hCursor);
    
    [DllImport("user32.dll")]
    private static extern bool ClipCursor(ref RECT lpRect);
    
    [DllImport("user32.dll")]
    private static extern bool ClipCursor(IntPtr lpRect);
    
    #endregion
    
    #region Constants
    
    // Mouse event flags
    private const uint MOUSEEVENTF_MOVE = 0x0001;
    private const uint MOUSEEVENTF_LEFTDOWN = 0x0002;
    private const uint MOUSEEVENTF_LEFTUP = 0x0004;
    private const uint MOUSEEVENTF_RIGHTDOWN = 0x0008;
    private const uint MOUSEEVENTF_RIGHTUP = 0x0010;
    private const uint MOUSEEVENTF_MIDDLEDOWN = 0x0020;
    private const uint MOUSEEVENTF_MIDDLEUP = 0x0040;
    private const uint MOUSEEVENTF_WHEEL = 0x0800;
    private const uint MOUSEEVENTF_HWHEEL = 0x1000;
    private const uint MOUSEEVENTF_ABSOLUTE = 0x8000;
    
    // Keyboard event flags
    private const uint KEYEVENTF_KEYDOWN = 0x0000;
    private const uint KEYEVENTF_KEYUP = 0x0002;
    private const uint KEYEVENTF_EXTENDEDKEY = 0x0001;
    
    // Virtual key codes
    private const byte VK_CONTROL = 0x11;
    private const byte VK_MENU = 0x12;     // Alt key
    private const byte VK_TAB = 0x09;
    private const byte VK_LWIN = 0x5B;
    private const byte VK_ESCAPE = 0x1B;
    private const byte VK_SHIFT = 0x10;
    
    // System metrics
    private const int SM_CXSCREEN = 0;
    private const int SM_CYSCREEN = 1;
    private const int SM_CXVIRTUALSCREEN = 78;
    private const int SM_CYVIRTUALSCREEN = 79;
    private const int SM_XVIRTUALSCREEN = 76;
    private const int SM_YVIRTUALSCREEN = 77;
    
    // Mouse wheel delta (standard Windows value)
    public const int WHEEL_DELTA = 120;
    
    // SendInput constants
    private const int INPUT_MOUSE = 0;
    private const int INPUT_KEYBOARD = 1;
    
    #endregion
    
    #region Structures
    
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
    }
    
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }
    
    [StructLayout(LayoutKind.Sequential)]
    private struct INPUT
    {
        public int type;
        public INPUTUNION union;
    }
    
    [StructLayout(LayoutKind.Explicit)]
    private struct INPUTUNION
    {
        [FieldOffset(0)] public MOUSEINPUT mi;
        [FieldOffset(0)] public KEYBDINPUT ki;
    }
    
    [StructLayout(LayoutKind.Sequential)]
    private struct MOUSEINPUT
    {
        public int dx;
        public int dy;
        public int mouseData;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }
    
    [StructLayout(LayoutKind.Sequential)]
    private struct KEYBDINPUT
    {
        public ushort wVk;
        public ushort wScan;
        public uint dwFlags;
        public uint time;
        public IntPtr dwExtraInfo;
    }
    
    #endregion
    
    #region Screen Information
    
    /// <summary>
    /// Gets the primary screen width.
    /// </summary>
    public static int ScreenWidth => GetSystemMetrics(SM_CXSCREEN);
    
    /// <summary>
    /// Gets the primary screen height.
    /// </summary>
    public static int ScreenHeight => GetSystemMetrics(SM_CYSCREEN);
    
    /// <summary>
    /// Gets the virtual screen width (all monitors combined).
    /// </summary>
    public static int VirtualScreenWidth => GetSystemMetrics(SM_CXVIRTUALSCREEN);
    
    /// <summary>
    /// Gets the virtual screen height (all monitors combined).
    /// </summary>
    public static int VirtualScreenHeight => GetSystemMetrics(SM_CYVIRTUALSCREEN);
    
    /// <summary>
    /// Gets the virtual screen left offset.
    /// </summary>
    public static int VirtualScreenLeft => GetSystemMetrics(SM_XVIRTUALSCREEN);
    
    /// <summary>
    /// Gets the virtual screen top offset.
    /// </summary>
    public static int VirtualScreenTop => GetSystemMetrics(SM_YVIRTUALSCREEN);
    
    #endregion
    
    #region Cursor Control
    
    /// <summary>
    /// Sets the cursor to an absolute screen position.
    /// </summary>
    /// <param name="x">X coordinate in screen pixels</param>
    /// <param name="y">Y coordinate in screen pixels</param>
    /// <returns>True if successful</returns>
    public static bool SetCursorPosition(int x, int y)
    {
        return SetCursorPos(x, y);
    }
    
    /// <summary>
    /// Sets the cursor position using normalized coordinates.
    /// </summary>
    /// <param name="normalizedX">X position [0, 1] where 0=left, 1=right</param>
    /// <param name="normalizedY">Y position [0, 1] where 0=top, 1=bottom</param>
    /// <returns>True if successful</returns>
    public static bool SetCursorPositionNormalized(float normalizedX, float normalizedY)
    {
        // Clamp to valid range
        normalizedX = Math.Clamp(normalizedX, 0f, 1f);
        normalizedY = Math.Clamp(normalizedY, 0f, 1f);
        
        int x = (int)(normalizedX * ScreenWidth);
        int y = (int)(normalizedY * ScreenHeight);
        
        return SetCursorPos(x, y);
    }
    
    /// <summary>
    /// Gets the current cursor position.
    /// </summary>
    /// <param name="x">Output X coordinate</param>
    /// <param name="y">Output Y coordinate</param>
    /// <returns>True if successful</returns>
    public static bool GetCursorPosition(out int x, out int y)
    {
        if (GetCursorPos(out POINT point))
        {
            x = point.X;
            y = point.Y;
            return true;
        }
        x = y = 0;
        return false;
    }
    
    /// <summary>
    /// Moves the cursor by a relative offset.
    /// </summary>
    /// <param name="deltaX">Horizontal offset</param>
    /// <param name="deltaY">Vertical offset</param>
    public static void MoveCursorRelative(int deltaX, int deltaY)
    {
        mouse_event(MOUSEEVENTF_MOVE, deltaX, deltaY, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Shows or hides the system cursor.
    /// </summary>
    /// <param name="show">True to show, false to hide</param>
    /// <returns>Display counter value</returns>
    public static int SetCursorVisibility(bool show)
    {
        return ShowCursor(show);
    }
    
    #endregion
    
    #region Mouse Buttons
    
    /// <summary>
    /// Simulates a left mouse button press (down only).
    /// </summary>
    public static void LeftMouseDown()
    {
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a left mouse button release (up only).
    /// </summary>
    public static void LeftMouseUp()
    {
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a complete left click (down + up).
    /// </summary>
    public static void LeftClick()
    {
        mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, IntPtr.Zero);
        mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a right mouse button press (down only).
    /// </summary>
    public static void RightMouseDown()
    {
        mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a right mouse button release (up only).
    /// </summary>
    public static void RightMouseUp()
    {
        mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a complete right click (down + up).
    /// </summary>
    public static void RightClick()
    {
        mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, IntPtr.Zero);
        mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a middle mouse button press (down only).
    /// </summary>
    public static void MiddleMouseDown()
    {
        mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a middle mouse button release (up only).
    /// </summary>
    public static void MiddleMouseUp()
    {
        mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, IntPtr.Zero);
    }
    
    #endregion
    
    #region Mouse Wheel
    
    /// <summary>
    /// Simulates a vertical mouse wheel scroll.
    /// </summary>
    /// <param name="delta">Scroll amount. Positive = up, negative = down. One notch = 120 (WHEEL_DELTA)</param>
    public static void ScrollVertical(int delta)
    {
        mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates a horizontal mouse wheel scroll.
    /// </summary>
    /// <param name="delta">Scroll amount. Positive = right, negative = left. One notch = 120 (WHEEL_DELTA)</param>
    public static void ScrollHorizontal(int delta)
    {
        mouse_event(MOUSEEVENTF_HWHEEL, 0, 0, delta, IntPtr.Zero);
    }
    
    /// <summary>
    /// Simulates Ctrl + Mouse Wheel for zoom operations.
    /// </summary>
    /// <param name="steps">Number of wheel steps. Positive = zoom in, negative = zoom out</param>
    public static void ZoomWithCtrlWheel(int steps)
    {
        if (steps == 0) return;
        
        // Clamp to reasonable range
        steps = Math.Clamp(steps, -50, 50);
        
        // Press Ctrl
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
        
        try
        {
            // Scroll wheel
            ScrollVertical(steps * WHEEL_DELTA);
        }
        finally
        {
            // Release Ctrl
            keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        }
    }
    
    #endregion
    
    #region Keyboard
    
    /// <summary>
    /// Presses a key down.
    /// </summary>
    /// <param name="virtualKeyCode">Virtual key code</param>
    /// <param name="extended">True if the key is an extended key</param>
    public static void KeyDown(byte virtualKeyCode, bool extended = false)
    {
        uint flags = KEYEVENTF_KEYDOWN;
        if (extended) flags |= KEYEVENTF_EXTENDEDKEY;
        keybd_event(virtualKeyCode, 0, flags, IntPtr.Zero);
    }
    
    /// <summary>
    /// Releases a key.
    /// </summary>
    /// <param name="virtualKeyCode">Virtual key code</param>
    /// <param name="extended">True if the key is an extended key</param>
    public static void KeyUp(byte virtualKeyCode, bool extended = false)
    {
        uint flags = KEYEVENTF_KEYUP;
        if (extended) flags |= KEYEVENTF_EXTENDEDKEY;
        keybd_event(virtualKeyCode, 0, flags, IntPtr.Zero);
    }
    
    /// <summary>
    /// Presses and releases a key.
    /// </summary>
    /// <param name="virtualKeyCode">Virtual key code</param>
    /// <param name="extended">True if the key is an extended key</param>
    public static void KeyPress(byte virtualKeyCode, bool extended = false)
    {
        KeyDown(virtualKeyCode, extended);
        KeyUp(virtualKeyCode, extended);
    }
    
    #endregion
    
    #region System Actions
    
    /// <summary>
    /// Triggers Alt+Tab for application switching.
    /// </summary>
    /// <param name="reverse">True for Shift+Alt+Tab (reverse direction)</param>
    public static void TriggerAltTab(bool reverse = false)
    {
        // Press Alt
        keybd_event(VK_MENU, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
        
        try
        {
            if (reverse)
            {
                // Press Shift for reverse
                keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
            }
            
            // Press Tab
            keybd_event(VK_TAB, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
            keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
            
            if (reverse)
            {
                // Release Shift
                keybd_event(VK_SHIFT, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
            }
        }
        finally
        {
            // Release Alt
            keybd_event(VK_MENU, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        }
    }
    
    /// <summary>
    /// Triggers Win+Tab for Task View.
    /// </summary>
    public static void TriggerWinTab()
    {
        // Press Win
        keybd_event(VK_LWIN, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
        
        try
        {
            // Press Tab
            keybd_event(VK_TAB, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
            keybd_event(VK_TAB, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        }
        finally
        {
            // Release Win
            keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
        }
    }
    
    /// <summary>
    /// Cancels any ongoing Alt+Tab or Win+Tab session.
    /// </summary>
    public static void CancelTaskSwitcher()
    {
        keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYDOWN, IntPtr.Zero);
        keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, IntPtr.Zero);
    }
    
    #endregion
}
