# AWS Cloud Relay Server Migration & Implementation Plan

이 계획서는 기존 로컬 Wi-Fi(동일 네트워크) 환경에서만 작동하던 원격 제어 프로그램을 AWS EC2에 호스팅된 WebSocket Relay 서버를 통과하도록 구조를 개선하고, 6자리 고유 연결 ID를 통해 전 세계 어디서나 인터넷만 연결되어 있으면 원격 제어 및 화면 공유가 가능하도록 개선하는 개발 계획서입니다.

## User Review Required

> [!IMPORTANT]
> **Android 및 PC 코드베이스 동시 수정**:
> 이 구현은 PC companion 프로그램(`telecontrolpc`)과 Android 앱(`telecom`) 양쪽 모두의 네트워크 레이어 및 UI 레이아웃 변경을 포함합니다.
> Android 앱의 `RemoteControlService` 내장 Ktor CIO 서버를 제거하고 AWS 릴레이 서버에 연결하는 웹소켓 클라이언트로 전환합니다.

> [!WARNING]
> **AWS 서버 호스팅 환경 설정**:
> 1. 본 릴레이 서버(`aws_relay.py`)는 기본적으로 Python `websockets` 모듈을 사용합니다.
> 2. 사용자는 AWS EC2(Ubuntu 등 프리티어 인스턴스 권장)를 생성하고 보안 그룹(Security Group)에서 포트 `8080` (혹은 포트 `80`) 인바운드 규칙을 추가해야 합니다.
> 3. 개발/테스트 중에는 로컬 호스트(`127.0.0.1:8080`)로 먼저 검증하고, 최종 릴레이 서버 IP가 확보되면 클라이언트 코드 상에 해당 공인 IP/도메인을 설정합니다.

---

## 1. 아키텍처 및 연결 흐름 (Architecture & Connection Flow)

기존 P2P(직접 IP 입력) 방식 대신, 릴레이 서버를 중계역으로 삼아 상호 연결합니다.

```
[Host (원격 도움 받기)]        ───► [ AWS Relay Server ] ◄───   [Client (원격 도움 주기)]
- 화면/오디오 송신                    (세션 ID 매칭 중계)               - 원격 제어 입력 송신
- ws://<IP>:8080/register            (예: 482 910 매칭)                - ws://<IP>:8080/join/482910
- 6자리 고유 ID 발급 표시                                             - 연결 ID 입력 후 접속
```

### 1) 프로토콜 규격 (Connection Protocol)
1. **호스트(Host)**: `/register` 경로로 WebSocket 연결을 시작합니다.
   - **서버 -> 호스트**: 연결 즉시 `ID=<6자리숫자>` 형태의 텍스트 메시지를 보냅니다. (예: `ID=389201`)
   - **호스트 UI**: 수신한 6자리 ID를 가독성 좋게 공백을 넣어 `389 201`로 화면에 표시합니다.
2. **클라이언트(Client)**: 사용자가 입력한 6자리 ID를 활용해 `/join/<ID>` 경로로 연결을 시도합니다.
   - **서버 -> 클라이언트**: 연결 허용 시 `CONNECTED` 메시지를 발송합니다.
   - **서버 -> 호스트**: 클라이언트 접속 시 `CLIENT_CONNECTED` 메시지를 발송합니다.
   - **호스트**: `CLIENT_CONNECTED` 메시지를 받으면 화면 캡처 및 바이너리 데이터 전송 루프를 활성화합니다.
3. **데이터 중계**:
   - **Host -> Client**: 화면 및 오디오 데이터 (바이너리). 첫 번째 바이트가 `0`이면 비디오 프레임(JPEG), `1`이면 오디오(PCM)입니다.
   - **Client -> Host**: 마우스, 키보드, 터치 제어 명령 (텍스트). `action=...,x=...,y=...` 형태의 CSV 데이터입니다.
4. **연결 해제**:
   - 호스트 종료 시: 서버는 클라이언트에게 `HOST_DISCONNECTED`를 전달하고 커넥션을 닫습니다.
   - 클라이언트 종료 시: 서버는 호스트에게 `CLIENT_DISCONNECTED`를 전달하여 호스트의 캡처 루프를 일시정지시킵니다.

