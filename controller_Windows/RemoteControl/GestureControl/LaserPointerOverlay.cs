using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Animation;
using System.Windows.Shapes;
using System.Windows.Threading;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// A transparent, click-through overlay window that displays a laser pointer with trail effect.
/// The window is topmost and allows mouse clicks to pass through to underlying windows.
/// Supports targeting a specific screen in multi-monitor setups.
/// </summary>
public class LaserPointerOverlay : Window
{
    #region Win32 Interop for Click-Through
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern int GetWindowLong(IntPtr hWnd, int nIndex);
    
    [DllImport("user32.dll", SetLastError = true)]
    private static extern int SetWindowLong(IntPtr hWnd, int nIndex, int dwNewLong);
    
    private const int GWL_EXSTYLE = -20;
    private const int WS_EX_TRANSPARENT = 0x00000020;
    private const int WS_EX_LAYERED = 0x00080000;
    private const int WS_EX_TOOLWINDOW = 0x00000080;
    private const int WS_EX_NOACTIVATE = 0x08000000;
    
    #endregion
    
    #region Configuration
    
    /// <summary>
    /// Radius of the main laser dot.
    /// </summary>
    public double DotRadius { get; set; } = 15.0;
    
    /// <summary>
    /// Color of the laser pointer.
    /// </summary>
    public Color LaserColor { get; set; } = Colors.Red;
    
    /// <summary>
    /// Maximum number of trail points to keep.
    /// </summary>
    public int MaxTrailPoints { get; set; } = 30;
    
    /// <summary>
    /// How fast the trail fades (in milliseconds).
    /// </summary>
    public double TrailFadeTime { get; set; } = 300.0;
    
    /// <summary>
    /// Minimum distance between trail points (to avoid excessive points when moving slowly).
    /// </summary>
    public double MinTrailPointDistance { get; set; } = 3.0;
    
    /// <summary>
    /// Gets or sets the target screen index (-1 for all screens/virtual desktop).
    /// </summary>
    public int TargetScreenIndex { get; private set; } = -1;
    
    /// <summary>
    /// Gets the current target screen info, or null if targeting all screens.
    /// </summary>
    public DpiAwareScreenManager.ScreenInfo? TargetScreenDpi { get; private set; }
    
    /// <summary>
    /// Gets the current target screen info (legacy), or null if targeting all screens.
    /// </summary>
    public ScreenManager.ScreenInfo? TargetScreen { get; private set; }
    
    #endregion
    
    #region Private Fields
    
    private readonly Canvas _canvas;
    private readonly Ellipse _mainDot;
    private readonly List<TrailPoint> _trailPoints = new();
    private readonly DispatcherTimer _updateTimer;
    private Point _currentPosition;
    private Point _lastTrailPosition;
    
    #endregion
    
    #region Nested Types
    
    private class TrailPoint
    {
        public Ellipse Shape { get; init; } = null!;
        public DateTime CreatedAt { get; init; }
        public Point Position { get; init; }
    }
    
    #endregion
    
    /// <summary>
    /// Creates a new LaserPointerOverlay instance targeting all screens.
    /// </summary>
    public LaserPointerOverlay() : this(-1)
    {
    }
    
    /// <summary>
    /// Creates a new LaserPointerOverlay instance targeting a specific screen.
    /// </summary>
    /// <param name="screenIndex">Target screen index (-1 for all screens)</param>
    public LaserPointerOverlay(int screenIndex)
    {
        // Window setup for transparent overlay
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ResizeMode = ResizeMode.NoResize;
        
        // Set target screen
        SetTargetScreen(screenIndex);
        
        // Create canvas for drawing
        _canvas = new Canvas
        {
            Background = Brushes.Transparent,
            ClipToBounds = false
        };
        Content = _canvas;
        
        // Create main laser dot with glow effect
        _mainDot = CreateLaserDot(DotRadius, 1.0);
        _canvas.Children.Add(_mainDot);
        
        // Timer for updating trail fade effects
        _updateTimer = new DispatcherTimer
        {
            Interval = TimeSpan.FromMilliseconds(16) // ~60 FPS
        };
        _updateTimer.Tick += OnUpdateTimerTick;
        
        // Handle source initialization for click-through
        SourceInitialized += OnSourceInitialized;
        
        // Initialize position
        _currentPosition = new Point(Width / 2, Height / 2);
        _lastTrailPosition = _currentPosition;
    }
    
