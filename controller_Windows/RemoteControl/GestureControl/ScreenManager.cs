using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Provides information about connected monitors/screens.
/// </summary>
public static class ScreenManager
{
    #region Win32 Interop
    
    [DllImport("user32.dll")]
    private static extern bool EnumDisplayMonitors(IntPtr hdc, IntPtr lprcClip, MonitorEnumProc lpfnEnum, IntPtr dwData);
    
    private delegate bool MonitorEnumProc(IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData);
    
    [DllImport("user32.dll", CharSet = CharSet.Auto)]
    private static extern bool GetMonitorInfo(IntPtr hMonitor, ref MONITORINFOEX lpmi);
    
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
    /// Represents information about a single screen/monitor.
    /// </summary>
    public record ScreenInfo
    {
        /// <summary>
        /// Zero-based index of the screen.
        /// </summary>
        public int Index { get; init; }
        
        /// <summary>
        /// Device name (e.g., "\\.\DISPLAY1").
        /// </summary>
        public string DeviceName { get; init; } = string.Empty;
        
        /// <summary>
        /// Whether this is the primary monitor.
        /// </summary>
        public bool IsPrimary { get; init; }
        
        /// <summary>
        /// Screen bounds in virtual desktop coordinates.
        /// </summary>
        public RECT Bounds { get; init; }
        
        /// <summary>
        /// Working area (excluding taskbar) in virtual desktop coordinates.
        /// </summary>
        public RECT WorkArea { get; init; }
        
        /// <summary>
        /// Screen width in pixels.
        /// </summary>
        public int Width => Bounds.Width;
        
        /// <summary>
        /// Screen height in pixels.
        /// </summary>
        public int Height => Bounds.Height;
        
        /// <summary>
        /// Left coordinate in virtual desktop.
        /// </summary>
        public int Left => Bounds.Left;
        
        /// <summary>
        /// Top coordinate in virtual desktop.
        /// </summary>
        public int Top => Bounds.Top;
        
        public override string ToString() => 
            $"Screen {Index}: {DeviceName} ({Width}x{Height}) at ({Left},{Top}){(IsPrimary ? " [Primary]" : "")}";
    }
    
    private static List<ScreenInfo>? _cachedScreens;
    private static DateTime _lastRefresh = DateTime.MinValue;
    private static readonly TimeSpan CacheExpiry = TimeSpan.FromSeconds(5);
    
    /// <summary>
    /// Gets all available screens. Results are cached for 5 seconds.
    /// </summary>
    public static IReadOnlyList<ScreenInfo> GetAllScreens(bool forceRefresh = false)
    {
        if (!forceRefresh && _cachedScreens != null && DateTime.UtcNow - _lastRefresh < CacheExpiry)
        {
            return _cachedScreens;
        }
        
        var screens = new List<ScreenInfo>();
        int index = 0;
        
        EnumDisplayMonitors(IntPtr.Zero, IntPtr.Zero, (IntPtr hMonitor, IntPtr hdcMonitor, ref RECT lprcMonitor, IntPtr dwData) =>
        {
            var mi = new MONITORINFOEX { cbSize = Marshal.SizeOf<MONITORINFOEX>() };
            if (GetMonitorInfo(hMonitor, ref mi))
            {
                screens.Add(new ScreenInfo
                {
                    Index = index,
                    DeviceName = mi.szDevice,
                    IsPrimary = (mi.dwFlags & MONITORINFOF_PRIMARY) != 0,
                    Bounds = mi.rcMonitor,
                    WorkArea = mi.rcWork
                });
                index++;
            }
            return true;
        }, IntPtr.Zero);
        
        // Sort so primary is first, then by left position
        screens.Sort((a, b) =>
        {
            if (a.IsPrimary && !b.IsPrimary) return -1;
            if (!a.IsPrimary && b.IsPrimary) return 1;
            return a.Left.CompareTo(b.Left);
        });
        
        // Re-index after sorting
        for (int i = 0; i < screens.Count; i++)
        {
            screens[i] = screens[i] with { Index = i };
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
    /// Gets the primary screen.
    /// </summary>
    public static ScreenInfo? PrimaryScreen => GetAllScreens().Count > 0 ? GetAllScreens()[0] : null;
    
    /// <summary>
    /// Gets a screen by index. Returns null if index is out of range.
    /// </summary>
    public static ScreenInfo? GetScreen(int index)
    {
        var screens = GetAllScreens();
        return index >= 0 && index < screens.Count ? screens[index] : null;
    }
    
    /// <summary>
    /// Converts normalized coordinates [0,1] to screen coordinates for a specific screen.
    /// </summary>
    /// <param name="screenIndex">Index of the target screen</param>
    /// <param name="normalizedX">X coordinate [0,1]</param>
    /// <param name="normalizedY">Y coordinate [0,1]</param>
    /// <param name="screenX">Output screen X coordinate</param>
    /// <param name="screenY">Output screen Y coordinate</param>
    /// <returns>True if successful, false if screen not found</returns>
    public static bool NormalizedToScreen(int screenIndex, float normalizedX, float normalizedY, 
                                          out int screenX, out int screenY)
    {
        var screen = GetScreen(screenIndex);
        if (screen == null)
        {
            screenX = screenY = 0;
            return false;
        }
        
        normalizedX = Math.Clamp(normalizedX, 0f, 1f);
        normalizedY = Math.Clamp(normalizedY, 0f, 1f);
        
        screenX = screen.Left + (int)(normalizedX * screen.Width);
        screenY = screen.Top + (int)(normalizedY * screen.Height);
        
        return true;
    }
    
    /// <summary>
    /// Clears the screen cache, forcing a refresh on next call.
    /// </summary>
    public static void RefreshCache()
    {
        _cachedScreens = null;
    }
}