---

## 2. PC 프로그램 수정 사항 (`telecontrolpc`)

### 1) Network Layer

#### [MODIFY] [server.py](file:///c:/Temp/Antigrvity/telecontrolpc/network/server.py)
* **목적**: 기존 로컬 웹소켓 서버를 중단하고, AWS Relay 서버에 연결하는 Host Client 역할을 수행하도록 전면 개편합니다.
* **상세 변경**:
  - `RemoteControlServer` 클래스 및 핵심 메서드(`start()`, `stop()`, `update_settings()`) 시그니처를 유지하여 `main_window.py`와의 호환성을 유지합니다.
  - `start()` 호출 시 `websockets.connect("ws://<AWS_IP>:8080/register")`로 연결합니다.
  - 수신 루프에서 `ID=xxxxxx`가 수신되면, 등록 완료 콜백(GUI)을 통해 UI에 발급받은 6자리 ID를 알립니다.
  - `CLIENT_CONNECTED` 수신 시 화면 스트리밍 플래그(`self.client_connected = True`)를 활성화하고 화면 전송 태스크를 재개합니다.
  - `CLIENT_DISCONNECTED` 수신 시 스트리밍 플래그를 비활성화합니다.
  - 클라이언트가 보내오는 조작 문자열(`action=...`)을 파싱하여 기존과 동일하게 `InputInjector`를 이용해 가상 입력을 주입합니다.

#### [MODIFY] [client.py](file:///c:/Temp/Antigrvity/telecontrolpc/network/client.py)
* **목적**: 특정 IP로의 직접 웹소켓 연결에서 AWS Relay를 통한 조인 연결로 변경합니다.
* **상세 변경**:
  - `connect(host, port)` 메서드 내부의 연결 타겟 URI를 `ws://{host}:{port}/join/{session_id}` 형태로 빌드합니다.
  - 접속 직후 서버로부터 `CONNECTED` 또는 오류 메시지(`ERROR: ...`) 수신 처리 로직을 구현합니다.

### 2) UI Layer

#### [MODIFY] [main_window.py](file:///c:/Temp/Antigrvity/telecontrolpc/gui/main_window.py)
* **목적**: IP/포트 대신 6자리 연결 ID를 표시 및 입력하는 사용자 친화적 UI로 변경합니다.
* **상세 변경**:
  - **도움 받기(Host) 패널**: 
    - "내 IP 주소" 라벨을 "연결 ID"로 변경합니다.
    - 초기 상태는 `------`로 표시하다가, AWS 릴레이 서버 등록 완료 시 전달받은 6자리 번호를 `123 456` 포맷으로 업데이트합니다.
  - **도움 주기(Client) 패널**:
    - "원격 주소(IP)" 및 "원격 포트" 입력박스(`edt_client_ip`, `spn_client_port`)를 제거하거나 숨깁니다.
    - 대신 하나의 `edt_connection_id` (6자리 번호 입력 필드)를 배치합니다.
    - 연결 버튼(`btn_connect`)을 클릭하면 입력된 문자열에서 공백을 제거하고 `client.connect(RELAY_HOST, RELAY_PORT, connection_id)`를 호출하도록 수정합니다.

---

## 3. Android 앱 수정 사항 (`telecom`)

### 1) Network Service

#### [MODIFY] [RemoteControlService.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/RemoteControlService.kt)
* **목적**: 로컬 Ktor CIO 웹소켓 서버를 완전히 제거하고, AWS 릴레이 서버에 접속하는 Ktor 웹소켓 클라이언트로 전환합니다.
* **상세 변경**:
  - `embeddedServer(CIO, ...)` 구문을 완전히 제거합니다.
  - Ktor `HttpClient(OkHttp)` 혹은 기존 HttpClient 인스턴스를 활용하여 `ws://<AWS_IP>:8080/register`에 연결하는 비동기 코루틴 루프를 구동합니다.
  - 서버로부터 `ID=xxxxxx`가 도착하면 `LocalBroadcastManager` 또는 시스템 인텐트 브로드캐스트를 발송하여 `HostActivity`가 ID를 갱신해 화면에 그릴 수 있게 합니다.
  - `CLIENT_CONNECTED`를 수신하면 `activeSessions`에 가상의 세션을 할당하거나 스트리밍 활성화 플래그를 켜서 `ImageReader`에서 생성되는 JPEG 화면 캡처 및 마이크 오디오 패킷(바이너리)을 AWS로 송신하기 시작합니다.
  - 클라이언트에서 릴레이되어 들어오는 텍스트 명령(`action=...,x=...,y=...`, `NAV_BACK` 등)을 파싱하여 기존과 같이 `RemoteAccessibilityService`를 통해 터치 및 제스처 동작을 안드로이드 화면에 주입합니다.

