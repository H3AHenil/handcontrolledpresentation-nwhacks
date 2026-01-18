using System;
using System.Windows;
using System.Windows.Threading;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// Main controller that implements gesture-to-action mapping.
/// Handles all gesture types and controls mode switching between Cursor and Laser Pointer modes.
/// </summary>
public class GestureController : IGestureInputHandler, IDisposable
{
    #region Configuration
    
    /// <summary>
    /// Configuration settings for the gesture controller.
    /// </summary>
    public class ControllerConfiguration
    {
        /// <summary>
        /// Zoom sensitivity - how much a stretch value change translates to wheel steps.
        /// </summary>
        public float ZoomSensitivity { get; set; } = 100.0f;
        
        /// <summary>
        /// Scroll sensitivity - how much roll value translates to wheel delta.
        /// </summary>
        public float ScrollSensitivity { get; set; } = 50.0f;
        
        /// <summary>
        /// Minimum stretch delta required to trigger a zoom step.
        /// </summary>
        public float ZoomThreshold { get; set; } = 0.01f;
        
        /// <summary>
        /// Minimum roll delta required to trigger a scroll.
        /// </summary>
        public float ScrollThreshold { get; set; } = 0.05f;
        
        /// <summary>
        /// Target monitor index for absolute positioning (0 = primary).
        /// </summary>
        public int TargetMonitorIndex { get; set; } = 0;
        
        /// <summary>
        /// Whether to use Win+Tab instead of Alt+Tab for swipes.
        /// </summary>
        public bool UseWinTabForSwipe { get; set; } = false;
        
        /// <summary>
        /// Cursor movement smoothing factor (0 = no smoothing, 1 = maximum smoothing).
        /// </summary>
        public float MovementSmoothing { get; set; } = 0.3f;
    }
    
    #endregion
    
    #region Private Fields
    
    private readonly ControllerConfiguration _config;
    private readonly Dispatcher _dispatcher;
    private LaserPointerOverlay? _laserOverlay;
    
    // State tracking
    private GestureMode _currentMode = GestureMode.Cursor;
    private bool _isPinchActive;
    private float _lastZoomValue;
    private float _lastRollValue;
    private float _zoomAccumulator;
    private float _scrollAccumulator;
    private bool _isFirstZoomUpdate = true;
    private bool _isFirstRollUpdate = true;
    
    // Screen targeting
    private int _targetScreenIndex = 0;
    
    // Smoothing state
    private float _smoothedX;
    private float _smoothedY;
    private bool _isFirstPositionUpdate = true;
    
    // Cursor visibility tracking
    private int _cursorHideCount;
    
    // Disposed flag
    private bool _disposed;
    
    #endregion
    
    #region Properties
    
    /// <inheritdoc />
    public GestureMode CurrentMode => _currentMode;
    
    /// <inheritdoc />
    public bool IsPinchActive => _isPinchActive;
    
    /// <inheritdoc />
    public int TargetScreenIndex
    {
        get => _targetScreenIndex;
        set
        {
            if (_targetScreenIndex != value)
            {
                var oldIndex = _targetScreenIndex;
                _targetScreenIndex = value;
                
                // Update laser overlay if active
                if (_laserOverlay != null && _currentMode == GestureMode.LaserPointer)
                {
                    _dispatcher.BeginInvoke(() =>
                    {
                        _laserOverlay.SetTargetScreen(value);
                    });
                }
                
                TargetScreenChanged?.Invoke(this, new ScreenChangedEventArgs(oldIndex, value));
            }
        }
    }
    
    /// <summary>
    /// Gets the configuration for this controller.
    /// </summary>
    public ControllerConfiguration Configuration => _config;
    
    #endregion
    
    #region Events
    
    /// <inheritdoc />
    public event EventHandler<GestureModeChangedEventArgs>? ModeChanged;
    
    /// <inheritdoc />
    public event EventHandler<ScreenChangedEventArgs>? TargetScreenChanged;
    
    #endregion
    
    #region Constructors
    
    /// <summary>
    /// Creates a new GestureController with default configuration.
    /// </summary>
    public GestureController() : this(new ControllerConfiguration())
    {
    }
    
    /// <summary>
    /// Creates a new GestureController with the specified configuration.
    /// </summary>
    /// <param name="configuration">Configuration settings</param>
    public GestureController(ControllerConfiguration configuration)
    {
        _config = configuration ?? throw new ArgumentNullException(nameof(configuration));
        _dispatcher = Application.Current?.Dispatcher ?? Dispatcher.CurrentDispatcher;
    }
    
    #endregion
    
    #region IGestureInputHandler Implementation
    
