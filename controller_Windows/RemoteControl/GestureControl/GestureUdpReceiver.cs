using System;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace TestOnRemoteControl.GestureControl;

/// <summary>
/// UDP listener that receives gesture data from a CV module and routes it to the gesture controller.
/// Expects JSON-formatted gesture data packets.
/// </summary>
public class GestureUdpReceiver : IDisposable
{
    private readonly int _port;
    private readonly GestureDataAdapter _adapter;
    private UdpClient? _udpClient;
    private CancellationTokenSource? _cts;
    private Task? _receiveTask;
    private bool _disposed;
    
    /// <summary>
    /// Gets or sets the device ID filter. Only gestures with matching deviceId will be processed.
    /// Empty string or null means accept all devices.
    /// </summary>
    public string? DeviceIdFilter { get; set; }
    
    /// <summary>
    /// Gets or sets the screen index filter. Only gestures targeting this screen will be processed.
    /// -1 means accept gestures for any screen.
    /// </summary>
    public int ScreenIndexFilter { get; set; } = -1;
    
    /// <summary>
    /// Event raised when a gesture is received and processed.
    /// </summary>
    public event EventHandler<GestureData>? GestureReceived;
    
    /// <summary>
    /// Event raised when a gesture is filtered out (not processed).
    /// </summary>
    public event EventHandler<GestureData>? GestureFiltered;
    
    /// <summary>
    /// Event raised when an error occurs during receiving.
    /// </summary>
    public event EventHandler<Exception>? ErrorOccurred;
    
    /// <summary>
    /// Gets whether the receiver is currently running.
    /// </summary>
    public bool IsRunning => _receiveTask != null && !_receiveTask.IsCompleted;
    
    /// <summary>
    /// Creates a new gesture UDP receiver.
    /// </summary>
    /// <param name="port">UDP port to listen on</param>
    /// <param name="gestureHandler">The gesture handler to route actions to</param>
    public GestureUdpReceiver(int port, IGestureInputHandler gestureHandler)
    {
        _port = port;
        _adapter = new GestureDataAdapter(gestureHandler);
    }
    
    /// <summary>
    /// Starts listening for gesture data.
    /// </summary>
    public void Start()
    {
        if (_disposed) throw new ObjectDisposedException(nameof(GestureUdpReceiver));
        if (IsRunning) return;
        
        _udpClient = new UdpClient(_port);
        _cts = new CancellationTokenSource();
        _receiveTask = ReceiveLoopAsync(_cts.Token);
    }
    
    /// <summary>
    /// Stops listening for gesture data.
    /// </summary>
    public async Task StopAsync()
    {
        if (!IsRunning) return;
        
        _cts?.Cancel();
        
        // Close the UDP client to unblock the receive
        _udpClient?.Close();
        
        if (_receiveTask != null)
        {
            try
            {
                await _receiveTask;
            }
            catch (OperationCanceledException)
            {
                // Expected
            }
        }
        
        _udpClient?.Dispose();
        _udpClient = null;
        _cts?.Dispose();
        _cts = null;
    }
    
