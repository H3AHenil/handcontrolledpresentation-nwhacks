using System;
using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using TestOnRemoteControl.GestureControl;

namespace TestOnRemoteControl;

/// <summary>
/// Interaction logic for MainWindow.xaml
/// </summary>
public partial class MainWindow : Window
{
    // Movement sensitivity
    private const double MoveSensitivity = 1.5;

    // --- Wheel-related settings ---
    // Wheel sensitivity multiplier: the larger the value, the faster a pinch gesture triggers wheel steps
    private const double ScrollSpeedMultiplier = 3000.0;

    // Windows standard wheel delta per notch
    private const int WHEEL_DELTA = 120;

    // Wheel accumulator ("reservoir")
    private double _accumulatedScrollDelta = 0;

    private const int RemoteControlPort = 8080;
    private readonly UdpRemoteCommandListener _listener = new(RemoteControlPort);
    
    // Gesture control components
    private const int GestureControlPort = 9090;
    private GestureController? _gestureController;
    private GestureUdpReceiver? _gestureReceiver;
    
    // Multi-screen AprilTag manager
    private MultiScreenAprilTagManager? _aprilTagManager;
    private bool _aprilTagsVisible;

    public MainWindow()
    {
        MouseController.MoveAbsolute(0,0);
        InitializeComponent();

        Loaded += (_, _) => _listener.Start();
        Closed += OnWindowClosed;
    }
    
    private async void OnWindowClosed(object? sender, EventArgs e)
    {
        await _listener.StopAsync();
        
        if (_gestureReceiver != null)
        {
            await _gestureReceiver.StopAsync();
            _gestureReceiver.Dispose();
        }
        
        _aprilTagManager?.Dispose();
        _gestureController?.Dispose();
    }
    
    private void Log(string message)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
        ActivityLog.Text = $"[{timestamp}] {message}\n" + ActivityLog.Text;
        
