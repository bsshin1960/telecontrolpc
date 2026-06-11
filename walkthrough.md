# AWS Cloud Relay 마이그레이션 — 최종 구현 결과 보고서 (Walkthrough)

본 문서에서는 **telecontrolpc (PC 파이썬 앱)**과 **telecom (Android 앱)** 두 프로젝트를 AWS Cloud Relay 구조로 마이그레이션하며 수행된 최종 작업 결과와 검증 내역을 정리합니다.

---

## 🛠️ 작업 수행 결과 요약

### 1. Android 앱 (`telecom`)
- **[MainActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/MainActivity.kt)**
  - 연결 ID 검증 추가 (6자리 숫자 여부 검사).
  - Client 모드로 참여하려는 유저 역시 릴레이 서버 IP를 손쉽게 수정 및 저장할 수 있도록 **⚙ 릴레이 서버 IP 설정 버튼**을 화면 하단에 동적으로 렌더링하고, 설정 팝업 다이얼로그를 추가했습니다.
- **[ClientActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/ClientActivity.kt)**
  - `RemoteControlService.RELAY_HOST` 상수 제거에 맞추어 `SharedPreferences`를 통해 설정된 동적 IP 주소를 로드하여 접속하도록 연동했습니다.
  - `io.ktor.websocket.readText` 확장 함수 참조 누락 오류를 해결하기 위한 임포트 구문을 보완했습니다.
- **[HostActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/HostActivity.kt)**
  - `dpToPx` 메소드의 중복 컴파일 오류(Conflicting overloads)를 수정하고 정상적으로 마진/패딩 레이아웃에 적용했습니다.
  - 릴레이 서버 IP를 다이얼로그 팝업 형태로 입력하여 저장할 수 있는 동적 톱니바퀴 버튼을 추가했습니다.
- **[RemoteControlService.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/RemoteControlService.kt)**
  - AWS EC2 릴레이 서버 연결 차단 시 최대 3회(5초 대기 간격)의 자동 재연결 시도 로직을 보완했습니다.
