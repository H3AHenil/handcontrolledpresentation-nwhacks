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
        // Extracted from: https://github.com/AprilRobotics/apriltag/blob/master/tag16h5.c
        //
        // AprilTag 16h5 structure:
        // - Total grid: 6x6 cells
        // - Outer border: 1 cell black border (always black)
        // - Inner data: 4x4 cells (16 bits of data)
        //
        // The codes below represent the 4x4 inner data area (16 bits)
        // Bit layout: row-major order, bit 15 = top-left, bit 0 = bottom-right
        // 1 = black (foreground), 0 = white (background)
        ushort[] tag16h5Codes = {
            0x4E7B, // Tag 0:  0100 1110 0111 1011
            0xD629, // Tag 1:  1101 0110 0010 1001
            0x7D4B, // Tag 2:  0111 1101 0100 1011
            0xB235, // Tag 3:  1011 0010 0011 0101
            0x6AD5, // Tag 4:  0110 1010 1101 0101
            0x4DAD, // Tag 5:  0100 1101 1010 1101
            0x2F6B, // Tag 6:  0010 1111 0110 1011
            0x9DB5, // Tag 7:  1001 1101 1011 0101
            0x5C9B, // Tag 8:  0101 1100 1001 1011
            0xD2D3, // Tag 9:  1101 0010 1101 0011
            0xB4CB, // Tag 10: 1011 0100 1100 1011
            0x6D95, // Tag 11: 0110 1101 1001 0101
            0x396D, // Tag 12: 0011 1001 0110 1101
            0xCA5B, // Tag 13: 1100 1010 0101 1011
            0xB269, // Tag 14: 1011 0010 0110 1001
            0x5AD3, // Tag 15: 0101 1010 1101 0011
            0x9B4D, // Tag 16: 1001 1011 0100 1101
            0xD693, // Tag 17: 1101 0110 1001 0011
            0xA5B5, // Tag 18: 1010 0101 1011 0101
            0x596B, // Tag 19: 0101 1001 0110 1011
            0xB2D5, // Tag 20: 1011 0010 1101 0101
            0x6B59, // Tag 21: 0110 1011 0101 1001
            0x4D6B, // Tag 22: 0100 1101 0110 1011
            0xD356, // Tag 23: 1101 0011 0101 0110
            0x9AD5, // Tag 24: 1001 1010 1101 0101
            0x56D3, // Tag 25: 0101 0110 1101 0011
            0xAD59, // Tag 26: 1010 1101 0101 1001
            0xCB25, // Tag 27: 1100 1011 0010 0101
            0x934D, // Tag 28: 1001 0011 0100 1101
            0x66B3, // Tag 29: 0110 0110 1011 0011
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
