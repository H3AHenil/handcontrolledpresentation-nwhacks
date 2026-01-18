using System;
using System.Runtime.InteropServices;

namespace TestOnRemoteControl;

internal static class TouchInjection
{
    // Windows 8+ API

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool InitializeTouchInjection(uint maxCount, uint dwMode);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern bool InjectTouchInput(uint count, [In] POINTER_TOUCH_INFO[] contacts);

    private const uint TOUCH_FEEDBACK_DEFAULT = 0x1;

    private const uint POINTER_INPUT_TYPE_TOUCH = 0x00000002;

    private const uint POINTER_FLAG_NONE = 0x00000000;
    private const uint POINTER_FLAG_NEW = 0x00000001;
    private const uint POINTER_FLAG_INRANGE = 0x00000002;
    private const uint POINTER_FLAG_INCONTACT = 0x00000004;
    private const uint POINTER_FLAG_DOWN = 0x00010000;
    private const uint POINTER_FLAG_UPDATE = 0x00020000;
    private const uint POINTER_FLAG_UP = 0x00040000;

    private const uint TOUCH_FLAG_NONE = 0x00000000;

    private const uint TOUCH_MASK_NONE = 0x00000000;
    private const uint TOUCH_MASK_CONTACTAREA = 0x00000001;
    private const uint TOUCH_MASK_ORIENTATION = 0x00000002;
    private const uint TOUCH_MASK_PRESSURE = 0x00000004;

    [StructLayout(LayoutKind.Sequential)]
    private struct RECT
    {
        public int left;
        public int top;
        public int right;
        public int bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINT
    {
        public int X;
        public int Y;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINTER_INFO
    {
        public uint pointerType;
        public uint pointerId;
        public uint frameId;
        public uint pointerFlags;
        public IntPtr sourceDevice;
        public IntPtr hwndTarget;
        public POINT ptPixelLocation;
        public POINT ptHimetricLocation;
        public POINT ptPixelLocationRaw;
        public POINT ptHimetricLocationRaw;
        public uint dwTime;
        public uint historyCount;
        public int inputData;
        public uint dwKeyStates;
        public ulong PerformanceCount;
        public uint ButtonChangeType;
    }

    [StructLayout(LayoutKind.Sequential)]
    private struct POINTER_TOUCH_INFO
    {
        public POINTER_INFO pointerInfo;
        public uint touchFlags;
        public uint touchMask;
        public RECT rcContact;
        public RECT rcContactRaw;
        public uint orientation;
        public uint pressure;
    }

    private static bool _initialized;

    public static bool EnsureInitialized()
    {
        if (_initialized) return true;
        _initialized = InitializeTouchInjection(2, TOUCH_FEEDBACK_DEFAULT);
        return _initialized;
    }

    public static bool InjectPinchAtScreenPoint(int centerX, int centerY, int direction, int steps)
    {
        if (!EnsureInitialized())
            return false;

        if (steps <= 0) return true;
        direction = direction >= 0 ? 1 : -1;

        // Two fingers move symmetrically around the center point (spread / pinch)
        const int startHalfDistance = 40;
        const int deltaPerStep = 12;
        var start1 = (x: centerX - startHalfDistance, y: centerY);
        var start2 = (x: centerX + startHalfDistance, y: centerY);

        // Per-step movement direction: out => increase distance; in => decrease distance
        var totalDelta = direction * deltaPerStep * steps;
        var end1 = (x: start1.x - totalDelta, y: start1.y);
        var end2 = (x: start2.x + totalDelta, y: start2.y);

        // Use a small rectangle as the contact area
        static RECT ContactRect(int x, int y)
        {
            const int r = 4;
            return new RECT { left = x - r, top = y - r, right = x + r, bottom = y + r };
        }

        var c1 = new POINTER_TOUCH_INFO
        {
            pointerInfo = new POINTER_INFO
            {
                pointerType = POINTER_INPUT_TYPE_TOUCH,
                pointerId = 1,
                ptPixelLocation = new POINT { X = start1.x, Y = start1.y },
                pointerFlags = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_NEW
            },
            touchFlags = TOUCH_FLAG_NONE,
            touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE,
            rcContact = ContactRect(start1.x, start1.y),
            orientation = 90,
            pressure = 32000
        };

        var c2 = new POINTER_TOUCH_INFO
        {
            pointerInfo = new POINTER_INFO
            {
                pointerType = POINTER_INPUT_TYPE_TOUCH,
                pointerId = 2,
                ptPixelLocation = new POINT { X = start2.x, Y = start2.y },
                pointerFlags = POINTER_FLAG_DOWN | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT | POINTER_FLAG_NEW
            },
            touchFlags = TOUCH_FLAG_NONE,
            touchMask = TOUCH_MASK_CONTACTAREA | TOUCH_MASK_ORIENTATION | TOUCH_MASK_PRESSURE,
            rcContact = ContactRect(start2.x, start2.y),
            orientation = 90,
            pressure = 32000
        };

        if (!InjectTouchInput(2, [c1, c2]))
            return false;

        // Use a few UPDATE frames to interpolate and simulate a continuous pinch
        const int frames = 6;
        for (var i = 1; i <= frames; i++)
        {
            var t = i / (double)frames;
            var ix1 = (int)(start1.x + (end1.x - start1.x) * t);
            var iy1 = (int)(start1.y + (end1.y - start1.y) * t);
            var ix2 = (int)(start2.x + (end2.x - start2.x) * t);
            var iy2 = (int)(start2.y + (end2.y - start2.y) * t);

            c1.pointerInfo.pointerFlags = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT;
            c1.pointerInfo.ptPixelLocation = new POINT { X = ix1, Y = iy1 };
            c1.rcContact = ContactRect(ix1, iy1);

            c2.pointerInfo.pointerFlags = POINTER_FLAG_UPDATE | POINTER_FLAG_INRANGE | POINTER_FLAG_INCONTACT;
            c2.pointerInfo.ptPixelLocation = new POINT { X = ix2, Y = iy2 };
            c2.rcContact = ContactRect(ix2, iy2);

            if (!InjectTouchInput(2, [c1, c2]))
                return false;
        }

        // Lift up
        c1.pointerInfo.pointerFlags = POINTER_FLAG_UP;
        c2.pointerInfo.pointerFlags = POINTER_FLAG_UP;
        return InjectTouchInput(2, [c1, c2]);
    }
}
