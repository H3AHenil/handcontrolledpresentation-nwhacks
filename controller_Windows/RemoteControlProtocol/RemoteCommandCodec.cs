using System;
using System.Globalization;

namespace RemoteControlProtocol;

/// <summary>
/// Minimal text protocol: one command per line.
/// Format examples:
/// - "Move:dx,dy"
/// - "Abs:screen,x,y"
/// - "Scroll:120"
/// - "Zoom:+1"   (Ctrl+Wheel fallback)
/// - "Pinch:+1,3" (simulated touch pinch: direction(+1 out/-1 in), steps)
/// - "LeftClick" / "RightClick"
/// </summary>
public static class RemoteCommandCodec
{
    public static string Encode(RemoteCommand cmd)
    {
        return cmd.Type switch
        {
            RemoteCommandType.Zoom => $"Zoom:{cmd.Arg1.ToString(CultureInfo.InvariantCulture)}",
            RemoteCommandType.Pinch => $"Pinch:{cmd.Arg1.ToString(CultureInfo.InvariantCulture)},{cmd.Arg2.ToString(CultureInfo.InvariantCulture)}",
            RemoteCommandType.Scroll => $"Scroll:{cmd.Arg1.ToString(CultureInfo.InvariantCulture)}",
            RemoteCommandType.MoveRelative => $"Move:{cmd.Arg1.ToString(CultureInfo.InvariantCulture)},{cmd.Arg2.ToString(CultureInfo.InvariantCulture)}",
            RemoteCommandType.MoveAbsolute => $"Abs:{cmd.Arg1.ToString(CultureInfo.InvariantCulture)},{cmd.Arg2.ToString(CultureInfo.InvariantCulture)},{cmd.Arg3.ToString(CultureInfo.InvariantCulture)}",
            RemoteCommandType.LeftClick => "LeftClick",
            RemoteCommandType.RightClick => "RightClick",
            _ => throw new ArgumentOutOfRangeException(nameof(cmd.Type), cmd.Type, null)
        };
    }

    public static bool TryDecode(string? text, out RemoteCommand command)
    {
        command = default!;
        if (string.IsNullOrWhiteSpace(text)) return false;

        text = text.Trim();

        if (text.Equals("LeftClick", StringComparison.OrdinalIgnoreCase))
        {
            command = new RemoteCommand(RemoteCommandType.LeftClick);
            return true;
        }

        if (text.Equals("RightClick", StringComparison.OrdinalIgnoreCase))
        {
            command = new RemoteCommand(RemoteCommandType.RightClick);
            return true;
        }

        var parts = text.Split(':', 2);
        if (parts.Length != 2) return false;

        var verb = parts[0].Trim();
        var args = parts[1].Trim();

        if (verb.Equals("Zoom", StringComparison.OrdinalIgnoreCase))
        {
            if (!int.TryParse(args, NumberStyles.Integer, CultureInfo.InvariantCulture, out var steps)) return false;
            command = new RemoteCommand(RemoteCommandType.Zoom, steps);
            return true;
        }

        if (verb.Equals("Pinch", StringComparison.OrdinalIgnoreCase))
        {
            var p = args.Split(',', 2);
            if (p.Length != 2) return false;
            if (!int.TryParse(p[0].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var direction)) return false;
            if (!int.TryParse(p[1].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var steps)) return false;
            // Normalize direction to +/- 1
            direction = direction >= 0 ? 1 : -1;
            command = new RemoteCommand(RemoteCommandType.Pinch, direction, steps);
            return true;
        }

        if (verb.Equals("Scroll", StringComparison.OrdinalIgnoreCase))
        {
            if (!int.TryParse(args, NumberStyles.Integer, CultureInfo.InvariantCulture, out var delta)) return false;
            command = new RemoteCommand(RemoteCommandType.Scroll, delta);
            return true;
        }

        if (verb.Equals("Move", StringComparison.OrdinalIgnoreCase))
        {
            var xy = args.Split(',', 2);
            if (xy.Length != 2) return false;
            if (!int.TryParse(xy[0].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var dx)) return false;
            if (!int.TryParse(xy[1].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var dy)) return false;
            command = new RemoteCommand(RemoteCommandType.MoveRelative, dx, dy);
            return true;
        }

        if (verb.Equals("Abs", StringComparison.OrdinalIgnoreCase) || verb.Equals("MoveAbs", StringComparison.OrdinalIgnoreCase))
        {
            var p = args.Split(',', 3);
            if (p.Length != 3) return false;
            if (!int.TryParse(p[0].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var screen)) return false;
            if (!int.TryParse(p[1].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var x)) return false;
            if (!int.TryParse(p[2].Trim(), NumberStyles.Integer, CultureInfo.InvariantCulture, out var y)) return false;
            command = new RemoteCommand(RemoteCommandType.MoveAbsolute, screen, x, y);
            return true;
        }

        return false;
    }
}
