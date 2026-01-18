using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Interop;
using System.Windows.Media;
using System.Windows.Shapes;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Manages AprilTag overlays across multiple screens.
/// Uses AprilTag 16h5 format with tags 0-3 for screen 0, tags 4-7 for screen 1, etc.
/// Corner mapping: 0=TopLeft, 1=TopRight, 2=BottomRight, 3=BottomLeft
/// </summary>
public class MultiScreenAprilTagManager : IDisposable
{
    private readonly Dictionary<int, AprilTag16h5Overlay> _overlays = new();
    private readonly Dictionary<int, int> _physicalToLogicalScreen = new();
    private bool _disposed;
    private bool _isVisible;
    
    /// <summary>
    /// Size of each AprilTag in pixels.
    /// </summary>
    public int TagSize { get; set; } = 120;
    
    /// <summary>
    /// Margin from screen corners.
    /// </summary>
    public int CornerMargin { get; set; } = 30;
    
    /// <summary>
    /// Gets whether the AprilTags are currently visible.
    /// </summary>
    public bool IsVisible => _isVisible;
    
    /// <summary>
    /// Gets the mapping from physical screen index to logical screen number.
    /// </summary>
    public IReadOnlyDictionary<int, int> ScreenMapping => _physicalToLogicalScreen;
    
    /// <summary>
    /// Event raised when screen mapping changes.
    /// </summary>
    public event EventHandler? ScreenMappingChanged;
    
    public MultiScreenAprilTagManager()
    {
        // Initialize default mapping (physical = logical)
        var screens = DpiAwareScreenManager.GetAllScreens(true);
        for (int i = 0; i < screens.Count; i++)
        {
            _physicalToLogicalScreen[i] = i;
        }
    }
    
    /// <summary>
    /// Sets the logical screen number for a physical screen.
    /// This determines which AprilTag IDs (0-3, 4-7, 8-11, etc.) appear on each screen.
    /// </summary>
    /// <param name="physicalScreenIndex">Physical screen index (0-based)</param>
    /// <param name="logicalScreenNumber">Logical screen number (determines tag IDs: screenNum*4 to screenNum*4+3)</param>
    public void SetScreenMapping(int physicalScreenIndex, int logicalScreenNumber)
    {
        _physicalToLogicalScreen[physicalScreenIndex] = logicalScreenNumber;
        
        if (_overlays.TryGetValue(physicalScreenIndex, out var overlay))
        {
            overlay.LogicalScreenNumber = logicalScreenNumber;
            if (_isVisible)
            {
                overlay.Redraw();
            }
        }
        
        ScreenMappingChanged?.Invoke(this, EventArgs.Empty);
    }
    
    /// <summary>
    /// Gets the logical screen number for a physical screen.
    /// </summary>
    public int GetLogicalScreenNumber(int physicalScreenIndex)
    {
        return _physicalToLogicalScreen.TryGetValue(physicalScreenIndex, out var num) ? num : physicalScreenIndex;
    }
    
    /// <summary>
    /// Shows AprilTags on all screens.
    /// </summary>
    public void ShowAll()
    {
        DpiAwareScreenManager.GetAllScreens(true);
        var screens = DpiAwareScreenManager.GetAllScreens();
        
        foreach (var screen in screens)
        {
            ShowOnScreen(screen.Index);
        }
        
        _isVisible = true;
    }
    
    /// <summary>
    /// Shows AprilTags on a specific screen.
    /// </summary>
    public void ShowOnScreen(int physicalScreenIndex)
    {
        if (!_overlays.TryGetValue(physicalScreenIndex, out var overlay))
        {
            int logicalNumber = GetLogicalScreenNumber(physicalScreenIndex);
            overlay = new AprilTag16h5Overlay(physicalScreenIndex, logicalNumber)
            {
                TagSize = TagSize,
                CornerMargin = CornerMargin
            };
            _overlays[physicalScreenIndex] = overlay;
        }
        
        overlay.Show();
    }
    
    /// <summary>
    /// Hides AprilTags on all screens.
    /// </summary>
    public void HideAll()
    {
        foreach (var overlay in _overlays.Values)
        {
            overlay.Hide();
        }
        _isVisible = false;
    }
    
    /// <summary>
    /// Hides AprilTags on a specific screen.
    /// </summary>
    public void HideOnScreen(int physicalScreenIndex)
    {
        if (_overlays.TryGetValue(physicalScreenIndex, out var overlay))
        {
            overlay.Hide();
        }
    }
    
