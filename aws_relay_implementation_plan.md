# AWS Cloud Relay Server Architecture & Implementation Plan

This plan details the transition of the remote control software from a local direct socket network to a cloud-based WebSocket relay server on AWS EC2. This enables remote desktop sharing and control over the internet (LTE/5G/any Wi-Fi) without configuration barriers.

## User Review Required

> [!IMPORTANT]
> **Android Codebase Modification Approval**: This plan requires modifying both the PC (`telecontrolpc`) and Android (`telecom`) repositories. To support remote control over the internet, we must redirect the Android app's networking layer from a local server to a WebSocket client connecting to AWS.

## Open Questions

> [!WARNING]
> **AWS Server Setup**:
> 1. We will provide the server script (`aws_relay.py`) and instructions.
> 2. The user will need to launch an Ubuntu EC2 instance on their AWS Free Tier, open port `8080` (or `80`) in the Security Group, and run the script.
> 3. Once the EC2 public IP is available, it must be configured in both the PC and Android client codes.

---

## Architecture Design

Instead of a direct P2P connection, we introduce an **AWS Relay Server** using persistent WebSockets:

```
[Host (Sharing Screen)]   ───► [ AWS Relay Server ] ◄───   [Client (Viewer/Controller)]
(Gets 6-digit ID)             (Matches matching IDs)        (Enters 6-digit ID)
```

1. **Host**: Connects to `ws://<AWS_IP>:8080/register`, receives a random unique 6-digit ID (e.g. `482 910`), and displays it.
2. **Client**: Connects to `ws://<AWS_IP>:8080/join/<ID>`, inputs the ID.
3. **Relay**: Couples the two WebSockets. Relays video/audio frames (binary) from Host to Client, and touch/keyboard commands (text) from Client to Host.

---

## Proposed Changes

### 1. New Component: AWS Relay Server

#### [NEW] [aws_relay.py](file:///c:/Temp/Antigrvity/telecontrolpc/aws_relay.py)
A lightweight Python script utilizing `websockets` or `FastAPI` to run on AWS EC2:
- Manage a session registry.
- Handle host registration, generate unique 6-digit IDs, and handle client matching.
- Relay binary and text frames bi-directionally between paired sockets.
- Handle disconnection gracefully (clean up registry, notify the other peer).

---

### 2. Component: PC Client (`telecontrolpc`)

#### [MODIFY] [client.py](file:///c:/Temp/Antigrvity/telecontrolpc/network/client.py)
- Replace direct `websockets.connect` with cloud relay registration and joining.
- Implement `register_host()` (receives ID from AWS) and `join_host(id)` (connects to target host).
- Relay mouse and keyboard inputs to the AWS server.

#### [MODIFY] [main_window.py](file:///c:/Temp/Antigrvity/telecontrolpc/gui/main_window.py)
- **UI Update**:
  - In "도움 받기" (Host) mode: display the 6-digit ID received from AWS instead of the local IP address.
  - In "도움 주기" (Client) mode: change the IP and Port input boxes to a single 6-digit connection ID entry box.
- Update connection triggers to call `register_host` or `join_host` accordingly.

---

### 3. Component: Android App (`telecom`)

#### [MODIFY] [RemoteControlService.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/RemoteControlService.kt)
- Remove the embedded Ktor CIO server.
- Add Ktor WebSocket client connection to AWS relay.
- Receive generated 6-digit ID from AWS and stream video frames to the AWS server.

#### [MODIFY] [HostActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/HostActivity.kt)
- Bind to the service, receive the 6-digit ID from the background service, and render it on the screen.

#### [MODIFY] [ClientActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/ClientActivity.kt)
- Change client connection logic to connect to the AWS server and send the target 6-digit ID to join the host.

---

## Verification Plan

### Automated/Local Tests
- Run `aws_relay.py` on localhost (`127.0.0.1:8080`).
- Start two PC Client instances locally:
  - Instance A (Host): registers to local relay, gets a 6-digit ID.
  - Instance B (Client): enters the ID and connects.
- Verify screen stream transmission and input relaying.

### Manual/AWS Verification
1. Deploy `aws_relay.py` to AWS EC2.
2. Build Android APK and PC EXE with the AWS server IP configured.
3. Test remote control between PC and phone over different networks (PC on Ethernet, Phone on cellular LTE/5G).