    /// <inheritdoc />
    public void UpdateFingerPosition(float normalizedX, float normalizedY, int fingerCount = 1, int screenIndex = -1)
    {
        ThrowIfDisposed();
        
        // Use provided screen index or default to configured target
        int effectiveScreenIndex = screenIndex >= 0 ? screenIndex : _targetScreenIndex;
        
        // Apply smoothing for more natural movement
        if (_isFirstPositionUpdate)
        {
            _smoothedX = normalizedX;
            _smoothedY = normalizedY;
            _isFirstPositionUpdate = false;
        }
        else
        {
            float smoothing = _config.MovementSmoothing;
            _smoothedX = _smoothedX * smoothing + normalizedX * (1 - smoothing);
            _smoothedY = _smoothedY * smoothing + normalizedY * (1 - smoothing);
        }
        
        // If two fingers, this might be a zoom gesture - handle position differently
        // For single finger, always update position
        if (fingerCount == 1)
        {
            UpdatePositionInternal(_smoothedX, _smoothedY, effectiveScreenIndex);
        }
        // For 2 fingers, we might want to update position for context
        // but zoom is handled separately via UpdateZoom
    }
    
    private void UpdatePositionInternal(float normalizedX, float normalizedY, int screenIndex)
    {
        if (_currentMode == GestureMode.Cursor)
        {
            // Move system cursor to specific screen (using physical coordinates)
            if (DpiAwareScreenManager.NormalizedToPhysical(screenIndex, normalizedX, normalizedY, 
                                                            out int physicalX, out int physicalY))
            {
                Win32InputSimulator.SetCursorPosition(physicalX, physicalY);
            }
            else
            {
                // Fallback to primary screen normalized positioning
                Win32InputSimulator.SetCursorPositionNormalized(normalizedX, normalizedY);
            }
        }
        else if (_currentMode == GestureMode.LaserPointer)
        {
            // Update laser pointer overlay
            _dispatcher.BeginInvoke(() =>
            {
                EnsureLaserOverlay();
                if (_laserOverlay != null)
                {
                    if (DpiAwareScreenManager.NormalizedToPhysical(screenIndex, normalizedX, normalizedY,
                                                                    out int physicalX, out int physicalY))
                    {
                        _laserOverlay.UpdatePosition(physicalX, physicalY);
                    }
                    else
                    {
                        _laserOverlay.UpdatePositionNormalized(normalizedX, normalizedY);
                    }
                }
            });
        }
    }
    
    /// <inheritdoc />
    public void UpdateZoom(float cumulativeStretchValue)
    {
        ThrowIfDisposed();
        
        if (_isFirstZoomUpdate)
        {
            _lastZoomValue = cumulativeStretchValue;
            _isFirstZoomUpdate = false;
            return;
        }
        
        // Calculate delta from last value
        float delta = cumulativeStretchValue - _lastZoomValue;
        _lastZoomValue = cumulativeStretchValue;
        
        // Accumulate delta
        _zoomAccumulator += delta * _config.ZoomSensitivity;
        
        // Convert accumulated value to discrete wheel steps
        int steps = (int)(_zoomAccumulator / Win32InputSimulator.WHEEL_DELTA);
        
        if (steps != 0)
        {
            // Send Ctrl + Wheel for zoom
            Win32InputSimulator.ZoomWithCtrlWheel(steps);
            
            // Remove the consumed amount from accumulator
            _zoomAccumulator -= steps * Win32InputSimulator.WHEEL_DELTA;
        }
    }
    
    /// <inheritdoc />
    public void TriggerSwipe(SwipeDirection direction)
    {
        ThrowIfDisposed();
        
        switch (direction)
        {
            case SwipeDirection.Left:
                // Previous window/app
                if (_config.UseWinTabForSwipe)
                {
                    Win32InputSimulator.TriggerWinTab();
                }
                else
                {
                    Win32InputSimulator.TriggerAltTab(reverse: true);
                }
                break;
                
            case SwipeDirection.Right:
                // Next window/app
                if (_config.UseWinTabForSwipe)
                {
                    Win32InputSimulator.TriggerWinTab();
                }
                else
                {
                    Win32InputSimulator.TriggerAltTab(reverse: false);
                }
                break;
                
            case SwipeDirection.Up:
                // Could be mapped to Task View or other action
                Win32InputSimulator.TriggerWinTab();
                break;
                
            case SwipeDirection.Down:
                // Could be mapped to show desktop or minimize
                // For now, using Win+Tab as well
                Win32InputSimulator.CancelTaskSwitcher();
                break;
        }
    }
    
    /// <inheritdoc />
    public void StartPinch()
    {
        ThrowIfDisposed();
        
        if (_isPinchActive) return;
        
        _isPinchActive = true;
        Win32InputSimulator.LeftMouseDown();
    }
    
    /// <inheritdoc />
    public void EndPinch()
    {
        ThrowIfDisposed();
        
        if (!_isPinchActive) return;
        
        _isPinchActive = false;
        Win32InputSimulator.LeftMouseUp();
    }
    
