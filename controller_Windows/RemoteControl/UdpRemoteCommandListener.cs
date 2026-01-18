using System;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using RemoteControlProtocol;

namespace TestOnRemoteControl;

public sealed class UdpRemoteCommandListener : IDisposable
{
    private readonly UdpClient _udp;
    private CancellationTokenSource? _cts;
    private Task? _loop;

    public UdpRemoteCommandListener(int port)
    {
        _udp = new UdpClient(port);
    }

    public void Start()
    {
        if (_cts != null) return;
        _cts = new CancellationTokenSource();
        _loop = Task.Run(() => LoopAsync(_cts.Token));
    }

    public async Task StopAsync()
    {
        var cts = _cts;
        if (cts == null) return;

        _cts = null;
        cts.Cancel();

        try { _udp.Close(); } catch { /* ignore */ }

        if (_loop != null)
        {
            try { await _loop.ConfigureAwait(false); } catch { /* ignore */ }
        }

        cts.Dispose();
    }

    private async Task LoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            UdpReceiveResult result;
            try
            {
                result = await _udp.ReceiveAsync(ct).ConfigureAwait(false);
            }
            catch (OperationCanceledException) { break; }
            catch (ObjectDisposedException) { break; }
            catch
            {
                await Task.Delay(100, ct).ConfigureAwait(false);
                continue;
            }

            var text = Encoding.UTF8.GetString(result.Buffer);
            if (!RemoteCommandCodec.TryDecode(text, out var cmd))
                continue;

            try
            {
                RemoteCommandExecutor.Execute(cmd);
            }
            catch
            {
                // Don't let exceptions break the listen loop
            }
        }
    }

    public void Dispose()
    {
        try { _udp.Dispose(); } catch { /* ignore */ }
        _cts?.Cancel();
        _cts?.Dispose();
    }
}
