using System;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Enumerates the gesture types that can be detected by the CV module.
/// </summary>
public enum GestureType
{
    None,
    Pointer,        // Single finger pointing
    TwoFingerPointer, // Two fingers (for zoom)
    Swipe,          // Quick swipe motion
    Pinch,          // Pinch gesture (click and hold)
    ThumbsUp,       // Thumbs up for scrolling
    Clap            // Clap for mode switching
}

/// <summary>
/// Represents raw gesture data from the Computer Vision module.
/// </summary>
public struct GestureData
{
    /// <summary>
    /// The type of gesture detected.
    /// </summary>
    public GestureType Type { get; set; }
    
    /// <summary>
    /// Normalized X position [0, 1] for pointer gestures.
    /// </summary>
    public float NormalizedX { get; set; }
    
    /// <summary>
    /// Normalized Y position [0, 1] for pointer gestures.
    /// </summary>
    public float NormalizedY { get; set; }
    
    /// <summary>
    /// Number of fingers detected (for pointer gestures).
    /// </summary>
    public int FingerCount { get; set; }
    
    /// <summary>
    /// Target screen index (0-based). -1 means use configured default.
    /// </summary>
    public int ScreenIndex { get; set; }
    
    /// <summary>
    /// Device identifier for multi-device setups. Empty string matches all devices.
    /// </summary>
    public string DeviceId { get; set; }
    
    /// <summary>
    /// Cumulative stretch value for zoom gestures.
    /// </summary>
    public float StretchValue { get; set; }
    
    /// <summary>
    /// Roll angle for thumbs up gesture (scrolling).
    /// </summary>
    public float RollValue { get; set; }
    
    /// <summary>
    /// Direction for swipe gestures.
    /// </summary>
    public SwipeDirection SwipeDirection { get; set; }
    
    /// <summary>
    /// Whether a pinch is currently active (pressed).
    /// </summary>
    public bool IsPinchActive { get; set; }
    
    /// <summary>
    /// Confidence score [0, 1] for the gesture detection.
    /// </summary>
    public float Confidence { get; set; }
    
    /// <summary>
    /// Timestamp when the gesture was detected.
    /// </summary>
    public DateTime Timestamp { get; set; }
}

/// <summary>
/// Adapter that converts raw CV gesture data to gesture controller actions.
/// Use this class to easily integrate your Computer Vision module.
/// </summary>
public class GestureDataAdapter
{
    private readonly IGestureInputHandler _handler;
    private GestureType _lastGestureType = GestureType.None;
    private bool _wasPinchActive;
    
    // Debouncing for discrete gestures
    private DateTime _lastSwipeTime = DateTime.MinValue;
    private DateTime _lastClapTime = DateTime.MinValue;
    private readonly TimeSpan _swipeDebounceInterval = TimeSpan.FromMilliseconds(500);
    private readonly TimeSpan _clapDebounceInterval = TimeSpan.FromMilliseconds(800);
    
    /// <summary>
    /// Minimum confidence required to process a gesture.
    /// </summary>
    public float MinConfidence { get; set; } = 0.7f;
    
    /// <summary>
    /// Creates a new adapter for the specified gesture handler.
    /// </summary>
    /// <param name="handler">The gesture handler to route actions to</param>
    public GestureDataAdapter(IGestureInputHandler handler)
    {
        _handler = handler ?? throw new ArgumentNullException(nameof(handler));
    }
    
