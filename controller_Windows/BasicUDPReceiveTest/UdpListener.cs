namespace basic_test;

using System;
using System.Net;
using System.Net.Sockets;
using System.Text;

public class UdpListener
{
    // 1. Configure the listen port (e.g., 8080)
    public static void StartListening(int port = 8080)
    {
        // 2. Initialize UdpClient
        // Note: we don't need to bind an IP here. Specifying the port will bind to all local interfaces (0.0.0.0).
        UdpClient udpClient = new UdpClient(port);

        // 3. Create an EndPoint to store sender information
        // IPAddress.Any means we can receive data from any IP.
        // Port 0 means we'll get the sender's actual port when receiving data.
        IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);

        Console.WriteLine($"Listening on port {port}...");

        try
        {
            while (true)
            {
                // 4. Receive data (the program blocks here until data arrives)
                // ref remoteEndPoint will be populated with the sender's actual IP and port
                byte[] receivedBytes = udpClient.Receive(ref remoteEndPoint);

                // 5. Handle data (e.g., convert to a string)
                string receivedString = Encoding.UTF8.GetString(receivedBytes);

                Console.WriteLine($"Message received from {remoteEndPoint.Address}:{remoteEndPoint.Port}:");
                Console.WriteLine($"Content: {receivedString}");
                Console.WriteLine("--------------------------------");
            }
        }
        catch (Exception e)
        {
            Console.WriteLine(e.ToString());
        }
        finally
        {
            udpClient.Close();
        }
    }
}