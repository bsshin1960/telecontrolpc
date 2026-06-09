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

---

## 🎯 최종 빌드 산출물

1. **Android 디버그 패키지**
   - 파일 위치: [app-debug.apk](file:///c:/Temp/Antigrvity/telecom/app/build/outputs/apk/debug/app-debug.apk)
2. **PC 실행 파일**
   - 파일 위치: [TeleControlPC.exe](file:///c:/Temp/Antigrvity/telecontrolpc/dist/TeleControlPC.exe)

이제 양측 기기에서 해당 실행 파일 및 패키지를 설치하신 후, 설정을 통해 동일한 AWS EC2 릴레이 서버 IP를 타겟팅하여 원활하게 6자리 핀 코드로 화면 제어를 수행하실 수 있습니다.
