using System;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Demo window for testing the Gesture Control system.
/// </summary>
public partial class GestureControlDemoWindow : Window
{
    private readonly GestureController _controller;
    private GestureUdpReceiver? _receiver;
    private float _simulatedZoomValue = 1.0f;
    private float _simulatedRollValue = 0.0f;
    
    public GestureControlDemoWindow()
    {
        InitializeComponent();
        
        // Create the gesture controller
        _controller = new GestureController(new GestureController.ControllerConfiguration
        {
            ZoomSensitivity = 150.0f,
            ScrollSensitivity = 80.0f,
            MovementSmoothing = 0.2f
        });
        
        // Subscribe to mode changes
        _controller.ModeChanged += OnModeChanged;
        
        // Update UI
        UpdateUI();
        
        Closed += OnWindowClosed;
    }
    
    private void OnModeChanged(object? sender, GestureModeChangedEventArgs e)
    {
        Dispatcher.BeginInvoke(() =>
        {
            ModeLabel.Text = e.NewMode == GestureMode.LaserPointer ? "Laser Pointer Mode" : "Cursor Mode";
            ModeLabel.Foreground = e.NewMode == GestureMode.LaserPointer 
                ? System.Windows.Media.Brushes.Red 
                : System.Windows.Media.Brushes.DodgerBlue;
            
            Log($"Mode changed: {e.OldMode} -> {e.NewMode}");
        });
    }
    
    private void UpdateUI()
    {
        ModeLabel.Text = _controller.CurrentMode == GestureMode.LaserPointer ? "Laser Pointer Mode" : "Cursor Mode";
        PinchStateLabel.Text = _controller.IsPinchActive ? "Pressed" : "Released";
        PinchStateLabel.Foreground = _controller.IsPinchActive 
            ? System.Windows.Media.Brushes.Red 
            : System.Windows.Media.Brushes.Green;
    }
    
    private void Log(string message)
    {
        var timestamp = DateTime.Now.ToString("HH:mm:ss.fff");
        LogOutput.Text = $"[{timestamp}] {message}\n" + LogOutput.Text;
        
        // Keep log size reasonable
        if (LogOutput.Text.Length > 5000)
        {
            LogOutput.Text = LogOutput.Text.Substring(0, 3000);
        }
    }
    
    #region Mode Control
    
    private void OnToggleLaserMode(object sender, RoutedEventArgs e)
    {
        _controller.ToggleLaserMode();
        Log("Toggle laser mode triggered (simulating Clap gesture)");
    }
    
    private void OnSetCursorMode(object sender, RoutedEventArgs e)
    {
        _controller.SetMode(GestureMode.Cursor);
        Log("Set to Cursor Mode");
    }
    
    private void OnSetLaserMode(object sender, RoutedEventArgs e)
    {
        _controller.SetMode(GestureMode.LaserPointer);
        Log("Set to Laser Pointer Mode");
    }
    
    #endregion
    
    #region Pointer Control
    
    private void OnMoveCenter(object sender, RoutedEventArgs e)
    {
        _controller.UpdateFingerPosition(0.5f, 0.5f, 1);
        Log("Moved pointer to center (0.5, 0.5)");
    }
    
    private void OnMoveTopLeft(object sender, RoutedEventArgs e)
    {
        _controller.UpdateFingerPosition(0.1f, 0.1f, 1);
        Log("Moved pointer to top-left (0.1, 0.1)");
    }
    
    private void OnMoveBottomRight(object sender, RoutedEventArgs e)
    {
        _controller.UpdateFingerPosition(0.9f, 0.9f, 1);
        Log("Moved pointer to bottom-right (0.9, 0.9)");
    }
    
    private async void OnCircularMotion(object sender, RoutedEventArgs e)
    {
        Log("Starting circular motion demo...");
        
        // Animate in a circle
        for (int i = 0; i <= 360; i += 5)
        {
            double angle = i * Math.PI / 180.0;
            float x = 0.5f + (float)(0.3 * Math.Cos(angle));
            float y = 0.5f + (float)(0.3 * Math.Sin(angle));
            
            _controller.UpdateFingerPosition(x, y, 1);
            await Task.Delay(20);
        }
        
        Log("Circular motion complete");
    }
    
    #endregion
    
    #region Zoom Control
    
    private void OnZoomIn(object sender, RoutedEventArgs e)
    {
        // Simulate increasing stretch value (zoom in)
        _simulatedZoomValue += 0.5f;
        _controller.UpdateZoom(_simulatedZoomValue);
        Log($"Zoom in - stretch value: {_simulatedZoomValue:F2}");
    }
    