    /// <summary>
    /// Sets the target screen for the overlay.
    /// </summary>
    /// <param name="screenIndex">Screen index (-1 for all screens/virtual desktop)</param>
    public void SetTargetScreen(int screenIndex)
    {
        TargetScreenIndex = screenIndex;
        TargetScreen = screenIndex >= 0 ? ScreenManager.GetScreen(screenIndex) : null;
        TargetScreenDpi = screenIndex >= 0 ? DpiAwareScreenManager.GetScreen(screenIndex) : null;
        
        UpdateWindowBounds();
    }
    
    /// <summary>
    /// Updates the window bounds based on the target screen.
    /// Uses logical coordinates (DPI-aware) for WPF positioning.
    /// </summary>
    private void UpdateWindowBounds()
    {
        if (TargetScreenDpi != null)
        {
            // Use logical coordinates for WPF (DPI-aware)
            Left = TargetScreenDpi.LogicalLeft;
            Top = TargetScreenDpi.LogicalTop;
            Width = TargetScreenDpi.LogicalWidth;
            Height = TargetScreenDpi.LogicalHeight;
        }
        else
        {
            // Cover entire virtual desktop (all monitors)
            // For virtual desktop, we need to calculate logical coordinates
            var primaryScreen = DpiAwareScreenManager.PrimaryScreen;
            double dpiScale = primaryScreen?.DpiScale ?? 1.0;
            
            Left = Win32InputSimulator.VirtualScreenLeft / dpiScale;
            Top = Win32InputSimulator.VirtualScreenTop / dpiScale;
            Width = Win32InputSimulator.VirtualScreenWidth / dpiScale;
            Height = Win32InputSimulator.VirtualScreenHeight / dpiScale;
        }
    }
    
    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        // Make the window click-through and non-activating
        var hwnd = new WindowInteropHelper(this).Handle;
        int extendedStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
        
        // Add WS_EX_TRANSPARENT for click-through
        // Add WS_EX_LAYERED for transparency
        // Add WS_EX_TOOLWINDOW to hide from Alt+Tab
        // Add WS_EX_NOACTIVATE to prevent focus stealing
        extendedStyle |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
        
