 using System;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Interface for handling gesture input from Computer Vision module.
/// Provides methods for continuous and discrete gesture events.
/// </summary>
public interface IGestureInputHandler
{
    /// <summary>
    /// Gets the current gesture mode.
    /// </summary>
    GestureMode CurrentMode { get; }
    
    /// <summary>
    /// Gets whether a pinch (click-hold) is currently active.
    /// </summary>
    bool IsPinchActive { get; }
    
    /// <summary>
    /// Gets or sets the target screen index for gesture control.
    /// </summary>
    int TargetScreenIndex { get; set; }
    
    /// <summary>
    /// Event raised when the gesture mode changes.
    /// </summary>
    event EventHandler<GestureModeChangedEventArgs>? ModeChanged;
    
    /// <summary>
    /// Event raised when the target screen changes.
    /// </summary>
    event EventHandler<ScreenChangedEventArgs>? TargetScreenChanged;
    
    /// <summary>
    /// Updates the finger/pointer position for cursor control.
    /// In Cursor Mode: Moves the system cursor.
    /// In Laser Mode: Moves the laser pointer dot.
    /// </summary>
    /// <param name="normalizedX">X position normalized to [0, 1] where 0=left, 1=right</param>
    /// <param name="normalizedY">Y position normalized to [0, 1] where 0=top, 1=bottom</param>
    /// <param name="fingerCount">Number of fingers detected (1 = move cursor, 2 = zoom gesture)</param>
    /// <param name="screenIndex">Target screen index (-1 to use configured default)</param>
    void UpdateFingerPosition(float normalizedX, float normalizedY, int fingerCount = 1, int screenIndex = -1);
    
    /// <summary>
    /// Updates the cumulative zoom/stretch value for two-finger zoom gestures.
    /// Delta changes are converted to Ctrl + MouseWheel events.
    /// </summary>
    /// <param name="cumulativeStretchValue">Cumulative stretch value (Σ). Increasing = zoom in, decreasing = zoom out</param>
    void UpdateZoom(float cumulativeStretchValue);
    
    /// <summary>
    /// Triggers a swipe gesture action (Alt+Tab or Win+Tab for app switching).
    /// </summary>
    /// <param name="direction">Direction of the swipe</param>
    void TriggerSwipe(SwipeDirection direction);
    
    /// <summary>
    /// Starts a pinch gesture - initiates a "Click and Hold" (Left Mouse Down).
    /// </summary>
    void StartPinch();
    
    /// <summary>
    /// Ends a pinch gesture - releases the held click (Left Mouse Up).
    /// </summary>
    void EndPinch();
    
    /// <summary>
    /// Updates the roll value from a Thumbs Up gesture for vertical scrolling.
    /// </summary>
    /// <param name="rollValue">Roll angle/value. Positive = scroll up, negative = scroll down</param>
    void UpdateThumbsUpRoll(float rollValue);
    
    /// <summary>
    /// Toggles between Cursor Mode and Laser Pointer Mode.
    /// Called when a Clap gesture is detected.
    /// </summary>
    void ToggleLaserMode();
    
    /// <summary>
    /// Sets the gesture mode explicitly.
    /// </summary>
    /// <param name="mode">The mode to switch to</param>
    void SetMode(GestureMode mode);
    
    /// <summary>
    /// Cleans up resources and resets state.
    /// </summary>
    void Shutdown();
}

/// <summary>
/// Defines the available gesture control modes.
/// </summary>
public enum GestureMode
{
    /// <summary>
    /// Standard cursor control mode - gestures control the system mouse.
    /// </summary>
    Cursor,
    
    /// <summary>
    /// Laser pointer mode - displays a red dot overlay with trail effect.
    /// </summary>
    LaserPointer
}

/// <summary>
/// Defines swipe gesture directions.
/// </summary>
public enum SwipeDirection
{
    Left,
    Right,
    Up,
    Down
}

/// <summary>
/// Event args for mode change events.
/// </summary>
public class GestureModeChangedEventArgs : EventArgs
{
    public GestureMode OldMode { get; }
    public GestureMode NewMode { get; }
    
    public GestureModeChangedEventArgs(GestureMode oldMode, GestureMode newMode)
    {
        OldMode = oldMode;
        NewMode = newMode;
    }
}

/// <summary>
/// Event args for screen change events.
/// </summary>
public class ScreenChangedEventArgs : EventArgs
{
    public int OldScreenIndex { get; }
    public int NewScreenIndex { get; }
    public ScreenManager.ScreenInfo? ScreenInfo { get; }
    
    public ScreenChangedEventArgs(int oldScreenIndex, int newScreenIndex)
    {
        OldScreenIndex = oldScreenIndex;
        NewScreenIndex = newScreenIndex;
        ScreenInfo = ScreenManager.GetScreen(newScreenIndex);
    }
}

