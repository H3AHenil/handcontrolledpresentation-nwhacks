# UDP Remote Control API

This repository separates the **controller** and the **controlled** side:

- **Controller**: `BasicUDPBroadcastTest` (interactive command-line terminal, sends UDP broadcast)
- **Controlled**: `TestOnRemoteControl` (WPF app, listens on UDP, executes mouse/gesture injection)
- **Shared protocol**: `RemoteControlProtocol` (`RemoteCommand` + `RemoteCommandCodec`)

> Goal: the controller only sends commands; the controlled side only executes commands.

---

## 1. Networking

- Transport: UDP
- Mode: **Broadcast** (default destination: `255.255.255.255`)
- Port: `8080` (default)
- Encoding: UTF-8
- Message format: **one command per datagram** (plain text)

The controlled side listens on this port (see `TestOnRemoteControl/UdpRemoteCommandListener.cs`).

---

## 2. Wire Protocol (Command Formats)

### 2.1 Click
- `LeftClick`
- `RightClick`

### 2.2 Relative Move
- `Move:<dx>,<dy>`

Example:
- `Move:10,-5`

### 2.3 Absolute Move (by screen index)
- `Abs:<screen>,<x>,<y>`

Semantics:
- `screen`: display index (0, 1, 2...; order comes from Windows monitor enumeration)
- `x,y`: **pixel coordinates within that screen** (top-left is 0,0)

Example:
- `Abs:0,960,540`

### 2.4 Mouse Wheel
- `Scroll:<delta>`

Examples:
- `Scroll:120`
- `Scroll:-120`

### 2.5 Zoom (fallback: Ctrl + Wheel)
- `Zoom:<steps>`

Semantics:
- steps > 0 zoom in; steps < 0 zoom out

Examples:
- `Zoom:1`
- `Zoom:-2`

### 2.6 Pinch (preferred: touch injection / two-finger pinch)
- `Pinch:<direction>,<steps>`

Semantics:
- `direction`: `1` means zoom in (pinch out), `-1` means zoom out (pinch in)
- `steps`: intensity/steps (larger value means larger pinch distance)

Execution strategy (controlled side):
1. Prefer Windows touch injection (`InitializeTouchInjection` / `InjectTouchInput`) to perform a two-finger pinch around the **current mouse cursor location**
2. If touch injection fails (system/app doesn’t support it), automatically fall back to `Ctrl+Wheel` (`Zoom`)

Examples:
- `Pinch:1,2`
- `Pinch:-1,3`

---

## 3. Controlled Side: Command-to-Action Mapping

Single entry point: `TestOnRemoteControl/RemoteCommandExecutor.cs`

| Command | Action |
|---|---|
| MoveRelative | `MouseController.MoveRelative(dx,dy)` |
| MoveAbsolute | `MouseController.MoveAbsoluteOnScreen(screen,x,y)` |
| LeftClick | `MouseController.LeftClick()` |
| RightClick | `MouseController.RightClick()` |
| Scroll | `MouseController.Scroll(delta)` |
| Zoom | `MouseController.Zoom(steps)` (Ctrl+Wheel) |
| Pinch | `MouseController.PinchZoomGesture(dir,steps)`; fallback to `Zoom(dir*steps)` |

---

## 4. Controller (Interactive CLI Terminal)

Project: `BasicUDPBroadcastTest`

### 4.1 Start

- Default port is 8080
- You can specify a port when starting: `BasicUDPBroadcastTest 8081`

### 4.2 Built-in commands (friendly commands)

- `move <dx> <dy>`
- `abs <screen> <x> <y>`
- `leftclick` / `lc`
- `rightclick` / `rc`
- `scroll <delta>`
- `zoomin` / `zoomout`
- `zoom <steps>`
- `pinch <in|out> <steps>`
- `port <port>` (change port at runtime)
- `help`
- `exit`

### 4.3 Examples

- Move cursor to the center of screen 0:
  - `abs 0 960 540`

- Pinch-style zoom in:
  - `pinch out 2`

- Pinch-style zoom out:
  - `pinch in 2`

- Send raw protocol lines directly:
  - `Abs:0,960,540`
  - `Pinch:1,3`

---

## 5. Notes / Caveats

1. **Screen index order** comes from Windows monitor enumeration and may not match the order shown in Windows Display Settings.
2. UDP broadcast may be blocked by firewall rules; allow inbound UDP 8080 for the controlled app.
3. Not every application responds to touch pinch; a fallback to Ctrl+Wheel is implemented.