- **[activity_host.xml](file:///c:/Temp/Antigrvity/telecom/app/src/main/res/layout/activity_host.xml)**
  - Host의 세션 ID 로드 전 초기 IP 텍스트를 `192.168.0.x`에서 `------`로 수정하여 직관성을 개선했습니다.
- **빌드 검증**
  - 시스템 JDK 8과의 호환을 보장하기 위해 `gradle.properties`에 G 드라이브 내에 보관된 JDK 17 경로(`org.gradle.java.home`)를 지정했습니다.
  - Android Gradle Plugin(AGP) 8.2.2 및 Kotlin 1.9.22로 원복하고 정상 빌드하여 디버그 APK(`app/build/outputs/apk/debug/app-debug.apk`) 생성을 마쳤습니다.

---

### 2. PC 앱 (`telecontrolpc`)
- **[config.py](file:///c:/Temp/Antigrvity/telecontrolpc/config.py)**
  - 사용자 홈 디렉토리 내 `.telecontrol_config.json`에 릴레이 IP와 포트를 로컬 저장 및 관리할 수 있는 파일 기반 설정 모듈을 신규 개발했습니다.
- **[gui/main_window.py](file:///c:/Temp/Antigrvity/telecontrolpc/gui/main_window.py)**
  - 최상단 헤더에 **⚙ 서버 설정** 버튼을 신규 도입하고, 릴레이 IP와 포트를 입력하여 저장하는 `QDialog` 설정 팝업을 연동했습니다.
  - 서버 실행 시 `config.py`로부터 매번 최신 IP 주소 값을 로드해 릴레이 서버(`/register`)에 접속하도록 구현을 수정했습니다.
- **빌드 및 실행 테스트**
  - `.venv` 가상환경 내의 python으로 `main.py` 실행 시 GUI 이벤트 루프와 Proactor가 오류 없이 온전히 기동되는 것을 검증했습니다.
  - PyInstaller를 이용해 단일 파일 실행 프로그램 `TeleControlPC.exe`를 성공적으로 재생성하여 `c:\Temp\Antigrvity\telecontrolpc\dist\TeleControlPC.exe`에 배치 완료하였습니다.

---

### 3. AWS Relay Server ID 고정 및 연결 안정화 (2026-06-10 추가)
- **[aws_relay.py](file:///c:/Temp/Antigrvity/telecontrolpc/aws_relay.py)**
  - 호스트 등록 시 항상 고정 연결 ID인 `"123456"`을 발급하도록 변경했습니다.
  - 중복 접속(동일 ID 충돌) 발생 시, 기존 Host 및 Client의 연결을 강제로 안전하게 닫고 새로 유입된 Host의 세션을 등록할 수 있도록 예외처리 로직을 추가했습니다.
  - 로컬 WebSocket 테스트 클라이언트를 구동하여 Host A 연결 -> Host B 접속(Host A 자동 세션 정리) -> Client 페어링 전 과정을 완벽히 검증했습니다.

### 4. 파일 전송 용량 제한 상향 (10MB -> 50MB) 및 10MB 이상 단순 토스트 알림 추가
- **Android 앱 (`telecom`)**
  - `FileTransferActivity.kt`에서 파일 크기 유효성 검사 기준을 기존 10MB에서 50MB로 상향 조정했습니다.
  - 파일 전송 시 용량이 **10MB 이상**일 경우, 별도 윈도우 창 대신 안드로이드 시스템의 **단순 토스트 메시지 (`Toast.makeText` - "비용 발생 주의!")**를 화면 하단에 띄우도록 변경했습니다. 이는 3초 후 자동으로 완벽하게 소멸합니다.
  - 대용량 파일 전송 중 OkHttp 소켓의 기본 타임아웃(10초)으로 인해 10MB 초과 전송 시 전송이 차단 및 종료되던 문제를 해결하기 위해, `ClientActivity.kt`와 `RemoteControlService.kt`의 Ktor OkHttp 클라이언트 설정에서 `readTimeout` 및 `writeTimeout` 제한을 **`0` (무제한)**으로 전격 수정했습니다.
- **PC 앱 (`telecontrolpc`)**
  - `file_transfer.py`에서 파일 송신 제한을 50MB로 조정했습니다.
  - 파일 송신 시 용량이 **10MB 이상**일 경우, OS 팝업 창을 아예 생성하지 않고 **기존 창 내부 정 중앙에 일시적으로 붉은색 바탕에 흰색 글씨의 토스트 알림창(ToastNotification - "비용 발생 주의!")**을 띄워 보여준 뒤, 3초 후 자동으로 닫히도록(close) 비차단(non-blocking) 구조로 변경했습니다.
  - `client.py` 및 `server.py`의 WebSocket 프레임 전송 제한(`max_size`)을 기존 10MB에서 80MB (`80 * 1024 * 1024` 바이트)로 상향하였습니다.
- **릴레이 서버 (`aws_relay.py`)**
  - AWS WebSocket 서버 실행 시 수신 가능한 최대 패킷 크기(`max_size`)를 동일하게 80MB로 확대하여 대용량 파일 전송 중 세션이 끊기지 않도록 조치했습니다.
- **최종 빌드 완료**
  - Android 앱 및 PC 용 단일 실행 파일 `TeleControlPC.exe`를 성공적으로 다시 빌드 및 패키징 완료했습니다.


### 5. 파일 전송 진행 상태(프로그레스 바) 실시간 동기화 구현
- **Android 앱 (`telecom`)**
  - [FileTransferActivity.kt](file:///c:/Temp/Antigrvity/telecom/app/src/main/java/com/sbs/telecom/remote/FileTransferActivity.kt)에서 수신측(`handleFileChunk`)이 청크를 수신해 디스크에 쓸 때마다 `FS_FILE_PROGRESS` 피드백 패킷을 송출하도록 하였습니다.
  - 송출 측(`transferLocalToRemote`, `sendLocalFile`) 루프에서는 프로그레스 바를 강제로 100% 등으로 올리지 않고 `"전송 중..."` 상태만 표시하며, 피드백 패킷 수신부(`onMessageReceived`의 `FS_FILE_PROGRESS` 분기)에서 실시간으로 프로그레스 진행 상황을 안전하게 갱신하게 하였습니다.
- **PC 앱 (`telecontrolpc`)**
  - [file_transfer.py](file:///c:/Temp/Antigrvity/telecontrolpc/gui/file_transfer.py)에서 `handle_file_chunk` 수신 직후 `FS_FILE_PROGRESS` 피드백 신호를 송신하도록 연동했습니다.
  - `send_local_file_async` 및 `send_requested_file_async` 송신 루프의 수동 프로그레스 갱신 로직을 제거하고, 피드백 수신 시 갱신되는 비동기 방식으로 수정했습니다.
  - [main_window.py](file:///c:/Temp/Antigrvity/telecontrolpc/gui/main_window.py)의 `handle_file_message`에서 `FS_FILE_PROGRESS` 패킷을 받아 `file_transfer_dialog`로 정상 라우팅하도록 필터를 추가했습니다.

---

## 🎯 최종 빌드 산출물

1. **Android 디버그 패키지**
   - 프로젝트 내 위치: [app-debug.apk](file:///c:/Temp/Antigrvity/telecom/app/build/outputs/apk/debug/app-debug.apk)
   - 루트 복사본: [app-debug.apk](file:///c:/Temp/Antigrvity/telecom/app-debug.apk)
2. **PC 실행 파일**
   - 빌드 배포판: [TeleControlPC.exe](file:///c:/Temp/Antigrvity/telecontrolpc/dist/TeleControlPC.exe)
   - 루트 복사본: [TeleControlPC.exe](file:///c:/Temp/Antigrvity/telecontrolpc/TeleControlPC.exe)
   - 압축 배포판: [TeleControlPC.zip](file:///c:/Temp/Antigrvity/telecontrolpc/TeleControlPC.zip)

이제 양측 기기에서 해당 실행 파일 및 패키지를 설치하신 후, 설정을 통해 동일한 AWS EC2 릴레이 서버 IP를 타겟팅하여 원활하게 6자리 핀 코드로 화면 제어를 수행하며 실시간 진행률 동기화가 반영된 파일 전송 기능을 테스트하실 수 있습니다.