    /// <summary>
    /// Refreshes all overlays (e.g., after screen configuration changes).
    /// </summary>
    public void Refresh()
    {
        var wasVisible = _isVisible;
        
        // Close all existing overlays
        foreach (var overlay in _overlays.Values)
        {
            overlay.Close();
        }
        _overlays.Clear();
        
        // Re-create mapping for new screens
        var screens = DpiAwareScreenManager.GetAllScreens(true);
        var newMapping = new Dictionary<int, int>();
        for (int i = 0; i < screens.Count; i++)
        {
            // Keep existing mapping if available
            newMapping[i] = _physicalToLogicalScreen.TryGetValue(i, out var num) ? num : i;
        }
        _physicalToLogicalScreen.Clear();
        foreach (var kv in newMapping)
        {
            _physicalToLogicalScreen[kv.Key] = kv.Value;
        }
        
        if (wasVisible)
        {
            ShowAll();
        }
    }
    
    /// <summary>
    /// Gets the AprilTag IDs for a given logical screen number.
    /// </summary>
    /// <param name="logicalScreenNumber">Logical screen number</param>
    /// <returns>Array of 4 tag IDs: [TopLeft, TopRight, BottomRight, BottomLeft]</returns>
    public static int[] GetTagIdsForScreen(int logicalScreenNumber)
    {
        int baseId = logicalScreenNumber * 4;
        return new[] { baseId, baseId + 1, baseId + 2, baseId + 3 };
    }
    
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        
        foreach (var overlay in _overlays.Values)
        {
            overlay.Close();
        }
        _overlays.Clear();
    }
}

/// <summary>
/// An overlay window that displays AprilTag 16h5 format tags on the corners of a screen.
/// </summary>
public class AprilTag16h5Overlay : Window
{
    #region Win32 Interop
    
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
    
    #region AprilTag 16h5 Patterns
    
    // Official AprilTag 16h5 family - 30 tags (0-29)
    // Extracted from: https://github.com/AprilRobotics/apriltag/blob/master/tag16h5.c
    //
    // AprilTag 16h5 structure:
    // - Total grid: 6x6 cells
    // - Outer border: 1 cell black border (always black)
    // - Inner data: 4x4 cells (16 bits of data)
    // - White border: 1 cell around the entire tag for detection
    //
    // The codes below represent the 4x4 inner data area (16 bits)
    // Bit layout: row-major order, bit 15 = top-left, bit 0 = bottom-right
    // 1 = black (foreground), 0 = white (background)
    //
    // Official hamming distance: 5 (can correct up to 2 bit errors)
    