        SetWindowLong(hwnd, GWL_EXSTYLE, extendedStyle);
    }
    
    /// <summary>
    /// Updates the laser pointer position.
    /// </summary>
    /// <param name="physicalX">X position in physical screen coordinates</param>
    /// <param name="physicalY">Y position in physical screen coordinates</param>
    public void UpdatePosition(int physicalX, int physicalY)
    {
        // Convert physical screen coordinates to logical window coordinates (DPI-aware)
        // WPF uses primary monitor's DPI for all window positioning
        double windowX, windowY;
        
        if (TargetScreenDpi != null)
        {
            // For specific screen, offset from that screen's physical origin
            // and convert to logical coordinates using PRIMARY DPI scale
            // (because WPF positions windows using primary monitor's DPI)
            double primaryDpiScale = TargetScreenDpi.PrimaryDpiScale;
            windowX = (physicalX - TargetScreenDpi.PhysicalLeft) / primaryDpiScale;
            windowY = (physicalY - TargetScreenDpi.PhysicalTop) / primaryDpiScale;
            
            // Clamp to logical screen bounds
            windowX = Math.Clamp(windowX, 0, TargetScreenDpi.LogicalWidth);
            windowY = Math.Clamp(windowY, 0, TargetScreenDpi.LogicalHeight);
        }
        else
        {
            // For virtual desktop, use primary screen's DPI for conversion
            var primaryScreen = DpiAwareScreenManager.PrimaryScreen;
            double primaryDpiScale = primaryScreen?.PrimaryDpiScale ?? 1.0;
            
            windowX = (physicalX - Win32InputSimulator.VirtualScreenLeft) / primaryDpiScale;
            windowY = (physicalY - Win32InputSimulator.VirtualScreenTop) / primaryDpiScale;
        }
        
        _currentPosition = new Point(windowX, windowY);
        
        // Add trail point if moved enough
        double distance = Math.Sqrt(
            Math.Pow(windowX - _lastTrailPosition.X, 2) + 
            Math.Pow(windowY - _lastTrailPosition.Y, 2));
        
        if (distance >= MinTrailPointDistance)
        {
            AddTrailPoint(windowX, windowY);
            _lastTrailPosition = new Point(windowX, windowY);
        }
        
        // Update main dot position (centered on the point)
        Canvas.SetLeft(_mainDot, windowX - DotRadius);
        Canvas.SetTop(_mainDot, windowY - DotRadius);
    }
    
    /// <summary>
    /// Updates the laser pointer position using normalized coordinates.
    /// Coordinates are relative to the target screen (or entire virtual desktop if no target).
    /// </summary>
    /// <param name="normalizedX">X position [0, 1]</param>
    /// <param name="normalizedY">Y position [0, 1]</param>
    public void UpdatePositionNormalized(float normalizedX, float normalizedY)
    {
        normalizedX = Math.Clamp(normalizedX, 0f, 1f);
        normalizedY = Math.Clamp(normalizedY, 0f, 1f);
        
        int physicalX, physicalY;
        
        if (TargetScreenDpi != null)
        {
            // Convert to physical coordinates on the target screen
            physicalX = TargetScreenDpi.PhysicalLeft + (int)(normalizedX * TargetScreenDpi.PhysicalWidth);
            physicalY = TargetScreenDpi.PhysicalTop + (int)(normalizedY * TargetScreenDpi.PhysicalHeight);
        }
        else
        {
            // Convert to virtual desktop physical coordinates
            physicalX = Win32InputSimulator.VirtualScreenLeft + 
                      (int)(normalizedX * Win32InputSimulator.VirtualScreenWidth);
            physicalY = Win32InputSimulator.VirtualScreenTop + 
                      (int)(normalizedY * Win32InputSimulator.VirtualScreenHeight);
        }
        
        UpdatePosition(physicalX, physicalY);
    }
    
    /// <summary>
    /// Updates the laser pointer position using normalized coordinates for a specific screen.
    /// </summary>
    /// <param name="normalizedX">X position [0, 1]</param>
    /// <param name="normalizedY">Y position [0, 1]</param>
    /// <param name="screenIndex">Target screen index</param>
    public void UpdatePositionNormalizedOnScreen(float normalizedX, float normalizedY, int screenIndex)
    {
        // Use DPI-aware conversion
        if (DpiAwareScreenManager.NormalizedToPhysical(screenIndex, normalizedX, normalizedY, 
                                                        out int physicalX, out int physicalY))
        {
            UpdatePosition(physicalX, physicalY);
        }
    }
    
    /// <summary>
    /// Shows the overlay and starts the animation timer.
    /// </summary>
    public new void Show()
    {
        // Refresh screen info in case resolution/monitors changed
        ScreenManager.RefreshCache();
        if (TargetScreenIndex >= 0)
        {
            TargetScreen = ScreenManager.GetScreen(TargetScreenIndex);
        }
        
        // Update window bounds
        UpdateWindowBounds();
        
        base.Show();
        _updateTimer.Start();
    }
    
    /// <summary>
    /// Shows the overlay on a specific screen.
    /// </summary>
    /// <param name="screenIndex">Screen index (-1 for all screens)</param>
    public void ShowOnScreen(int screenIndex)
    {
        SetTargetScreen(screenIndex);
        Show();
    }
    
    /// <summary>
    /// Hides the overlay and stops the animation timer.
    /// </summary>
    public new void Hide()
    {
        _updateTimer.Stop();
        ClearTrail();
        base.Hide();
    }
    
    /// <summary>
    /// Clears all trail points.
    /// </summary>
    public void ClearTrail()
    {
        foreach (var point in _trailPoints)
        {
            _canvas.Children.Remove(point.Shape);
        }
        _trailPoints.Clear();
    }
    
    private Ellipse CreateLaserDot(double radius, double opacity)
    {
        var dot = new Ellipse
        {
            Width = radius * 2,
            Height = radius * 2,
            Fill = new RadialGradientBrush
            {
                GradientOrigin = new Point(0.5, 0.5),
                Center = new Point(0.5, 0.5),
                RadiusX = 0.5,
                RadiusY = 0.5,
                GradientStops = new GradientStopCollection
                {
                    new GradientStop(Color.FromArgb((byte)(255 * opacity), LaserColor.R, LaserColor.G, LaserColor.B), 0.0),
                    new GradientStop(Color.FromArgb((byte)(200 * opacity), LaserColor.R, LaserColor.G, LaserColor.B), 0.4),
                    new GradientStop(Color.FromArgb((byte)(100 * opacity), LaserColor.R, LaserColor.G, LaserColor.B), 0.7),
                    new GradientStop(Color.FromArgb(0, LaserColor.R, LaserColor.G, LaserColor.B), 1.0)
                }
            },
            Opacity = opacity
        };
        
        // Add a subtle glow effect
        dot.Effect = new System.Windows.Media.Effects.DropShadowEffect
        {
            Color = LaserColor,
            BlurRadius = radius,
            ShadowDepth = 0,
            Opacity = 0.8
        };
        
        return dot;
    }
    
    private void AddTrailPoint(double x, double y)
    {
        // Create a smaller trail dot
        double trailRadius = DotRadius * 0.4;
        var trailDot = new Ellipse
        {
            Width = trailRadius * 2,
            Height = trailRadius * 2,
            Fill = new SolidColorBrush(LaserColor),
            Opacity = 0.7
        };
        
        Canvas.SetLeft(trailDot, x - trailRadius);
        Canvas.SetTop(trailDot, y - trailRadius);
        
        // Insert behind the main dot
        _canvas.Children.Insert(0, trailDot);
        
        var trailPoint = new TrailPoint
        {
            Shape = trailDot,
            CreatedAt = DateTime.UtcNow,
            Position = new Point(x, y)
        };
        
        _trailPoints.Add(trailPoint);
        
        // Remove old points if we have too many
        while (_trailPoints.Count > MaxTrailPoints)
        {
            var oldest = _trailPoints[0];
            _canvas.Children.Remove(oldest.Shape);
            _trailPoints.RemoveAt(0);
        }
    }
    
    private void OnUpdateTimerTick(object? sender, EventArgs e)
    {
        var now = DateTime.UtcNow;
        var pointsToRemove = new List<TrailPoint>();
        
        foreach (var point in _trailPoints)
        {
            double age = (now - point.CreatedAt).TotalMilliseconds;
            double fadeProgress = age / TrailFadeTime;
            
            if (fadeProgress >= 1.0)
            {
                // Mark for removal
                pointsToRemove.Add(point);
            }
            else
            {
                // Update opacity based on age
                point.Shape.Opacity = 0.7 * (1.0 - fadeProgress);
                
                // Also scale down as it fades
                double scale = 1.0 - (fadeProgress * 0.5);
                point.Shape.RenderTransform = new ScaleTransform(scale, scale, 
                    point.Shape.Width / 2, point.Shape.Height / 2);
            }
        }
        
        // Remove expired points
        foreach (var point in pointsToRemove)
        {
            _canvas.Children.Remove(point.Shape);
            _trailPoints.Remove(point);
        }
    }
    
    protected override void OnClosed(EventArgs e)
    {
        _updateTimer.Stop();
        base.OnClosed(e);
    }
}
