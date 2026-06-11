# AWS Cloud Relay Server Architecture & Implementation Plan

This plan details the transition of the remote control software from a local direct socket network to a cloud-based WebSocket relay server on AWS EC2. This enables remote desktop sharing and control over the internet (LTE/5G/any Wi-Fi) without configuration barriers.

## 구현 완료 요약 (2026-06-11 업데이트)

AWS Relay 서버 구축 및 기기 간 양방향 원격 제어/파일 전송에 대한 모든 최적화 및 편의 개선 사항이 최종 반영 및 배포되었습니다.

### 1. AWS EC2 릴레이 서버 상시 운영
- **서버 IP**: `54.242.81.228` (포트 `8080`)
- EC2 인스턴스에 `aws_relay.py` 배포 완료
- `systemd` 서비스(`telecontrol-relay.service`)로 등록하여 24시간 자동 실행 및 상시 대기 가동 중
- AWS WebSocket 서버 최대 패킷 제한(`max_size`)을 기존 10MB에서 80MB로 확대 적용 완료

### 2. 파일 전송 진행 상태(프로그레스 바) 실시간 동기화
- **진행률 피드백 연동**: 수신측이 청크 데이터를 받아 파일에 저장할 때마다 `FS_FILE_PROGRESS` 피드백 신호를 송출하고, 송신측이 이를 수신해 프로그레스 바를 채우는 방식으로 양쪽 화면의 실시간 진행률을 완벽히 동기화하였습니다.
- **연결 안정화**: 10MB 이상 대용량 파일 전송 시 Ktor 소켓 기본 타임아웃으로 인해 전송이 끊어지는 문제를 해결하기 위해, Android 측 클라이언트 Ktor 설정을 보완하여 read/writeTimeout 제한을 0(무제한)으로 수정했습니다.

### 3. 모바일 기기 간 파일 전송 레이아웃 개선 및 제어 최적화
- **모바일 간 UI 레이아웃 정반대 반전**: 상대방 기기가 Android 폰임을 식별할 수 있는 핸드셰이크 프로토콜(`device=android`)을 양방향 도입했습니다. 휴대폰끼리 전송할 경우 위에 창은 "도움 주기", 아래 창은 "도움 받기"가 되도록 UI 뷰 레이아웃과 데이터 바인딩, 파일 송수신 전송 방향을 완벽히 반전시켰습니다.
- **제어(화면/터치) 속도 극대화**:
  1. **비디오 프레임 백프레셔(Backpressure) 및 스로틀링**: 프레임 전송 간격을 최소 40ms(최대 25 FPS)로 고정하고, 이전 프레임 전송 코루틴이 완료될 때까지 다음 프레임 캡처 처리를 락(Lock)하여 네트워크 병목 시 지연(렉) 누적을 원천 차단했습니다.
  2. **비트맵 재사용(Bitmap Pooling)**: 매 프레임 이미지 캡처 시 비트맵을 새로 생성하지 않고 전역 재활용 버퍼 비트맵에 Canvas draw를 통해 복사함으로써 가비지 컬렉터(GC)에 의한 화면 끊김 오버헤드를 0으로 소멸시켰습니다.
  3. **터치 이벤트 스로틀링**: Client 스크롤 시 쏟아지는 `ACTION_MOVE` 이벤트를 20ms 간격으로 스로틀링 전송하여 소켓 트래픽 정체를 개선했습니다.

### 4. 연결 종료 시 원격 도움 서비스 자동 중지 기능
- 클라이언트(도움 주기) 측에서 연결을 종료하면 호스트 기기(도움 받기)에서도 소켓 통신 및 로그를 통해 이를 자동 인지하여, 백그라운드 MediaProjection 캡처 화면 투사와 오디오 녹음 서비스 및 PC 호스트 서버가 즉각 자동 정지(`stopSelf()`, `stop()`)되도록 편의성을 개선했습니다.

### 5. 기존 마이그레이션 이력 (2026-06-10 이전)
- **PC 프로그램 개선**: `network/server.py` 화면 프레임 송출 시 `b'\x00'` 헤더 누락 버그 해결.
- **Android 모바일 앱 개선**: `RemoteDisplayView.kt`에 핀치-투-줌 기능 추가 및 좌표 매핑 역산 반영.
- **AWS 릴레이 세션 안정화**: 동일 연결 ID(`123456`) 중복 세션 덮어쓰기 논리 구현.

