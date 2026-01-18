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

    public MainWindow()
    {
        MouseController.MoveAbsolute(0,0);
        InitializeComponent();

        Loaded += (_, _) => _listener.Start();
        Closed += async (_, _) => await _listener.StopAsync();
    }


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