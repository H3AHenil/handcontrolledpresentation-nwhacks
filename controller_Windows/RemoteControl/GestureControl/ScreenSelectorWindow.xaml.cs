using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Window for selecting which screen to target for gesture control.
/// </summary>
public partial class ScreenSelectorWindow : Window
{
    private int _selectedScreenIndex;
    
    /// <summary>
    /// Gets the selected screen index after the dialog is closed.
    /// </summary>
    public int SelectedScreenIndex => _selectedScreenIndex;
    
    /// <summary>
    /// Gets or sets whether the selection was confirmed (OK clicked).
    /// </summary>
    public bool Confirmed { get; private set; }
    
    /// <summary>
    /// View model for screen list items.
    /// </summary>
    public class ScreenViewModel
    {
        public int Index { get; init; }
        public string DisplayIndex => (Index + 1).ToString();
        public string DeviceName { get; init; } = string.Empty;
        public string Resolution { get; init; } = string.Empty;
        public string Position { get; init; } = string.Empty;
        public string PrimaryLabel { get; init; } = string.Empty;
        public bool IsSelected { get; set; }
        public Brush Background => IsSelected ? new SolidColorBrush(Color.FromRgb(0xE3, 0xF2, 0xFD)) : Brushes.White;
        public Brush SelectionColor => IsSelected ? new SolidColorBrush(Color.FromRgb(0x21, 0x96, 0xF3)) : new SolidColorBrush(Color.FromRgb(0xCC, 0xCC, 0xCC));
        public Visibility CheckVisibility => IsSelected ? Visibility.Visible : Visibility.Hidden;
    }
    
    private List<ScreenViewModel> _screens = new();
    
    /// <summary>
    /// Creates a new ScreenSelectorWindow with the specified initial selection.
    /// </summary>
    /// <param name="currentScreenIndex">Currently selected screen index</param>
    public ScreenSelectorWindow(int currentScreenIndex = 0)
    {
        InitializeComponent();
        _selectedScreenIndex = currentScreenIndex;
        RefreshScreenList();
    }
    
    private void RefreshScreenList()
    {
        ScreenManager.RefreshCache();
        var screens = ScreenManager.GetAllScreens();
        
        _screens = new List<ScreenViewModel>();
        
        foreach (var screen in screens)
        {
            _screens.Add(new ScreenViewModel
            {
                Index = screen.Index,
                DeviceName = screen.DeviceName,
                Resolution = $"{screen.Width} × {screen.Height}",
                Position = $"({screen.Left}, {screen.Top})",
                PrimaryLabel = screen.IsPrimary ? " [Primary]" : "",
                IsSelected = screen.Index == _selectedScreenIndex
            });
        }
        
        // If selected index is out of range, select first
        if (_selectedScreenIndex >= _screens.Count && _screens.Count > 0)
        {
            _selectedScreenIndex = 0;
            _screens[0].IsSelected = true;
        }
        
        ScreenList.ItemsSource = null;
        ScreenList.ItemsSource = _screens;
    }
    
    private void OnScreenItemClick(object sender, MouseButtonEventArgs e)
    {
        if (sender is FrameworkElement element && element.DataContext is ScreenViewModel vm)
        {
            // Deselect all
            foreach (var screen in _screens)
            {
                screen.IsSelected = false;
            }
            
            // Select clicked
            vm.IsSelected = true;
            _selectedScreenIndex = vm.Index;
            
            // Refresh to update visual states
            ScreenList.ItemsSource = null;
            ScreenList.ItemsSource = _screens;
        }
    }
    
    private void OnRefreshScreens(object sender, RoutedEventArgs e)
    {
        RefreshScreenList();
    }
    
    private void OnCancel(object sender, RoutedEventArgs e)
    {
        Confirmed = false;
        Close();
    }
    
    private void OnOK(object sender, RoutedEventArgs e)
    {
        Confirmed = true;
        Close();
    }
    
    /// <summary>
    /// Shows the screen selector dialog and returns the selected screen index.
    /// </summary>
    /// <param name="currentScreenIndex">Current screen index</param>
    /// <param name="owner">Owner window (optional)</param>
    /// <returns>Selected screen index, or -1 if cancelled</returns>
    public static int ShowDialog(int currentScreenIndex, Window? owner = null)
    {
        var dialog = new ScreenSelectorWindow(currentScreenIndex);
        if (owner != null)
        {
            dialog.Owner = owner;
        }
        dialog.ShowDialog();
        
        return dialog.Confirmed ? dialog.SelectedScreenIndex : -1;
    }
}