---

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

---

## Appendix: TeleControl 로컬 테스트 가이드

> 이 문서는 클라우드(AWS EC2) 배포 전, **PC를 임시 릴레이 서버로 활용하여 로컬 환경에서 기능을 검증하는 전체 절차**를 설명합니다.

---

### 1. 로컬 테스트의 원리

실제 배포 환경과 로컬 테스트 환경은 **릴레이 서버의 물리적 위치만 다를 뿐 구조가 동일**합니다.

```
[실제 배포]  휴대폰  ⇄  AWS EC2 릴레이 서버  ⇄  PC 프로그램
[로컬 테스트] 휴대폰  ⇄  내 PC (릴레이 서버)  ⇄  PC 프로그램
```

로컬 테스트에서는 **내 PC가 릴레이 서버와 제어 클라이언트 역할을 동시에 수행**합니다.

---

### 2. 사전 준비

#### 2-1. PC 네트워크 정보 확인

PC의 로컬 IP 주소를 확인합니다.

```powershell
ipconfig
```

출력에서 현재 사용 중인 네트워크 어댑터의 **IPv4 주소**를 기록합니다.

- 사설 IP 예시: `192.168.0.x`, `10.0.x.x`
- 공인 IP 예시: `210.113.71.99` (모뎀에 직접 연결된 경우)

> **팁:** 휴대폰 브라우저에서 `http://<PC_IP>:8080` 에 접속하여 `Upgrade Required` 메시지가 뜨면 방화벽이 열려 있는 것입니다.

#### 2-2. Python 가상 환경 확인

```powershell
cd c:\Temp\Antigrvity\telecontrolpc
.venv\Scripts\pip list
```

`websockets`, `PyQt5`, `qasync` 패키지가 설치되어 있어야 합니다.

#### 2-3. Android 앱 빌드

```powershell
cd c:\Temp\Antigrvity\telecom
.\gradlew.bat assembleDebug
```

빌드 성공 후 APK 경로:

```
app\build\outputs\apk\debug\app-debug.apk
```

이 파일을 스마트폰에 설치합니다.

---

### 3. 로컬 테스트 절차

#### 3-1단계: 릴레이 서버 실행 (PC에서)

PowerShell 창을 열고 아래 명령을 실행합니다.

```powershell
cd c:\Temp\Antigrvity\telecontrolpc
.venv\Scripts\python aws_relay.py
```

정상 실행 시 출력:
```
[INFO] Starting AWS Relay Server on 0.0.0.0:8080...
[INFO] server listening on 0.0.0.0:8080
```

> ⚠️ **이 창을 테스트가 끝날 때까지 절대 닫지 마세요.**

---

#### 3-2단계: PC 프로그램 실행 (PC에서)

새로운 PowerShell 창을 열고 실행합니다.

```powershell
cd c:\Temp\Antigrvity\telecontrolpc
.venv\Scripts\python main.py
```

또는 빌드된 실행 파일을 사용합니다.

```
dist\TeleControlPC.exe
```

---

#### 3-3단계: PC 프로그램 설정

1. 실행된 **TeleControl** 프로그램 우측 상단의 **`⚙ 서버 설정`** 버튼을 클릭합니다.
2. 설정 창에서 아래 값을 입력하고 **[저장]**을 클릭합니다.

   | 항목 | 값 |
   |---|---|
   | 릴레이 서버 IP | `127.0.0.1` |
   | 포트 | `8080` |

3. 좌측 패널에서 **`도움 주기`** 버튼을 클릭합니다.
4. **원격 연결 ID** 입력 칸이 나타나면 대기합니다.

---

#### 3-4단계: 스마트폰 앱 설정

1. 스마트폰에 설치한 **TeleControl** 앱을 실행합니다.
2. 메인 화면에서 **`도움 받기`** 버튼을 탭합니다.
3. 화면 하단의 **`⚙ 릴레이 서버 IP: ...`** 버튼을 터치합니다.
4. IP 입력 다이얼로그에서 PC IP 주소를 입력하고 **[저장]**을 누릅니다.

   | 테스트 환경 | 입력할 IP |
   |---|---|
   | 안드로이드 에뮬레이터 | `10.0.2.2` |
   | 실제 스마트폰 (공유기 Wi-Fi 연결) | PC의 사설 IP (예: `192.168.0.x`) |
   | 실제 스마트폰 (PC가 공인 IP 보유) | PC의 공인 IP (예: `210.113.71.99`) |

