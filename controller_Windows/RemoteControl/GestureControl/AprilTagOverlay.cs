using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Shapes;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// An overlay window that displays AprilTags on the corners of a screen.
/// Used for camera-based screen detection and calibration.
/// </summary>
public class AprilTagOverlay : Window
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
    /// Size of each AprilTag in pixels.
    /// </summary>
    public int TagSize { get; set; } = 100;
    
    /// <summary>
    /// Margin from screen corners.
    /// </summary>
    public int CornerMargin { get; set; } = 20;
    
    /// <summary>
    /// Target screen index.
    /// </summary>
    public int TargetScreenIndex { get; private set; } = 0;
    
    /// <summary>
    /// Whether to make the window click-through.
    /// </summary>
    public bool IsClickThrough { get; set; } = true;
    
    #endregion
    
    private readonly Canvas _canvas;
    private ScreenManager.ScreenInfo? _targetScreen;
    private DpiAwareScreenManager.ScreenInfo? _targetScreenDpi;
    
    /// <summary>
    /// Creates a new AprilTagOverlay for the primary screen.
    /// </summary>
    public AprilTagOverlay() : this(0)
    {
    }
    
    /// <summary>
    /// Creates a new AprilTagOverlay for a specific screen.
    /// </summary>
    /// <param name="screenIndex">Target screen index</param>
    public AprilTagOverlay(int screenIndex)
    {
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ResizeMode = ResizeMode.NoResize;
        
        _canvas = new Canvas
        {
            Background = Brushes.Transparent
        };
        Content = _canvas;
        
        SourceInitialized += OnSourceInitialized;
        
        SetTargetScreen(screenIndex);
    }
    
    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        if (IsClickThrough)
        {
            var hwnd = new WindowInteropHelper(this).Handle;
            int extendedStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
            extendedStyle |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
            SetWindowLong(hwnd, GWL_EXSTYLE, extendedStyle);
        }
    }
    
    /// <summary>
    /// Sets the target screen for the overlay using DPI-aware positioning.
    /// </summary>
    public void SetTargetScreen(int screenIndex)
    {
        TargetScreenIndex = screenIndex;
        _targetScreen = ScreenManager.GetScreen(screenIndex);
        _targetScreenDpi = DpiAwareScreenManager.GetScreen(screenIndex);
        
        if (_targetScreenDpi != null)
        {
            // Use logical coordinates for WPF (DPI-aware)
            Left = _targetScreenDpi.LogicalLeft;
            Top = _targetScreenDpi.LogicalTop;
            Width = _targetScreenDpi.LogicalWidth;
            Height = _targetScreenDpi.LogicalHeight;
        }
        else
        {
            // Fallback to primary screen with DPI awareness
            var primaryScreen = DpiAwareScreenManager.PrimaryScreen;
            if (primaryScreen != null)
            {
                Left = primaryScreen.LogicalLeft;
                Top = primaryScreen.LogicalTop;
                Width = primaryScreen.LogicalWidth;
                Height = primaryScreen.LogicalHeight;
            }
            else
            {
                Left = 0;
                Top = 0;
                Width = Win32InputSimulator.ScreenWidth;
                Height = Win32InputSimulator.ScreenHeight;
            }
        }
    }
    
    /// <summary>
    /// Shows the overlay and draws the AprilTags.
    /// </summary>
    public new void Show()
    {
        ScreenManager.RefreshCache();
        _targetScreen = ScreenManager.GetScreen(TargetScreenIndex);
        SetTargetScreen(TargetScreenIndex);
        
        DrawAprilTags();
        base.Show();
    }
    
    /// <summary>
    /// Shows the overlay on a specific screen.
    /// </summary>
    public void ShowOnScreen(int screenIndex)
    {
        SetTargetScreen(screenIndex);
        Show();
    }
    
    private void DrawAprilTags()
    {
        _canvas.Children.Clear();
        
        double screenWidth = Width;
        double screenHeight = Height;
        
        // Draw AprilTag in each corner
        // Top-Left (ID: 0)
        DrawAprilTag(CornerMargin, CornerMargin, 0);
        
        // Top-Right (ID: 1)
        DrawAprilTag(screenWidth - TagSize - CornerMargin, CornerMargin, 1);
        
        // Bottom-Left (ID: 2)
        DrawAprilTag(CornerMargin, screenHeight - TagSize - CornerMargin, 2);
        
        // Bottom-Right (ID: 3)
        DrawAprilTag(screenWidth - TagSize - CornerMargin, screenHeight - TagSize - CornerMargin, 3);
    }
    
    private void DrawAprilTag(double x, double y, int tagId)
    {
        // Create a simple AprilTag-like pattern
        // This is a simplified 4x4 pattern for visual identification
        // Real AprilTags would use a proper encoding library
        
        var tagGrid = GetSimplifiedTagPattern(tagId);
        
        // Background border (white)
        var background = new Border
        {
            Width = TagSize,
            Height = TagSize,
            Background = Brushes.White,
            BorderBrush = Brushes.Black,
            BorderThickness = new Thickness(2)
        };
        Canvas.SetLeft(background, x);
        Canvas.SetTop(background, y);
        _canvas.Children.Add(background);
        
        // Draw the tag pattern
        int cellSize = (TagSize - 4) / 6; // 6x6 grid with border
        int offset = 2; // Border offset
        
        for (int row = 0; row < 6; row++)
        {
            for (int col = 0; col < 6; col++)
            {
                bool isBlack = false;
                
                // Outer border is always black
                if (row == 0 || row == 5 || col == 0 || col == 5)
                {
                    isBlack = true;
                }
                else
                {
                    // Inner 4x4 pattern based on tagId
                    int innerRow = row - 1;
                    int innerCol = col - 1;
                    isBlack = tagGrid[innerRow, innerCol];
                }
                
                if (isBlack)
                {
                    var cell = new Rectangle
                    {
                        Width = cellSize,
                        Height = cellSize,
                        Fill = Brushes.Black
                    };
                    Canvas.SetLeft(cell, x + offset + col * cellSize);
                    Canvas.SetTop(cell, y + offset + row * cellSize);
                    _canvas.Children.Add(cell);
                }
            }
        }
        
        // Add corner label
        var label = new TextBlock
        {
            Text = $"ID:{tagId}",
            FontSize = 10,
            Foreground = Brushes.Red,
            FontWeight = FontWeights.Bold,
            Background = new SolidColorBrush(Color.FromArgb(200, 255, 255, 255))
        };
        Canvas.SetLeft(label, x);
        Canvas.SetTop(label, y + TagSize + 2);
        _canvas.Children.Add(label);
    }
    
    /// <summary>
    /// Gets a simplified 4x4 pattern for the given tag ID.
    /// These are unique patterns for each corner.
    /// </summary>
    private bool[,] GetSimplifiedTagPattern(int tagId)
    {
        // Simple unique patterns for each corner
        return tagId switch
        {
            0 => new bool[,] // Top-Left
            {
                { true, true, false, false },
                { true, false, false, false },
                { false, false, false, true },
                { false, false, true, true }
            },
            1 => new bool[,] // Top-Right
            {
                { false, false, true, true },
                { false, false, false, true },
                { true, false, false, false },
                { true, true, false, false }
            },
            2 => new bool[,] // Bottom-Left
            {
                { false, false, true, true },
                { false, true, true, false },
                { false, true, true, false },
                { true, true, false, false }
            },
            3 => new bool[,] // Bottom-Right
            {
                { true, true, true, true },
                { true, false, false, true },
                { true, false, false, true },
                { true, true, true, true }
            },
            _ => new bool[,]
            {
                { true, false, true, false },
                { false, true, false, true },
                { true, false, true, false },
                { false, true, false, true }
            }
        };
    }
    
    /// <summary>
    /// Updates the tag size and redraws.
    /// </summary>
    public void SetTagSize(int size)
    {
        TagSize = size;
        if (IsVisible)
        {
            DrawAprilTags();
        }
    }
}