    private void OnZoomOut(object sender, RoutedEventArgs e)
    {
        // Simulate decreasing stretch value (zoom out)
        _simulatedZoomValue -= 0.5f;
        _controller.UpdateZoom(_simulatedZoomValue);
        Log($"Zoom out - stretch value: {_simulatedZoomValue:F2}");
    }
    
    #endregion
    
    #region Swipe Control
    
    private void OnSwipeLeft(object sender, RoutedEventArgs e)
    {
        _controller.TriggerSwipe(SwipeDirection.Left);
        Log("Swipe Left triggered (Alt+Shift+Tab)");
    }
    
    private void OnSwipeRight(object sender, RoutedEventArgs e)
    {
        _controller.TriggerSwipe(SwipeDirection.Right);
        Log("Swipe Right triggered (Alt+Tab)");
    }
    
    private void OnSwipeUp(object sender, RoutedEventArgs e)
    {
        _controller.TriggerSwipe(SwipeDirection.Up);
        Log("Swipe Up triggered (Win+Tab)");
    }
    
    #endregion
    
    #region Pinch Control
    
    private void OnStartPinch(object sender, RoutedEventArgs e)
    {
        _controller.StartPinch();
        UpdateUI();
        Log("Pinch started (Left Mouse Down)");
    }
    
    private void OnEndPinch(object sender, RoutedEventArgs e)
    {
        _controller.EndPinch();
        UpdateUI();
        Log("Pinch ended (Left Mouse Up)");
    }
    
    #endregion
    
    #region Scroll Control
    
    private void OnScrollUp(object sender, RoutedEventArgs e)
    {
        // Simulate positive roll for scroll up
        _simulatedRollValue += 2.0f;
        _controller.UpdateThumbsUpRoll(_simulatedRollValue);
        Log($"Scroll up - roll value: {_simulatedRollValue:F2}");
    }
    
    private void OnScrollDown(object sender, RoutedEventArgs e)
    {
        // Simulate negative roll for scroll down
        _simulatedRollValue -= 2.0f;
        _controller.UpdateThumbsUpRoll(_simulatedRollValue);
        Log($"Scroll down - roll value: {_simulatedRollValue:F2}");
    }
    
    #endregion
    
    #region UDP Listener
    
    private void OnStartListener(object sender, RoutedEventArgs e)
    {
        if (!int.TryParse(PortTextBox.Text, out int port) || port < 1 || port > 65535)
        {
            MessageBox.Show("Please enter a valid port number (1-65535)", "Invalid Port", MessageBoxButton.OK, MessageBoxImage.Warning);
            return;
        }
        
        try
        {
            _receiver = new GestureUdpReceiver(port, _controller);
            _receiver.GestureReceived += OnGestureReceived;
            _receiver.ErrorOccurred += OnReceiverError;
            _receiver.Start();
            
            StartListenerButton.IsEnabled = false;
            StopListenerButton.IsEnabled = true;
            PortTextBox.IsEnabled = false;
            
            ListenerStatusLabel.Text = $"Listening on :{port}";
            ListenerStatusLabel.Foreground = System.Windows.Media.Brushes.Green;
            
            Log($"UDP listener started on port {port}");
        }
        catch (Exception ex)
        {
            MessageBox.Show($"Failed to start listener: {ex.Message}", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
            Log($"Error starting listener: {ex.Message}");
        }
    }
    
    private async void OnStopListener(object sender, RoutedEventArgs e)
    {
        if (_receiver != null)
        {
            await _receiver.StopAsync();
            _receiver.GestureReceived -= OnGestureReceived;
            _receiver.ErrorOccurred -= OnReceiverError;
            _receiver.Dispose();
            _receiver = null;
        }
        
        StartListenerButton.IsEnabled = true;
        StopListenerButton.IsEnabled = false;
        PortTextBox.IsEnabled = true;
        
        ListenerStatusLabel.Text = "Stopped";
        ListenerStatusLabel.Foreground = System.Windows.Media.Brushes.Gray;
        
        Log("UDP listener stopped");
    }
    
    private void OnGestureReceived(object? sender, GestureData data)
    {
        Dispatcher.BeginInvoke(() =>
        {
            UpdateUI();
            Log($"Gesture: {data.Type} @ ({data.NormalizedX:F2}, {data.NormalizedY:F2}) conf={data.Confidence:F2}");
        });
    }
    
    private void OnReceiverError(object? sender, Exception ex)
    {
        Dispatcher.BeginInvoke(() =>
        {
            Log($"Receiver error: {ex.Message}");
        });
    }
    
    #endregion
    
    private async void OnWindowClosed(object? sender, EventArgs e)
    {
        if (_receiver != null)
        {
            await _receiver.StopAsync();
            _receiver.Dispose();
        }
        
        _controller.Dispose();
    }
}