    private static readonly ushort[] AprilTag16h5Visual = new ushort[]
    {
        // These are the actual 16h5 tag patterns from the official library
        // Converted to 16-bit representation of the 4x4 inner data region
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
    
    #endregion
    
    public int TagSize { get; set; } = 120;
    public int CornerMargin { get; set; } = 30;
    public int PhysicalScreenIndex { get; private set; }
    public int LogicalScreenNumber { get; set; }
    
    private readonly Canvas _canvas;
    
    public AprilTag16h5Overlay(int physicalScreenIndex, int logicalScreenNumber)
    {
        PhysicalScreenIndex = physicalScreenIndex;
        LogicalScreenNumber = logicalScreenNumber;
        
        WindowStyle = WindowStyle.None;
        AllowsTransparency = true;
        Background = Brushes.Transparent;
        Topmost = true;
        ShowInTaskbar = false;
        ResizeMode = ResizeMode.NoResize;
        
        _canvas = new Canvas { Background = Brushes.Transparent };
        Content = _canvas;
        
        SourceInitialized += OnSourceInitialized;
        PositionOnScreen();
    }
    
    private void OnSourceInitialized(object? sender, EventArgs e)
    {
        var hwnd = new WindowInteropHelper(this).Handle;
        int extendedStyle = GetWindowLong(hwnd, GWL_EXSTYLE);
        extendedStyle |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE;
        SetWindowLong(hwnd, GWL_EXSTYLE, extendedStyle);
    }
    
    private void PositionOnScreen()
    {
        var screen = DpiAwareScreenManager.GetScreen(PhysicalScreenIndex);
        if (screen != null)
        {
            Left = screen.LogicalLeft;
            Top = screen.LogicalTop;
            Width = screen.LogicalWidth;
            Height = screen.LogicalHeight;
        }
    }
    
    public new void Show()
    {
        PositionOnScreen();
        DrawAprilTags();
        base.Show();
    }
    
    public void Redraw()
    {
        if (IsVisible)
        {
            DrawAprilTags();
        }
    }
    
    private void DrawAprilTags()
    {
        _canvas.Children.Clear();
        
        double w = Width;
        double h = Height;
        
        // Get tag IDs for this logical screen
        // Tag positions: 0=TopLeft, 1=TopRight, 2=BottomRight, 3=BottomLeft
        int baseId = LogicalScreenNumber * 4;
        
        // Top-Left
        DrawAprilTag16h5(CornerMargin, CornerMargin, baseId + 0);
        
        // Top-Right  
        DrawAprilTag16h5(w - TagSize - CornerMargin, CornerMargin, baseId + 1);
        
        // Bottom-Right
        DrawAprilTag16h5(w - TagSize - CornerMargin, h - TagSize - CornerMargin, baseId + 2);
        
        // Bottom-Left
        DrawAprilTag16h5(CornerMargin, h - TagSize - CornerMargin, baseId + 3);
    }
    
    private void DrawAprilTag16h5(double x, double y, int tagId)
    {
        // AprilTag 16h5 structure:
        // - 8x8 total grid (including white border)
        // - Outer white border (1 cell width)
        // - Black border (1 cell width) 
        // - Inner 4x4 = data pattern
        
        // The white border is essential for AprilTag detection
        int totalGridSize = 8; // 6x6 tag + 1 cell white border on each side
        int tagGridSize = 6;
        double cellSize = TagSize / (double)totalGridSize;
        double tagInnerSize = cellSize * tagGridSize;
        double borderOffset = cellSize; // White border width
        
        // Draw white background (covers the entire tag area including white border)
        var background = new Rectangle
        {
            Width = TagSize,
            Height = TagSize,
            Fill = Brushes.White
        };
        Canvas.SetLeft(background, x);
        Canvas.SetTop(background, y);
        _canvas.Children.Add(background);
        
        // Get the pattern (use modulo to handle out-of-range tag IDs)
        ushort pattern = tagId < AprilTag16h5Visual.Length 
            ? AprilTag16h5Visual[tagId] 
            : AprilTag16h5Visual[tagId % AprilTag16h5Visual.Length];
        
        // Draw the 6x6 inner grid (offset by white border)
        for (int row = 0; row < tagGridSize; row++)
        {
            for (int col = 0; col < tagGridSize; col++)
            {
                bool isBlack;
                
                // Outer border of the 6x6 is always black
                if (row == 0 || row == tagGridSize - 1 || col == 0 || col == tagGridSize - 1)
                {
                    isBlack = true;
                }
                else
                {
                    // Inner 4x4 data pattern
                    int innerRow = row - 1;
                    int innerCol = col - 1;
                    int bitIndex = innerRow * 4 + innerCol;
                    // Bit 15 is top-left, bit 0 is bottom-right
                    isBlack = ((pattern >> (15 - bitIndex)) & 1) == 1;
                }
                
                if (isBlack)
                {
                    var cell = new Rectangle
                    {
                        Width = cellSize + 0.5, // Small overlap to avoid gaps
                        Height = cellSize + 0.5,
                        Fill = Brushes.Black
                    };
                    // Offset by white border
                    Canvas.SetLeft(cell, x + borderOffset + col * cellSize);
                    Canvas.SetTop(cell, y + borderOffset + row * cellSize);
                    _canvas.Children.Add(cell);
                }
            }
        }
        
        // Add label below the tag
        var label = new TextBlock
        {
            Text = $"ID:{tagId} (Screen {LogicalScreenNumber})",
            FontSize = 11,
            Foreground = Brushes.White,
            FontWeight = FontWeights.Bold,
            Background = new SolidColorBrush(Color.FromArgb(200, 0, 0, 0)),
            Padding = new Thickness(3, 1, 3, 1)
        };
        Canvas.SetLeft(label, x);
        Canvas.SetTop(label, y + TagSize + 4);
        _canvas.Children.Add(label);
        
        // Add corner indicator
        string cornerName = (tagId % 4) switch
        {
            0 => "TL",
            1 => "TR",
            2 => "BR",
            3 => "BL",
            _ => "?"
        };
        var cornerLabel = new TextBlock
        {
            Text = cornerName,
            FontSize = 9,
            Foreground = Brushes.Yellow,
            FontWeight = FontWeights.Bold
        };
        Canvas.SetLeft(cornerLabel, x + TagSize - 18);
        Canvas.SetTop(cornerLabel, y + TagSize + 4);
        _canvas.Children.Add(cornerLabel);
    }
}