5. 저장 후 하단 버튼 텍스트가 변경된 IP로 즉시 업데이트되는지 확인합니다.

---

#### 3-5단계: 화면 공유 시작 (스마트폰)

1. **`원격 도움 요청`** 버튼을 탭합니다.
2. 오디오 녹음 권한 요청이 뜨면 **[허용]**을 탭합니다.
3. 안드로이드 화면 공유 권한 대화상자가 표시됩니다.
   - **Android 14 이상**: 기본값이 **`전체 화면`**으로 선택되어 있습니다. 바로 **[지금 시작]**을 탭합니다.
   - **Android 13 이하**: 드롭다운을 **`전체 화면 공유`**로 변경한 뒤 **[지금 시작]**을 탭합니다.
4. 약 0.5초 이내에 화면 상단의 **원격 연결 ID**가 6자리 숫자로 자동 업데이트됩니다.

   ```
   예: 원격 연결 ID → 385 921
   ```

---

#### 3-6단계: PC에서 연결하여 제어

1. 스마트폰에 표시된 **6자리 연결 ID**를 확인합니다.
2. PC 프로그램의 **원격 연결 ID** 입력칸에 기존 내용을 지우고 해당 숫자를 입력합니다.
3. **`연결`** 버튼을 클릭합니다.
4. 연결 성공 시 PC 화면 뷰어에 **스마트폰 화면이 실시간으로 스트리밍**됩니다.
5. PC 마우스로 뷰어 영역을 클릭·드래그하여 스마트폰을 제어합니다.

---

### 4. 연결 확인 방법 (로그)

#### 릴레이 서버 로그 (정상 연결 시)

```
[INFO] connection open
[INFO] New connection request on path: /register
[INFO] Host registered. Session ID: 385921     ← 스마트폰 연결 및 ID 발급
[INFO] Client joined session 385921             ← PC 클라이언트 연결
```

#### PC 프로그램 로그 (정상 수신 시)

```
[DEBUG] WebSocketClient: Received binary message: 28964 bytes   ← JPEG 화면 프레임
[DEBUG] RemoteViewer: Successfully decoded JPEG, cropped: 540x1170 -> 540x1170
```

---

### 5. 문제 해결

#### 연결 ID가 표시되지 않는 경우

| 증상 | 원인 | 해결 방법 |
|---|---|---|
| `------` 유지 | 릴레이 서버 IP 오류 | 스마트폰 앱 하단에서 IP 재설정 후 `원격 도움 중단` → `원격 도움 요청` 재시작 |
| `연결 실패` 표시 | PC 방화벽이 8080 포트 차단 | Windows 방화벽 인바운드 규칙에 TCP 8080 포트 추가 허용 |
| 릴레이 서버 오류 | 서버가 실행되지 않음 | `aws_relay.py` 재실행 |

#### 방화벽 포트 개방 명령 (관리자 PowerShell)

```powershell
netsh advfirewall firewall add rule name="TeleControl Relay 8080" dir=in action=allow protocol=TCP localport=8080
```

#### 연결 후 화면이 표시되지 않는 경우

- 스마트폰 앱에서 **화면 공유 권한**이 `전체 화면`으로 설정되었는지 확인합니다.
- 접근성 서비스 활성화 여부와 무관하게 화면 공유 자체는 동작합니다.

---

### 6. AWS EC2 실제 배포로 전환 시

로컬 테스트 완료 후 실제 서버 배포 시 변경할 항목은 **IP 주소 하나뿐**입니다.

1. AWS EC2 인스턴스에서 `aws_relay.py` 실행 후 공인 IP 확인
2. PC 프로그램 **`⚙ 서버 설정`**: `127.0.0.1` → **EC2 공인 IP**로 변경
3. 스마트폰 앱 **`⚙ 릴레이 서버 IP`**: 로컬 IP → **EC2 공인 IP**로 변경
4. EC2 보안 그룹에서 **TCP 8080 인바운드** 허용 확인

---

*최종 업데이트: 2026-06-09*
*작성자: Antigravity AI (로컬 테스트 실제 수행 기반)*
