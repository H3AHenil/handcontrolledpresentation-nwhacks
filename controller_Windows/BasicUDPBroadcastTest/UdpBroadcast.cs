namespace BasicUDPBroadcastTest;

using System;
using System.Net;
using System.Net.Sockets;
using System.Text;

public class UdpBroadcaster
{
    public static void SendBroadcast(string message, int targetPort)
    {
        // 1. Create UdpClient (no need to bind a port; the system will assign a send port automatically)
        UdpClient client = new UdpClient();

        try
        {
            // [Key point 1] Allow sending broadcast packets. Without this you may get "Access denied" or similar errors.
            client.EnableBroadcast = true;

            // [Key point 2] Set target to the broadcast address (255.255.255.255)
            // This means every device on the LAN listening on targetPort can receive it.
            IPEndPoint targetEndPoint = new IPEndPoint(IPAddress.Broadcast, targetPort);

            // 3. Encode payload
            byte[] data = Encoding.UTF8.GetBytes(message);

            // 4. Send data
            client.Send(data, data.Length, targetEndPoint);

            Console.WriteLine($"Broadcasted: \"{message}\" to port {targetPort}");
        }
        catch (Exception e)
        {
            Console.WriteLine($"Send failed: {e.Message}");
        }
        finally
        {
            client.Close();
        }
    }
}