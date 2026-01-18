using System;
using System.Collections.Generic;
using System.ComponentModel;
using System.Windows;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Window for configuring multi-screen AprilTag settings.
/// Allows users to assign logical screen numbers to physical displays.
/// </summary>
public partial class ScreenConfigurationWindow : Window
{
    private readonly MultiScreenAprilTagManager? _manager;
    private List<ScreenConfigViewModel> _screens = new();
    private MultiScreenAprilTagManager? _previewManager;
    
    /// <summary>
    /// Gets the configured screen mappings after dialog is closed.
    /// Key = physical screen index, Value = logical screen number
    /// </summary>
    public Dictionary<int, int> ScreenMappings { get; } = new();
    
    /// <summary>
    /// Gets whether the configuration was confirmed.
    /// </summary>
    public bool Confirmed { get; private set; }
    
    /// <summary>
    /// View model for screen configuration items.
    /// </summary>
    public class ScreenConfigViewModel : INotifyPropertyChanged
    {
        private int _logicalScreenNumber;
        
        public int PhysicalIndex { get; init; }
        public string PhysicalDisplayIndex => (PhysicalIndex + 1).ToString();
        public string DeviceName { get; init; } = string.Empty;
        public string Resolution { get; init; } = string.Empty;
        public string Position { get; init; } = string.Empty;
        public string PrimaryLabel { get; init; } = string.Empty;
        
        public int LogicalScreenNumber
        {
            get => _logicalScreenNumber;
            set
            {
                if (_logicalScreenNumber != value)
                {
                    _logicalScreenNumber = value;
                    OnPropertyChanged(nameof(LogicalScreenNumber));
                    OnPropertyChanged(nameof(TagIdRange));
                }
            }
        }
        
        public string TagIdRange
        {
            get
            {
                int baseId = _logicalScreenNumber * 4;
                return $"{baseId}, {baseId + 1}, {baseId + 2}, {baseId + 3}";
            }
        }
        
        public event PropertyChangedEventHandler? PropertyChanged;
        
        protected virtual void OnPropertyChanged(string propertyName)
        {
            PropertyChanged?.Invoke(this, new PropertyChangedEventArgs(propertyName));
        }
    }
    
    /// <summary>
    /// Creates a new ScreenConfigurationWindow.
    /// </summary>
    /// <param name="manager">Optional AprilTag manager to get current mappings from</param>
    public ScreenConfigurationWindow(MultiScreenAprilTagManager? manager = null)
    {
        InitializeComponent();
        _manager = manager;
        RefreshScreenList();
    }
    
    private void RefreshScreenList()
    {
        DpiAwareScreenManager.GetAllScreens(true);
        var screens = DpiAwareScreenManager.GetAllScreens();
        
        _screens = new List<ScreenConfigViewModel>();
        
        foreach (var screen in screens)
        {
            int logicalNumber = _manager?.GetLogicalScreenNumber(screen.Index) ?? screen.Index;
            
            _screens.Add(new ScreenConfigViewModel
            {
                PhysicalIndex = screen.Index,
                DeviceName = screen.DeviceName,
                Resolution = $"{screen.PhysicalWidth} × {screen.PhysicalHeight}",
                Position = $"({screen.PhysicalLeft}, {screen.PhysicalTop})",
                PrimaryLabel = screen.IsPrimary ? " [Primary]" : "",
                LogicalScreenNumber = logicalNumber
            });
        }
        
        ScreenList.ItemsSource = null;
        ScreenList.ItemsSource = _screens;
    }
    
    private void OnRefreshScreens(object sender, RoutedEventArgs e)
    {
        RefreshScreenList();
    }
    
    private void OnPreviewTags(object sender, RoutedEventArgs e)
    {
        // Create temporary preview manager
        if (_previewManager == null)
        {
            _previewManager = new MultiScreenAprilTagManager
            {
                TagSize = 120,
                CornerMargin = 30
            };
        }
        
        // Apply current settings
        foreach (var screen in _screens)
        {
            _previewManager.SetScreenMapping(screen.PhysicalIndex, screen.LogicalScreenNumber);
        }
        
        if (_previewManager.IsVisible)
        {
            _previewManager.HideAll();
        }
        else
        {
            _previewManager.ShowAll();
        }
    }
    
    private void OnCancel(object sender, RoutedEventArgs e)
    {
        _previewManager?.HideAll();
        _previewManager?.Dispose();
        Confirmed = false;
        Close();
    }
    
    private void OnApply(object sender, RoutedEventArgs e)
    {
        _previewManager?.HideAll();
        _previewManager?.Dispose();
        
        // Save mappings
        ScreenMappings.Clear();
        foreach (var screen in _screens)
        {
            ScreenMappings[screen.PhysicalIndex] = screen.LogicalScreenNumber;
        }
        
        // Apply to manager if provided
        if (_manager != null)
        {
            foreach (var kv in ScreenMappings)
            {
                _manager.SetScreenMapping(kv.Key, kv.Value);
            }
        }
        
        Confirmed = true;
        Close();
    }
    
    protected override void OnClosed(EventArgs e)
    {
        _previewManager?.HideAll();
        _previewManager?.Dispose();
        base.OnClosed(e);
    }
    
    /// <summary>
    /// Shows the configuration dialog.
    /// </summary>
    /// <param name="manager">AprilTag manager to configure</param>
    /// <param name="owner">Owner window</param>
    /// <returns>True if configuration was applied</returns>
    public static bool ShowDialog(MultiScreenAprilTagManager? manager, Window? owner = null)
    {
        var dialog = new ScreenConfigurationWindow(manager);
        if (owner != null)
        {
            dialog.Owner = owner;
        }
        dialog.ShowDialog();
        return dialog.Confirmed;
    }
}