### 2) UI & Activities

#### [MODIFY] [HostActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/HostActivity.kt)
* **목적**: 내 IP 주소 출력 대신, 서비스에서 릴레이 서버로부터 얻어온 6자리 연결 ID를 화면에 렌더링하도록 변경합니다.
* **상세 변경**:
  - `RemoteControlService`로부터 `SESSION_ID_RECEIVED` 인텐트를 받기 위한 `BroadcastReceiver`를 구현하고 `onResume` / `onPause`에서 등록 및 해제합니다.
  - 방송 수신 시 6자리 숫자를 가공해 `txtIpAddress` 필드(레이블은 '연결 ID'로 변경)에 표시합니다.

#### [MODIFY] [ClientActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/ClientActivity.kt)
* **목적**: Android 앱에서 PC 등을 제어할 때 직접 IP 연결 대신 AWS Relay 서버를 거치도록 수정합니다.
* **상세 변경**:
  - `client.ws` 호출 시 `ws://<AWS_IP>:8080/join/<ID>` 경로로 연결하도록 타겟 경로를 수정합니다.
  - 연결 수립 시 UI에 연결 상태를 업데이트하고 화면 스트림 및 마우스/키 터치 이벤트의 송수신을 진행합니다.

#### [MODIFY] [MainActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/MainActivity.kt) 및 [activity_main.xml](file:///c:/Temp/Antigrvity/telecom/app/src/main/res/layout/activity_main.xml)
* **목적**: IP 주소 입력창을 6자리 연결 ID 입력창으로 수정합니다.
* **상세 변경**:
  - `edtIpAddress`의 힌트 문구를 "6자리 연결 ID 입력 (예: 123456)"으로 변경합니다.
  - 입력값 검증 로직을 IP 포맷 검증에서 6자리 숫자 여부 검증으로 수정합니다.

---

## 4. 검증 계획 (Verification Plan)

### 1) 로컬 시뮬레이션 및 통합 테스트 (Local Simulation)
* **준비**: 로컬 개발 환경에서 `python aws_relay.py`를 실행하여 `127.0.0.1:8080` 포트로 릴레이 서버를 구동합니다.
* **PC 테스트**: 
  - PC Companion A를 Host 모드로 실행 -> `ID=123456` 획득 확인.
  - PC Companion B를 Client 모드로 실행하여 `123456` 입력 -> 상호 페어링, 화면 공유 및 키보드/마우스 제어 동작 검증.
* **모바일 테스트**:
  - Android 기기에서 도움 받기(Host) 실행 -> 로컬 서버 IP(개발 환경 PC IP)의 릴레이 서버로 접속하여 6자리 ID 획득 및 화면 출력 확인.
  - PC Companion에서 해당 ID를 입력하고 연결하여 스마트폰 원격 제어가 실시간으로 이뤄지는지 검증.

### 2) AWS EC2 배포 및 최종 필드 테스트 (Cloud Deployment)
1. AWS EC2 인스턴스에 `aws_relay.py` 업로드 및 백그라운드 프로세스로 실행.
2. PC Companion 빌드 및 Android APK 패키징 시 AWS 공인 IP 주소를 기본 주소로 하드코딩 혹은 설정 파일 연동.
3. PC는 사무실 유선 인터넷, 안드로이드 스마트폰은 LTE/5G 무선 데이터 네트워크로 이종 네트워크망 환경을 구성합니다.
4. 6자리 번호를 통한 글로벌 매칭 접속이 이루어지는지 확인하고, 프레임 레이트(FPS), 레이턴시(딜레이) 수준을 정성 평가합니다.