    private async Task ReceiveLoopAsync(CancellationToken cancellationToken)
    {
        while (!cancellationToken.IsCancellationRequested)
        {
            try
            {
                var result = await _udpClient!.ReceiveAsync(cancellationToken);
                var json = Encoding.UTF8.GetString(result.Buffer);
                
                var gestureData = ParseGestureData(json);
                if (gestureData.HasValue)
                {
                    var data = gestureData.Value;
                    
                    // Check device ID filter
                    if (!string.IsNullOrEmpty(DeviceIdFilter) && 
                        !string.IsNullOrEmpty(data.DeviceId) &&
                        data.DeviceId != DeviceIdFilter)
                    {
                        GestureFiltered?.Invoke(this, data);
                        continue;
                    }
                    
                    // Check screen index filter
                    if (ScreenIndexFilter >= 0 && 
                        data.ScreenIndex >= 0 &&
                        data.ScreenIndex != ScreenIndexFilter)
                    {
                        GestureFiltered?.Invoke(this, data);
                        continue;
                    }
                    
                    _adapter.ProcessGestureData(data);
                    GestureReceived?.Invoke(this, data);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (SocketException) when (cancellationToken.IsCancellationRequested)
            {
                break;
            }
            catch (Exception ex)
            {
                ErrorOccurred?.Invoke(this, ex);
            }
        }
    }
    
    /// <summary>
    /// Parses JSON gesture data from the CV module.
    /// Expected format:
    /// {
    ///   "type": "pointer|two_finger|swipe|pinch|thumbs_up|clap",
    ///   "deviceId": "device_1",
    ///   "x": 0.5,
    ///   "y": 0.5,
    ///   "fingerCount": 1,
    ///   "screenIndex": 0,
    ///   "stretch": 1.0,
    ///   "roll": 0.0,
    ///   "swipeDirection": "left|right|up|down",
    ///   "pinchActive": false,
    ///   "confidence": 0.95
    /// }
    /// </summary>
    private GestureData? ParseGestureData(string json)
    {
        try
        {
            using var doc = JsonDocument.Parse(json);
            var root = doc.RootElement;
            
            var data = new GestureData
            {
                Timestamp = DateTime.UtcNow,
                Confidence = GetFloatProperty(root, "confidence", 1.0f),
                DeviceId = GetStringProperty(root, "deviceId", "")
            };
            
            // Parse gesture type
            var typeStr = GetStringProperty(root, "type", "none").ToLowerInvariant();
            data.Type = typeStr switch
            {
                "pointer" or "point" or "single" => GestureType.Pointer,
                "two_finger" or "twofinger" or "zoom" => GestureType.TwoFingerPointer,
                "swipe" => GestureType.Swipe,
                "pinch" or "grab" => GestureType.Pinch,
                "thumbs_up" or "thumbsup" or "thumb" => GestureType.ThumbsUp,
                "clap" => GestureType.Clap,
                _ => GestureType.None
            };
            
            // Parse position
            data.NormalizedX = GetFloatProperty(root, "x", 0.5f);
            data.NormalizedY = GetFloatProperty(root, "y", 0.5f);
            data.FingerCount = GetIntProperty(root, "fingerCount", 1);
            
            // Parse screen index (-1 means use default)
            data.ScreenIndex = GetIntProperty(root, "screenIndex", -1);
            // Also support "screen" as alias
            if (data.ScreenIndex < 0)
            {
                data.ScreenIndex = GetIntProperty(root, "screen", -1);
            }
            
            // Parse gesture-specific data
            data.StretchValue = GetFloatProperty(root, "stretch", 1.0f);
            data.RollValue = GetFloatProperty(root, "roll", 0.0f);
            data.IsPinchActive = GetBoolProperty(root, "pinchActive", false);
            
            // Parse swipe direction
            var swipeStr = GetStringProperty(root, "swipeDirection", "").ToLowerInvariant();
            data.SwipeDirection = swipeStr switch
            {
                "left" => SwipeDirection.Left,
                "right" => SwipeDirection.Right,
                "up" => SwipeDirection.Up,
                "down" => SwipeDirection.Down,
                _ => SwipeDirection.Right
            };
            
            return data;
        }
        catch
        {
            return null;
        }
    }
    
    private static string GetStringProperty(JsonElement element, string name, string defaultValue)
    {
        return element.TryGetProperty(name, out var prop) ? prop.GetString() ?? defaultValue : defaultValue;
    }
    
    private static float GetFloatProperty(JsonElement element, string name, float defaultValue)
    {
        if (element.TryGetProperty(name, out var prop))
        {
            if (prop.ValueKind == JsonValueKind.Number)
            {
                return (float)prop.GetDouble();
            }
        }
        return defaultValue;
    }
    
    private static int GetIntProperty(JsonElement element, string name, int defaultValue)
    {
        if (element.TryGetProperty(name, out var prop))
        {
            if (prop.ValueKind == JsonValueKind.Number)
            {
                return prop.GetInt32();
            }
        }
        return defaultValue;
    }
    
    private static bool GetBoolProperty(JsonElement element, string name, bool defaultValue)
    {
        if (element.TryGetProperty(name, out var prop))
        {
            if (prop.ValueKind == JsonValueKind.True) return true;
            if (prop.ValueKind == JsonValueKind.False) return false;
        }
        return defaultValue;
    }
    
    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        
        _cts?.Cancel();
        _udpClient?.Close();
        _udpClient?.Dispose();
        _cts?.Dispose();
        
        _adapter.Reset();
        
        GC.SuppressFinalize(this);
    }
}