        // Keep log size reasonable
        if (ActivityLog.Text.Length > 3000)
        {
            ActivityLog.Text = ActivityLog.Text.Substring(0, 2000);
        }
    }
    
    #region Gesture Control
    
    private void OnStartGestureListener(object sender, RoutedEventArgs e)
    {
        try
        {
            // Create controller if not exists
            _gestureController ??= new GestureController(new GestureController.ControllerConfiguration
            {
                ZoomSensitivity = 150.0f,
                ScrollSensitivity = 80.0f,
                MovementSmoothing = 0.2f
            });
            
            _gestureController.ModeChanged += OnGestureModeChanged;
            _gestureController.TargetScreenChanged += OnTargetScreenChanged;
            
            // Create and start receiver - accept gestures for ALL screens
            // The screenIndex in gesture data determines which screen to control
            _gestureReceiver = new GestureUdpReceiver(GestureControlPort, _gestureController);
            // ScreenIndexFilter = -1 means accept all screens (default)
            // _gestureReceiver.ScreenIndexFilter = _gestureController.TargetScreenIndex; // Removed: don't filter by screen
            _gestureReceiver.GestureReceived += OnGestureReceived;
            _gestureReceiver.GestureFiltered += OnGestureFiltered;
            _gestureReceiver.ErrorOccurred += OnGestureError;
            _gestureReceiver.Start();
            
            StartGestureListenerButton.IsEnabled = false;
            StopGestureListenerButton.IsEnabled = true;
            
            StatusLabel.Text = $"Listening on port {GestureControlPort}";
            StatusLabel.Foreground = new SolidColorBrush(Colors.LimeGreen);
            
            UpdateTargetScreenLabel();
            
            Log($"Gesture listener started on port {GestureControlPort}, accepting ALL screens");
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Failed to start gesture listener: {ex.Message}", "Error", 
                MessageBoxButton.OK, MessageBoxImage.Error);
            Log($"Error: {ex.Message}");
        }
    }
    
    private async void OnStopGestureListener(object sender, RoutedEventArgs e)
    {
        if (_gestureReceiver != null)
        {
            _gestureReceiver.GestureReceived -= OnGestureReceived;
            _gestureReceiver.GestureFiltered -= OnGestureFiltered;
            _gestureReceiver.ErrorOccurred -= OnGestureError;
            await _gestureReceiver.StopAsync();
            _gestureReceiver.Dispose();
            _gestureReceiver = null;
        }
        
        if (_gestureController != null)
        {
            _gestureController.ModeChanged -= OnGestureModeChanged;
            _gestureController.TargetScreenChanged -= OnTargetScreenChanged;
        }
        
        StartGestureListenerButton.IsEnabled = true;
        StopGestureListenerButton.IsEnabled = false;
        
        StatusLabel.Text = "Idle";
        StatusLabel.Foreground = new SolidColorBrush(Color.FromRgb(0x4C, 0xAF, 0x50));
        
        Log("Gesture listener stopped");
    }
    
    private void OnOpenDemoWindow(object sender, RoutedEventArgs e)
    {
        var demoWindow = new GestureControlDemoWindow();
        demoWindow.Show();
        Log("Opened Gesture Control Demo window");
    }
    
    private void OnSelectScreen(object sender, RoutedEventArgs e)
    {
        int currentScreen = _gestureController?.TargetScreenIndex ?? 0;
        int selectedScreen = ScreenSelectorWindow.ShowDialog(currentScreen, this);
        
        if (selectedScreen >= 0)
        {
            // Ensure controller exists
            _gestureController ??= new GestureController();
            _gestureController.TargetScreenIndex = selectedScreen;
            
            UpdateTargetScreenLabel();
            Log($"Target screen changed to: Screen {selectedScreen + 1}");
        }
    }
    
    private void UpdateTargetScreenLabel()
    {
        int screenIndex = _gestureController?.TargetScreenIndex ?? 0;
        var screen = ScreenManager.GetScreen(screenIndex);
        
        if (screen != null)
        {
            TargetScreenLabel.Text = $"Screen {screenIndex + 1}{(screen.IsPrimary ? " [Primary]" : "")}";
        }
        else
        {
            TargetScreenLabel.Text = $"Screen {screenIndex + 1}";
        }
    }
    
    private void OnGestureModeChanged(object? sender, GestureModeChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(() =>
        {
            GestureModeLabel.Text = e.NewMode == GestureMode.LaserPointer ? "Laser Pointer" : "Cursor";
            GestureModeLabel.Foreground = e.NewMode == GestureMode.LaserPointer 
                ? new SolidColorBrush(Colors.Red) 
                : new SolidColorBrush(Color.FromRgb(0x21, 0x96, 0xF3));
            Log($"Mode changed to: {e.NewMode}");
        });
    }
    
    private void OnTargetScreenChanged(object? sender, ScreenChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(() =>
        {
            UpdateTargetScreenLabel();
            Log($"Target screen changed to: Screen {e.NewScreenIndex + 1}");
        });
    }
    
    private void OnGestureReceived(object? sender, GestureData data)
    {
        Dispatcher.BeginInvoke(() =>
        {
            // Only log some gestures to avoid flooding
            if (data.Type != GestureType.Pointer || DateTime.Now.Millisecond % 500 < 50)
            {
                Log($"Gesture: {data.Type} @ ({data.NormalizedX:F2}, {data.NormalizedY:F2}) screen={data.ScreenIndex}");
            }
        });
    }
    
    private void OnGestureError(object? sender, Exception ex)
    {
        Dispatcher.BeginInvoke(() =>
        {
            Log($"Receiver error: {ex.Message}");
        });
    }
    
    private void OnGestureFiltered(object? sender, GestureData data)
    {
        // Optionally log filtered gestures (uncomment for debugging)
        // Dispatcher.BeginInvoke(() =>
        // {
        //     Log($"Filtered: {data.Type} screen={data.ScreenIndex} device={data.DeviceId}");
        // });
    }
    
    private void OnToggleAprilTags(object sender, RoutedEventArgs e)
    {
        if (_aprilTagsVisible)
        {
            // Hide AprilTags on all screens
            _aprilTagManager?.HideAll();
            _aprilTagsVisible = false;
            AprilTagButton.Content = "Show AprilTags";
            AprilTagStatusLabel.Text = "Off";
            AprilTagStatusLabel.Foreground = new SolidColorBrush(Colors.Gray);
            Log("AprilTags hidden on all screens");
        }
        else
        {
            // Show AprilTags on all screens
            if (_aprilTagManager == null)
            {
                _aprilTagManager = new MultiScreenAprilTagManager
                {
                    TagSize = 120,
                    CornerMargin = 30
                };
            }
            
            _aprilTagManager.ShowAll();
            _aprilTagsVisible = true;
            AprilTagButton.Content = "Hide AprilTags";
            
            int screenCount = DpiAwareScreenManager.ScreenCount;
            AprilTagStatusLabel.Text = $"All {screenCount} screens";
            AprilTagStatusLabel.Foreground = new SolidColorBrush(Colors.LimeGreen);
            Log($"AprilTags shown on {screenCount} screen(s)");
        }
    }
    
    private async void OnTestLaserPointer(object sender, RoutedEventArgs e)
    {
        // Ensure controller exists
        _gestureController ??= new GestureController();
        
        // Toggle to laser mode
        if (_gestureController.CurrentMode != GestureMode.LaserPointer)
        {
            _gestureController.SetMode(GestureMode.LaserPointer);
            LaserTestButton.Content = "Stop Laser Test";
            Log("Laser pointer mode enabled - move to test");
            
            // Animate the laser pointer in a circle
            int targetScreen = _gestureController.TargetScreenIndex;
            
            for (int i = 0; i < 100 && _gestureController.CurrentMode == GestureMode.LaserPointer; i++)
            {
                double angle = i * 0.1;
                float x = 0.5f + 0.2f * (float)Math.Cos(angle);
                float y = 0.5f + 0.2f * (float)Math.Sin(angle);
                
                _gestureController.UpdateFingerPosition(x, y, 1, targetScreen);
                await System.Threading.Tasks.Task.Delay(30);
            }
        }
        else
        {
            _gestureController.SetMode(GestureMode.Cursor);
            LaserTestButton.Content = "Test Laser Pointer";
            Log("Laser pointer mode disabled");
        }
    }
    
    private void OnConfigureScreens(object sender, RoutedEventArgs e)
    {
        // Ensure AprilTag manager exists
        _aprilTagManager ??= new MultiScreenAprilTagManager
        {
            TagSize = 120,
            CornerMargin = 30
        };
        
        bool wasVisible = _aprilTagsVisible;
        if (wasVisible)
        {
            _aprilTagManager.HideAll();
        }
        
        if (ScreenConfigurationWindow.ShowDialog(_aprilTagManager, this))
        {
            Log("Screen configuration updated");
            
            // Update target screen label
            UpdateTargetScreenLabel();
        }
        
        if (wasVisible)
        {
            _aprilTagManager.ShowAll();
        }
    }
    
    #endregion


    private void OnManipulationDelta(object sender, ManipulationDeltaEventArgs e)
    {
        // ===========================
        // 1. Handle movement (one-finger drag or multi-finger pan)
        // ===========================
        var translation = e.DeltaManipulation.Translation;
        int dx = (int)(translation.X * MoveSensitivity);
        int dy = (int)(translation.Y * MoveSensitivity);

        if (dx != 0 || dy != 0)
        {
            MouseController.MoveRelative(dx, dy);
        }

        // ===========================
        // 2. Handle scaling (two-finger pinch/spread) -> map to "Ctrl + Wheel" zoom
        // ===========================

        // Get scale ratio. Scale.X and Scale.Y are usually close; average is more robust.
        // scaleRatio > 1.0 means spread (zoom in), < 1.0 means pinch (zoom out)
        double scaleRatio = (e.DeltaManipulation.Scale.X + e.DeltaManipulation.Scale.Y) / 2.0;

        // If the ratio is ~1.0, there's no scaling. Skip.
        if (Math.Abs(scaleRatio - 1.0) < 0.001)
        {
            return;
        }

        // Compute the "wheel pressure" for this frame.
        // (scaleRatio - 1.0) is a tiny float (e.g., +0.02 or -0.03).
        // Multiply by a large constant to convert it into a meaningful wheel delta.
        double currentStepDelta = (scaleRatio - 1.0) * ScrollSpeedMultiplier;

        // Add delta into the accumulator ("reservoir")
        _accumulatedScrollDelta += currentStepDelta;

        // --- Threshold checks & triggering ---

        // If the positive pressure exceeds one wheel notch (zoom in / wheel up)
        if (_accumulatedScrollDelta >= WHEEL_DELTA)
        {
            MouseController.Zoom(+1);
            _accumulatedScrollDelta -= WHEEL_DELTA;
        }
        // If the negative pressure exceeds one wheel notch (zoom out / wheel down)
        else if (_accumulatedScrollDelta <= -WHEEL_DELTA)
        {
            MouseController.Zoom(-1);
            _accumulatedScrollDelta += WHEEL_DELTA;
        }

        // Debug: inspect accumulated value
        // Console.WriteLine($"Ratio: {scaleRatio:F4}, Accum: {_accumulatedScrollDelta:F2}");
    }

    private void OnManipulationCompleted(object sender, ManipulationCompletedEventArgs e)
    {
        // When the gesture ends, clear the accumulator to avoid leftover scroll from previous interaction
        _accumulatedScrollDelta = 0;
    }
}