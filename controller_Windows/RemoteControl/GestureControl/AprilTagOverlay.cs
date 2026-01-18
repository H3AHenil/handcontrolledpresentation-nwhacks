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
        
        // Calculate base tag ID for this screen (4 tags per screen)
        int baseId = TargetScreenIndex * 4;
        
        // Draw AprilTag in each corner (matching Python generate_tags.py)
        // Top-Left (ID: baseId + 0)
        DrawAprilTag(CornerMargin, CornerMargin, baseId + 0);
        
        // Top-Right (ID: baseId + 1)
        DrawAprilTag(screenWidth - TagSize - CornerMargin, CornerMargin, baseId + 1);
        
        // Bottom-Right (ID: baseId + 2)
        DrawAprilTag(screenWidth - TagSize - CornerMargin, screenHeight - TagSize - CornerMargin, baseId + 2);
        
        // Bottom-Left (ID: baseId + 3)
        DrawAprilTag(CornerMargin, screenHeight - TagSize - CornerMargin, baseId + 3);
    }
    
    private void DrawAprilTag(double x, double y, int tagId)
    {
        // Get the actual tag16h5 AprilTag pattern
        // These patterns match the Python generate_tags.py output
        
        var tagGrid = GetTag16h5Pattern(tagId);
        
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
    /// Gets the actual tag16h5 AprilTag pattern for the given tag ID.
    /// These patterns match the OpenCV/pupil-apriltags tag16h5 family.
    /// </summary>
    private bool[,] GetTag16h5Pattern(int tagId)
    {
        // Official AprilTag 16h5 family - 30 tags (0-29)
        // Source: https://github.com/AprilRobotics/apriltag/blob/master/tag16h5.c
        //
        // AprilTag 16h5 structure:
        // - Total grid: 6x6 cells
        // - Outer border: 1 cell black border (always black)
        // - Inner data: 4x4 cells (16 bits of data)
        //
        // The codes represent the 4x4 inner data area (16 bits)
        // 1 = black, 0 = white
        // Bit layout: MSB (bit 15) = top-left, LSB (bit 0) = bottom-right
        ushort[] tag16h5Codes = {
            0x231b, // Tag 0
            0x2ea5, // Tag 1
            0x346a, // Tag 2
            0x45b9, // Tag 3
            0x79a6, // Tag 4
            0x7f6b, // Tag 5
            0xb358, // Tag 6
            0xe745, // Tag 7
            0xfe59, // Tag 8
            0x156d, // Tag 9
            0x380b, // Tag 10
            0xf0ab, // Tag 11
            0x0d84, // Tag 12
            0x4736, // Tag 13
            0x8c72, // Tag 14
            0xaf10, // Tag 15
            0x093c, // Tag 16
            0x93b4, // Tag 17
            0xa503, // Tag 18
            0x468f, // Tag 19
            0xe137, // Tag 20
            0x5795, // Tag 21
            0xdf42, // Tag 22
            0x1c1d, // Tag 23
            0xe9dc, // Tag 24
            0x73ad, // Tag 25
            0xad5f, // Tag 26
            0xd530, // Tag 27
            0x07ca, // Tag 28
            0xaf2e, // Tag 29
        };
        
        if (tagId < 0 || tagId >= tag16h5Codes.Length)
        {
            tagId = 0; // Fallback to ID 0
        }
        
        int code = tag16h5Codes[tagId];
        bool[,] pattern = new bool[4, 4];
        
        // Decode the 16-bit code into 4x4 pattern
        // Bits are arranged MSB first, row by row
        // Bit 15 = top-left, bit 0 = bottom-right
        for (int row = 0; row < 4; row++)
        {
            int rowBits = (code >> (12 - row * 4)) & 0xF;
            for (int col = 0; col < 4; col++)
            {
                // Bit 3 is leftmost, bit 0 is rightmost
                pattern[row, col] = ((rowBits >> (3 - col)) & 1) == 1;
            }
        }
        
        return pattern;
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
