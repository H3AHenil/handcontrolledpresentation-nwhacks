namespace RemoteControlProtocol;

public enum RemoteCommandType
{
    MoveRelative,
    MoveAbsolute,
    LeftClick,
    RightClick,
    Scroll,
    Zoom,
    Pinch,
}

/// <summary>
/// A generic command container.
/// Meaning of Arg1/Arg2/Arg3 depends on <see cref="RemoteCommandType"/>:
/// - MoveRelative: Arg1=dx, Arg2=dy
/// - MoveAbsolute: Arg1=screenIndex, Arg2=x, Arg3=y
/// - Scroll: Arg1=wheelDelta
/// - Zoom: Arg1=steps (Ctrl+Wheel fallback)
/// - Pinch: Arg1=direction(+1 out / -1 in), Arg2=steps, Arg3=reserved(0)
/// </summary>
public sealed record RemoteCommand(RemoteCommandType Type, int Arg1 = 0, int Arg2 = 0, int Arg3 = 0)
{
    public override string ToString() => RemoteCommandCodec.Encode(this);
}
