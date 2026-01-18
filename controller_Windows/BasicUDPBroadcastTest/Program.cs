// See https://aka.ms/new-console-template for more information

using System;
using System.Globalization;
using BasicUDPBroadcastTest;
using RemoteControlProtocol;

namespace BasicUDPBroadcastTest;

internal static class Program
{
    private const int DefaultPort = 8080;

    private static int Main(string[] args)
    {
        var port = DefaultPort;
        if (args.Length >= 1 && int.TryParse(args[0], out var parsedPort))
            port = parsedPort;

        Console.WriteLine("Remote Controller Terminal (UDP Broadcast)");
        Console.WriteLine($"Target port: {port}");
        Console.WriteLine("Type 'help' for commands. Type 'exit' to quit.");

        while (true)
        {
            Console.Write("> ");
            var line = Console.ReadLine();
            if (line == null) break;

            line = line.Trim();
            if (line.Length == 0) continue;

            if (line.Equals("exit", StringComparison.OrdinalIgnoreCase) || line.Equals("quit", StringComparison.OrdinalIgnoreCase))
                break;

            if (line.Equals("help", StringComparison.OrdinalIgnoreCase) || line.Equals("?", StringComparison.OrdinalIgnoreCase))
            {
                PrintHelp();
                continue;
            }

            // Allow changing port dynamically: port 8081
            if (TryHandlePortCommand(line, ref port))
                continue;

            // 1) First try parsing as a raw protocol line (e.g. Zoom:1 / Move:10,-5)
            if (RemoteCommandCodec.TryDecode(line, out var cmdFromProtocol))
            {
                Send(cmdFromProtocol, port);
                continue;
            }

            // 2) Then try parsing as a friendly command (e.g. zoomin / move 10 -5)
            if (!TryParseFriendlyCommand(line, out var cmd, out var error))
            {
                Console.WriteLine(error);
                continue;
            }

            Send(cmd, port);
        }

        return 0;
    }

    private static void Send(RemoteCommand cmd, int port)
    {
        var payload = RemoteCommandCodec.Encode(cmd);
        UdpBroadcaster.SendBroadcast(payload, port);
    }

    private static bool TryHandlePortCommand(string line, ref int port)
    {
        // Supports: port 8080
        var parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 2 && parts[0].Equals("port", StringComparison.OrdinalIgnoreCase) && int.TryParse(parts[1], out var p))
        {
            port = p;
            Console.WriteLine($"Port set to {port}");
            return true;
        }

        return false;
    }

    private static bool TryParseFriendlyCommand(string line, out RemoteCommand cmd, out string error)
    {
        cmd = default!;
        error = string.Empty;

        var parts = line.Split(' ', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries);
        if (parts.Length == 0)
        {
            error = "Empty command";
            return false;
        }

        var verb = parts[0].ToLowerInvariant();
        switch (verb)
        {
            case "zoomin":
                cmd = new RemoteCommand(RemoteCommandType.Zoom, +1);
                return true;

            case "zoomout":
                cmd = new RemoteCommand(RemoteCommandType.Zoom, -1);
                return true;

            case "zoom":
                if (parts.Length < 2 || !int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var steps))
                {
                    error = "Usage: zoom <steps>    (e.g. zoom 3 | zoom -2)";
                    return false;
                }
                cmd = new RemoteCommand(RemoteCommandType.Zoom, steps);
                return true;

            case "move":
                if (parts.Length < 3 ||
                    !int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var dx) ||
                    !int.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out var dy))
                {
                    error = "Usage: move <dx> <dy>  (e.g. move 10 -5)";
                    return false;
                }
                cmd = new RemoteCommand(RemoteCommandType.MoveRelative, dx, dy);
                return true;

            case "leftclick":
            case "lc":
                cmd = new RemoteCommand(RemoteCommandType.LeftClick);
                return true;

            case "rightclick":
            case "rc":
                cmd = new RemoteCommand(RemoteCommandType.RightClick);
                return true;

            case "scroll":
                if (parts.Length < 2 || !int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var delta))
                {
                    error = "Usage: scroll <delta> (e.g. scroll 120 | scroll -120)";
                    return false;
                }
                cmd = new RemoteCommand(RemoteCommandType.Scroll, delta);
                return true;

            case "abs":
            case "moveabs":
                if (parts.Length < 4 ||
                    !int.TryParse(parts[1], NumberStyles.Integer, CultureInfo.InvariantCulture, out var screen) ||
                    !int.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out var x) ||
                    !int.TryParse(parts[3], NumberStyles.Integer, CultureInfo.InvariantCulture, out var y))
                {
                    error = "Usage: abs <screen> <x> <y>   (e.g. abs 0 960 540)";
                    return false;
                }

                cmd = new RemoteCommand(RemoteCommandType.MoveAbsolute, screen, x, y);
                return true;

            case "pinch":
                // pinch in 3  | pinch out 2
                if (parts.Length < 3)
                {
                    error = "Usage: pinch <in|out> <steps>  (e.g. pinch out 2)";
                    return false;
                }

                var dirToken = parts[1].ToLowerInvariant();
                var direction = dirToken switch
                {
                    "out" or "+" or "+1" => 1,
                    "in" or "-" or "-1" => -1,
                    _ => 0
                };

                if (direction == 0)
                {
                    error = "pinch direction must be 'in' or 'out'";
                    return false;
                }

                if (!int.TryParse(parts[2], NumberStyles.Integer, CultureInfo.InvariantCulture, out var pinchSteps))
                {
                    error = "pinch steps must be an integer";
                    return false;
                }

                cmd = new RemoteCommand(RemoteCommandType.Pinch, direction, pinchSteps);
                return true;

            default:
                error = "Unknown command. Type 'help' to see available commands.";
                return false;
        }
    }

    private static void PrintHelp()
    {
        Console.WriteLine();
        Console.WriteLine("Friendly commands:");
        Console.WriteLine("  zoomin              (Zoom +1)");
        Console.WriteLine("  zoomout             (Zoom -1)");
        Console.WriteLine("  zoom <steps>        (e.g. zoom 3 | zoom -2)");
        Console.WriteLine("  move <dx> <dy>      (relative move)");
        Console.WriteLine("  leftclick | lc");
        Console.WriteLine("  rightclick | rc");
        Console.WriteLine("  scroll <delta>      (wheel delta, usually +/-120)");
        Console.WriteLine("  port <port>         (change target port)");
        Console.WriteLine("  exit                (quit)");
        Console.WriteLine("  abs <screen> <x> <y> (absolute move on a screen)");
        Console.WriteLine("  pinch <in|out> <n>   (touch-style pinch gesture)");
        Console.WriteLine();
        Console.WriteLine("Raw protocol lines are also accepted:");
        Console.WriteLine("  Zoom:1");
        Console.WriteLine("  Scroll:-120");
        Console.WriteLine("  Move:10,-5");
        Console.WriteLine("  LeftClick");
        Console.WriteLine("  RightClick");
        Console.WriteLine("  Abs:0,960,540");
        Console.WriteLine("  Pinch:1,3");
        Console.WriteLine();
    }
}
// Broadcast "Hello Everyone" to all programs on the LAN listening on port 8080