    /// <summary>
    /// Processes raw gesture data and routes it to the appropriate handler method.
    /// Call this method with each frame of gesture data from your CV module.
    /// </summary>
    /// <param name="data">The gesture data to process</param>
    public void ProcessGestureData(GestureData data)
    {
        // Skip low-confidence detections
        if (data.Confidence < MinConfidence && data.Type != GestureType.None)
        {
            return;
        }
        
        // Handle gesture type transitions
        HandleGestureTransition(data.Type);
        
        // Process based on gesture type
        switch (data.Type)
        {
            case GestureType.Pointer:
                _handler.UpdateFingerPosition(data.NormalizedX, data.NormalizedY, 1, data.ScreenIndex);
                break;
                
            case GestureType.TwoFingerPointer:
                _handler.UpdateFingerPosition(data.NormalizedX, data.NormalizedY, 2, data.ScreenIndex);
                _handler.UpdateZoom(data.StretchValue);
                break;
                
            case GestureType.Swipe:
                ProcessSwipe(data);
                break;
                
            case GestureType.Pinch:
                ProcessPinch(data);
                break;
                
            case GestureType.ThumbsUp:
                _handler.UpdateThumbsUpRoll(data.RollValue);
                break;
                
            case GestureType.Clap:
                ProcessClap(data);
                break;
                
            case GestureType.None:
                // Handle end of gestures
                HandleNoGesture();
                break;
        }
        
        _lastGestureType = data.Type;
    }
    
    /// <summary>
    /// Handles the transition between gesture types.
    /// </summary>
    private void HandleGestureTransition(GestureType newType)
    {
        if (_lastGestureType == newType) return;
        
        // End previous gesture if needed
        switch (_lastGestureType)
        {
            case GestureType.Pinch:
                if (_wasPinchActive)
                {
                    _handler.EndPinch();
                    _wasPinchActive = false;
                }
                break;
                
            case GestureType.TwoFingerPointer:
                // Reset zoom state when transitioning away from zoom gesture
                if (_handler is GestureController controller)
                {
                    controller.ResetZoomState();
                }
                break;
                
            case GestureType.ThumbsUp:
                // Reset scroll state when transitioning away from thumbs up
                if (_handler is GestureController ctrl)
                {
                    ctrl.ResetScrollState();
                }
                break;
        }
    }
    
    /// <summary>
    /// Handles the case when no gesture is detected.
    /// </summary>
    private void HandleNoGesture()
    {
        // Release pinch if it was active
        if (_wasPinchActive)
        {
            _handler.EndPinch();
            _wasPinchActive = false;
        }
    }
    
    /// <summary>
    /// Processes a swipe gesture with debouncing.
    /// </summary>
    private void ProcessSwipe(GestureData data)
    {
        var now = DateTime.UtcNow;
        if (now - _lastSwipeTime < _swipeDebounceInterval)
        {
            return; // Debounce
        }
        
        _handler.TriggerSwipe(data.SwipeDirection);
        _lastSwipeTime = now;
    }
    
    /// <summary>
    /// Processes a pinch gesture, handling start/end states.
    /// </summary>
    private void ProcessPinch(GestureData data)
    {
        if (data.IsPinchActive && !_wasPinchActive)
        {
            // IMPORTANT: Move cursor to position BEFORE mouse down
            // This prevents cursor drift when pinch starts
            _handler.UpdateFingerPosition(data.NormalizedX, data.NormalizedY, 1, data.ScreenIndex);
            _handler.StartPinch();
            _wasPinchActive = true;
        }
        else if (!data.IsPinchActive && _wasPinchActive)
        {
            _handler.EndPinch();
            _wasPinchActive = false;
        }
        else if (data.IsPinchActive)
        {
            // During ongoing pinch, still update position for drag operations
            // but with the locked position from Python, this won't cause drift
            _handler.UpdateFingerPosition(data.NormalizedX, data.NormalizedY, 1, data.ScreenIndex);
        }
    }
    
    /// <summary>
    /// Processes a clap gesture with debouncing.
    /// </summary>
    private void ProcessClap(GestureData data)
    {
        var now = DateTime.UtcNow;
        if (now - _lastClapTime < _clapDebounceInterval)
        {
            return; // Debounce
        }
        
        _handler.ToggleLaserMode();
        _lastClapTime = now;
    }
    
    /// <summary>
    /// Resets the adapter state. Call when gesture tracking is lost.
    /// </summary>
    public void Reset()
    {
        if (_wasPinchActive)
        {
            _handler.EndPinch();
            _wasPinchActive = false;
        }
        
        _lastGestureType = GestureType.None;
        
        if (_handler is GestureController controller)
        {
            controller.ResetAllState();
        }
    }
}
