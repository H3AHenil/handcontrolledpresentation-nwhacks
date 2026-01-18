using System;
using RemoteControlProtocol;

namespace TestOnRemoteControl;

public static class RemoteCommandExecutor
{
    public static void Execute(RemoteCommand cmd)
    {
        switch (cmd.Type)
        {
            case RemoteCommandType.MoveRelative:
                MouseController.MoveRelative(cmd.Arg1, cmd.Arg2);
                break;
            case RemoteCommandType.MoveAbsolute:
                MouseController.MoveAbsoluteOnScreen(cmd.Arg1, cmd.Arg2, cmd.Arg3);
                break;
            case RemoteCommandType.LeftClick:
                MouseController.LeftClick();
                break;
            case RemoteCommandType.RightClick:
                MouseController.RightClick();
                break;
            case RemoteCommandType.Scroll:
                MouseController.Scroll(cmd.Arg1);
                break;
            case RemoteCommandType.Zoom:
                MouseController.Zoom(cmd.Arg1);
                break;
            case RemoteCommandType.Pinch:
                {
                    var dir = cmd.Arg1 >= 0 ? 1 : -1;
                    var steps = Math.Max(1, cmd.Arg2);

                    // Preferred: touch injection (feels closer to a trackpad two-finger pinch)
                    if (!MouseController.PinchZoomGesture(dir, steps))
                    {
                        // Fallback: Ctrl+Wheel
                        MouseController.Zoom(dir * steps);
                    }

                    break;
                }
            default:
                throw new ArgumentOutOfRangeException(nameof(cmd.Type), cmd.Type, null);
        }
    }
}