    /// <inheritdoc />
    public void UpdateThumbsUpRoll(float rollValue)
    {
        ThrowIfDisposed();
        
        if (_isFirstRollUpdate)
        {
            _lastRollValue = rollValue;
            _isFirstRollUpdate = false;
            return;
        }
        
        // Calculate delta from last value
        float delta = rollValue - _lastRollValue;
        _lastRollValue = rollValue;
        
        // Ignore small changes (noise filtering)
        if (Math.Abs(delta) < _config.ScrollThreshold)
        {
            return;
        }
        
        // Accumulate and convert to scroll amount
        _scrollAccumulator += delta * _config.ScrollSensitivity;
        
        // Convert to discrete wheel steps
        int scrollAmount = (int)_scrollAccumulator;
        
        if (Math.Abs(scrollAmount) >= Win32InputSimulator.WHEEL_DELTA / 2)
        {
            // Normalize to WHEEL_DELTA multiples for smooth scrolling
            int steps = scrollAmount / (Win32InputSimulator.WHEEL_DELTA / 2);
            int wheelDelta = steps * (Win32InputSimulator.WHEEL_DELTA / 2);
            
            Win32InputSimulator.ScrollVertical(wheelDelta);
            _scrollAccumulator -= wheelDelta;
        }
    }
    
    /// <inheritdoc />
    public void ToggleLaserMode()
    {
        ThrowIfDisposed();
        
        if (_currentMode == GestureMode.Cursor)
        {
            SetMode(GestureMode.LaserPointer);
        }
        else
        {
            SetMode(GestureMode.Cursor);
        }
    }
    
    /// <inheritdoc />
    public void SetMode(GestureMode mode)
    {
        ThrowIfDisposed();
        
        if (_currentMode == mode) return;
        
        var oldMode = _currentMode;
        _currentMode = mode;
        
        _dispatcher.BeginInvoke(() =>
        {
            switch (mode)
            {
                case GestureMode.LaserPointer:
                    EnableLaserMode();
                    break;
                    
                case GestureMode.Cursor:
                    DisableLaserMode();
                    break;
            }
        });
        
        ModeChanged?.Invoke(this, new GestureModeChangedEventArgs(oldMode, mode));
    }
    
    /// <inheritdoc />
    public void Shutdown()
    {
        Dispose();
    }
    
    #endregion
    
    #region Private Methods
    
    private void EnsureLaserOverlay()
    {
        if (_laserOverlay == null)
        {
            _laserOverlay = new LaserPointerOverlay(_targetScreenIndex);
        }
        else if (_laserOverlay.TargetScreenIndex != _targetScreenIndex)
        {
            _laserOverlay.SetTargetScreen(_targetScreenIndex);
        }
    }
    
    private void EnableLaserMode()
    {
        EnsureLaserOverlay();
        _laserOverlay!.ShowOnScreen(_targetScreenIndex);
        
        // Hide the system cursor
        HideCursor();
        
        // Get current cursor position and set laser there
        if (Win32InputSimulator.GetCursorPosition(out int x, out int y))
        {
            _laserOverlay.UpdatePosition(x, y);
        }
    }
    
    private void DisableLaserMode()
    {
        _laserOverlay?.Hide();
        
        // Show the system cursor again
        ShowCursor();
    }
    
    private void HideCursor()
    {
        // ShowCursor returns a counter - we need to hide until it goes negative
        while (Win32InputSimulator.SetCursorVisibility(false) >= 0)
        {
            _cursorHideCount++;
        }
        _cursorHideCount++;
    }
    
    private void ShowCursor()
    {
        // Restore cursor visibility
        for (int i = 0; i < _cursorHideCount; i++)
        {
            Win32InputSimulator.SetCursorVisibility(true);
        }
        _cursorHideCount = 0;
    }
    
    private void ThrowIfDisposed()
    {
        if (_disposed)
        {
            throw new ObjectDisposedException(nameof(GestureController));
        }
    }
    
    #endregion
    
    #region Reset Methods
    
    /// <summary>
    /// Resets the zoom tracking state. Call this when starting a new zoom gesture.
    /// </summary>
    public void ResetZoomState()
    {
        _isFirstZoomUpdate = true;
        _zoomAccumulator = 0;
    }
    
    /// <summary>
    /// Resets the scroll/roll tracking state. Call this when starting a new roll gesture.
    /// </summary>
    public void ResetScrollState()
    {
        _isFirstRollUpdate = true;
        _scrollAccumulator = 0;
    }
    
    /// <summary>
    /// Resets the position smoothing state.
    /// </summary>
    public void ResetPositionState()
    {
        _isFirstPositionUpdate = true;
    }
    
    /// <summary>
    /// Resets all tracking state. Useful when gesture tracking is lost or reset.
    /// </summary>
    public void ResetAllState()
    {
        ResetZoomState();
        ResetScrollState();
        ResetPositionState();
        
        // Also release any held buttons
        if (_isPinchActive)
        {
            EndPinch();
        }
    }
    
    #endregion
    
    #region IDisposable
    
    /// <summary>
    /// Disposes of the controller and releases all resources.
    /// </summary>
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        
        // Release any held mouse button
        if (_isPinchActive)
        {
            Win32InputSimulator.LeftMouseUp();
            _isPinchActive = false;
        }
        
        // Restore cursor if hidden
        ShowCursor();
        
        // Close the laser overlay
        _dispatcher.BeginInvoke(() =>
        {
            _laserOverlay?.Close();
            _laserOverlay = null;
        });
        
        GC.SuppressFinalize(this);
    }
    
    ~GestureController()
    {
        Dispose();
    }
    
    #endregion
}
