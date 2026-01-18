using System;
using System.Collections.Generic;
using System.Linq;
using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Provides DPI-aware screen management for multi-monitor setups.
/// Handles the conversion between logical (WPF) and physical (screen) pixels.
/// </summary>
public static class DpiAwareScreenManager
{
    #region Win32 Interop
    
    [DllImport("user32.dll")]
    private static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumProc lpfnEnum, IntPtr dwData);
    
    private delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);
    
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFOEX lpmi);
    
    [DllImport("shcore.dll")]
    private static extern int GetDpiForMonitor(IntPtr hMonitor, MonitorDpiType dpiType, out uint dpiX, out uint dpiY);
    
    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromPoint(POINT pt, uint dwFlags);
    
    [DllImport("user32.dll")]
    private static extern IntPtr MonitorFromWindow(IntPtr hwnd, uint dwFlags);
    
    private const uint MONITOR_DEFAULTTONEAREST = 2;
    
    private enum MonitorDpiType
    {
        MDT_EFFECTIVE_DPI = 0,
        MDT_ANGULAR_DPI = 1,
        MDT_RAW_DPI = 2
    }
    
    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
        
        public int Width => Right - Left;
        public int Height => Bottom - Top;
    }
    
    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int X;
        public int Y;
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
    
    private const uint MONITORINFOF_PRIMARY = 1;
    
    #endregion
    
    /// <summary>
    /// Represents DPI-aware screen information.
    /// </summary>
    public class ScreenInfo
    {
        /// <summary>Zero-based index of the screen.</summary>
        public int Index { get; init; }
        
        /// <summary>Device name (e.g., "\\.\DISPLAY1").</summary>
        public string DeviceName { get; init; } = string.Empty;
        
        /// <summary>Whether this is the primary monitor.</summary>
        public bool IsPrimary { get; init; }
        
        /// <summary>Monitor handle.</summary>
        public IntPtr Handle { get; init; }
        
        /// <summary>Physical screen bounds (in physical pixels).</summary>
        public RECT PhysicalBounds { get; init; }
        
        /// <summary>Physical working area (in physical pixels).</summary>
        public RECT PhysicalWorkArea { get; init; }
        
        /// <summary>DPI scale factor (1.0 = 100%, 1.25 = 125%, 1.5 = 150%, etc.)</summary>
        public double DpiScale { get; init; }
        
        /// <summary>Horizontal DPI.</summary>
        public uint DpiX { get; init; }
        
        /// <summary>Vertical DPI.</summary>
        public uint DpiY { get; init; }
        
        /// <summary>Primary screen's DPI scale (used for WPF coordinate calculations).</summary>
        public double PrimaryDpiScale { get; init; } = 1.0;
        
        // Logical dimensions (for WPF) - uses primary monitor's DPI for positioning
        // because WPF uses the primary monitor's DPI as the base for all coordinates
        public double LogicalLeft => PhysicalBounds.Left / PrimaryDpiScale;
        public double LogicalTop => PhysicalBounds.Top / PrimaryDpiScale;
        public double LogicalWidth => PhysicalBounds.Width / PrimaryDpiScale;
        public double LogicalHeight => PhysicalBounds.Height / PrimaryDpiScale;
        
        // Physical dimensions
        public int PhysicalLeft => PhysicalBounds.Left;
        public int PhysicalTop => PhysicalBounds.Top;
        public int PhysicalWidth => PhysicalBounds.Width;
        public int PhysicalHeight => PhysicalBounds.Height;
        
        public override string ToString() => 
            $"Screen {Index}: {DeviceName} Physical({PhysicalWidth}x{PhysicalHeight}) @ ({PhysicalLeft},{PhysicalTop}) DPI:{DpiX} Scale:{DpiScale:P0}{(IsPrimary ? " [Primary]" : "")}";
    }
    
    private static List<ScreenInfo>? _cachedScreens;
    private static DateTime _lastRefresh = DateTime.MinValue;
    private static readonly TimeSpan CacheExpiry = TimeSpan.FromSeconds(2);
    
    /// <summary>
    /// Gets all available screens with DPI information.
    /// </summary>
    public static IReadOnlyList<ScreenInfo> GetAllScreens(bool forceRefresh = false)
    {
        if (!forceRefresh && _cachedScreens != null && DateTime.UtcNow - _lastRefresh < CacheExpiry)
        {
            return _cachedScreens;
        }
        
        var screens = new List<ScreenInfo>();
        var monitorHandles = new List<IntPtr>();
        
        // First pass: collect all monitor handles
        EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, (IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData) =>
        {
            monitorHandles.Add(hMonitor);
            return true;
        }, IntPtr.Zero);
        
        // Second pass: get detailed info for each monitor
        for (int i = 0; i < monitorHandles.Count; i++)
        {
            var hMonitor = monitorHandles[i];
            var mi = new MONITORINFOEX { cbSize = Marshal.SizeOf<MONITORINFOEX>() };
            
            if (GetMonitorInfo(hMonitor, ref mi))
            {
                // Get DPI for this monitor
                uint dpiX = 96, dpiY = 96;
                try
                {
                    GetDpiForMonitor(hMonitor, MonitorDpiType.MDT_EFFECTIVE_DPI, out dpiX, out dpiY);
                }
                catch
                {
                    // Fallback to 96 DPI if shcore.dll is not available
                }
                
                double dpiScale = dpiX / 96.0;
                
                screens.Add(new ScreenInfo
                {
                    Index = i,
                    DeviceName = mi.szDevice,
                    IsPrimary = (mi.dwFlags & MONITORINFOF_PRIMARY) != 0,
                    Handle = hMonitor,
                    PhysicalBounds = mi.rcMonitor,
                    PhysicalWorkArea = mi.rcWork,
                    DpiX = dpiX,
                    DpiY = dpiY,
                    DpiScale = dpiScale
                });
            }
        }
        
        // Sort: primary first, then by left position
        screens.Sort((a, b) =>
        {
            if (a.IsPrimary && !b.IsPrimary) return -1;
            if (!a.IsPrimary && b.IsPrimary) return 1;
            return a.PhysicalLeft.CompareTo(b.PhysicalLeft);
        });
        
        // Get primary screen's DPI scale (used for WPF coordinate conversion)
        double primaryDpiScale = screens.FirstOrDefault(s => s.IsPrimary)?.DpiScale ?? 1.0;
        
        // Re-index after sorting and set primary DPI scale
        for (int i = 0; i < screens.Count; i++)
        {
            var s = screens[i];
            screens[i] = new ScreenInfo
            {
                Index = i,
                DeviceName = s.DeviceName,
                IsPrimary = s.IsPrimary,
                Handle = s.Handle,
                PhysicalBounds = s.PhysicalBounds,
                PhysicalWorkArea = s.PhysicalWorkArea,
                DpiX = s.DpiX,
                DpiY = s.DpiY,
                DpiScale = s.DpiScale,
                PrimaryDpiScale = primaryDpiScale
            };
        }
        
        _cachedScreens = screens;
        _lastRefresh = DateTime.UtcNow;
        
        return screens;
    }
    
    /// <summary>
    /// Gets the number of screens.
    /// </summary>
    public static int ScreenCount => GetAllScreens().Count;
    
    /// <summary>
    /// Gets a screen by index.
    /// </summary>
    public static ScreenInfo? GetScreen(int index)
    {
        var screens = GetAllScreens();
        return index >= 0 && index < screens.Count ? screens[index] : null;
    }
    
    /// <summary>
    /// Gets the primary screen.
    /// </summary>
    public static ScreenInfo? PrimaryScreen => GetAllScreens().Count > 0 ? GetAllScreens()[0] : null;
    
    /// <summary>
    /// Converts normalized coordinates [0,1] to physical screen coordinates.
    /// </summary>
    public static bool NormalizedToPhysical(int screenIndex, float normalizedX, float normalizedY,
                                             out int physicalX, out int physicalY)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null)
        {
            physicalX = physicalY = 0;
            return false;
        }
        
        normalizedX = Math.Clamp(normalizedX, 0f, 1f);
        normalizedY = Math.Clamp(normalizedY, 0f, 1f);
        
        physicalX = screen.PhysicalLeft + (int)(normalizedX * screen.PhysicalWidth);
        physicalY = screen.PhysicalTop + (int)(normalizedY * screen.PhysicalHeight);
        
        return true;
    }
    
    /// <summary>
    /// Converts physical screen coordinates to logical (WPF) coordinates.
    /// </summary>
    public static void PhysicalToLogical(int screenIndex, int physicalX, int physicalY,
                                          out double logicalX, out double logicalY)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null)
        {
            logicalX = physicalX;
            logicalY = physicalY;
            return;
        }
        
        logicalX = physicalX / screen.DpiScale;
        logicalY = physicalY / screen.DpiScale;
    }
    
    /// <summary>
    /// Converts logical (WPF) coordinates to physical screen coordinates.
    /// </summary>
    public static void LogicalToPhysical(int screenIndex, double logicalX, double logicalY,
                                          out int physicalX, out int physicalY)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null)
        {
            physicalX = (int)logicalX;
            physicalY = (int)logicalY;
            return;
        }
        
        physicalX = (int)(logicalX * screen.DpiScale);
        physicalY = (int)(logicalY * screen.DpiScale);
    }
    
    /// <summary>
    /// Moves a WPF window to the specified screen, making it fullscreen and borderless.
    /// Properly handles DPI scaling.
    /// </summary>
    public static void MoveWindowToScreen(Window window, int screenIndex)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null) return;
        
        // Use logical coordinates for WPF
        window.Left = screen.LogicalLeft;
        window.Top = screen.LogicalTop;
        window.Width = screen.LogicalWidth;
        window.Height = screen.LogicalHeight;
    }
    
    /// <summary>
    /// Gets the logical bounds for a screen (for WPF positioning).
    /// </summary>
    public static Rect GetLogicalBounds(int screenIndex)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null) return Rect.Empty;
        
        return new Rect(screen.LogicalLeft, screen.LogicalTop, 
                       screen.LogicalWidth, screen.LogicalHeight);
    }
    
    /// <summary>
    /// Clears the screen cache.
    /// </summary>
    public static void RefreshCache()
    {
        _cachedScreens = null;
    }
}
