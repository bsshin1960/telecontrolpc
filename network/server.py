import asyncio
import websockets
import logging
from capture.screen_capture import ScreenCapturer
from input.input_injector import InputInjector

logger = logging.getLogger("WebSocketServer")

class RemoteControlServer:
    def __init__(self, host="0.0.0.0", port=8080):
        self.host = host
        self.port = port
        self.server = None
        self.active_connections = set()
        
        self.capturer = ScreenCapturer()
        self.injector = InputInjector()
        
        # Stream settings
        self.monitor_index = 1
        self.scale = 1.0
        self.quality = 60
        self.fps = 30
        
        self.is_running = False
        self.stream_task = None
        
        # Callback to update UI with client logs
        self.log_callback = None
        
        # AWS Relay client attributes
        self.websocket = None
        self.session_id = None
        self.client_connected = False
        self.id_callback = None
        self.file_callback = None

    def set_log_callback(self, callback):
        self.log_callback = callback

    def log_message(self, message: str):
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

    def set_id_callback(self, callback):
        self.id_callback = callback

    def set_file_callback(self, callback):
        self.file_callback = callback

    def send_command(self, cmd_str: str):
        if self.websocket and self.client_connected:
            asyncio.create_task(self.websocket.send(cmd_str))

    def update_settings(self, monitor_index: int, scale: float, quality: int, fps: int):
        self.monitor_index = monitor_index
        self.scale = scale
        self.quality = quality
        self.fps = fps
        self.log_message(f"Settings updated: Monitor={monitor_index}, Scale={scale}, Quality={quality}, FPS={fps}")

    async def start(self):
        if self.is_running:
            return
        
        self.is_running = True
        self.log_message("AWS 릴레이 서버에 접속 중...")
        
        uri = f"ws://{self.host}:{self.port}/register"
        
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=15,
                ping_timeout=30,
                max_size=10 * 1024 * 1024  # 10MB limit
            )
            self.log_message("AWS 릴레이 서버 연결 성공. ID 발급 대기 중...")
            
            # Start background tasks
            self.recv_task = asyncio.create_task(self.receive_loop())
            self.stream_task = asyncio.create_task(self.screen_stream_loop())
        except Exception as e:
            self.is_running = False
            if self.websocket:
                await self.websocket.close()
                self.websocket = None
            self.log_message(f"릴레이 서버 접속 실패: {e}")
            raise e

    async def stop(self):
        if not self.is_running:
            return
        
        self.log_message("원격 제어 호스트 연결 종료 중...")
        self.is_running = False
        self.client_connected = False
        self.session_id = None
        
        # Cancel tasks
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
            self.stream_task = None
            
        if hasattr(self, "recv_task") and self.recv_task:
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
            self.recv_task = None
            
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        self.log_message("원격 제어 호스트 연결이 종료되었습니다.")

    async def receive_loop(self):
        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    logger.debug(f"Host received text message: {message}")
                    if message.startswith("ID="):
                        self.session_id = message.split("=")[1].strip()
                        self.log_message(f"연결 ID가 발급되었습니다: {self.session_id}")
                        if self.id_callback:
                            self.id_callback(self.session_id)
                    elif message == "CLIENT_CONNECTED":
                        self.client_connected = True
                        self.log_message("원격 도움 제공자(클라이언트)가 연결되었습니다.")
                        # Send handshake back to the client via relay
                        await self.websocket.send("device=windows")
                    elif message == "CLIENT_DISCONNECTED":
                        self.client_connected = False
                        self.log_message("원격 도움 제공자(클라이언트)의 연결이 해제되었습니다.")
                        asyncio.create_task(self.stop())
                    elif message.startswith("FS_"):
                        if self.file_callback:
                            self.file_callback(message)
                    else:
                        self.parse_and_inject(message)
        except websockets.exceptions.ConnectionClosed:
            self.log_message("릴레이 서버와의 연결이 비정상 종료되었습니다.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in host receive loop: {e}")
            self.log_message(f"수신 처리 오류: {e}")
        finally:
            # Clean up on disconnect
            asyncio.create_task(self.stop())

    def parse_and_inject(self, text: str):
        """
        Parses the received command CSV text and injects the corresponding inputs.
        """
        try:
            params = {}
            for part in text.split(","):
                if "=" in part:
                    k, v = part.split("=", 1)
                    params[k.strip()] = v.strip()
                    
            action = params.get("action")
            if not action:
                return

            # Log received actions to server console & GUI connections log (exclude high-frequency move event to prevent flooding)
            if action != "2":
                self.log_message(f"원격 명령 수신: action={action}, params={params}")
            else:
                logger.debug(f"원격 마우스 이동: {params}")

            # Retrieve active monitor geometry if we need to map relative coordinates
            monitors = self.capturer.get_monitors()
            active_monitor = None
            for m in monitors:
                if m["index"] == self.monitor_index:
                    active_monitor = m
                    break
            if not active_monitor and len(monitors) > 1:
                active_monitor = monitors[1] # fallback to primary monitor
            
            # Standard Touch / Mouse Move / Click Actions
            # action: 0 (down), 1 (up), 2 (move)
            if action in ["0", "1", "2"]:
                x_ratio = float(params.get("x", 0.0))
                y_ratio = float(params.get("y", 0.0))
                
                # Move first
                self.injector.move_mouse(x_ratio, y_ratio, active_monitor)
                
                # Mouse Click Actions
                button = params.get("button", "left")
                if action == "0":
                    self.injector.press_mouse_button(button, True)
                elif action == "1":
                    self.injector.press_mouse_button(button, False)
                    
            # Extended Mouse Button Click Actions (right_down, right_up, middle_down, middle_up)
            elif action in ["right_down", "right_up", "middle_down", "middle_up"]:
                x_ratio = float(params.get("x", 0.0))
                y_ratio = float(params.get("y", 0.0))
                self.injector.move_mouse(x_ratio, y_ratio, active_monitor)
                
                is_down = "down" in action
                button = "right" if "right" in action else "middle"
                self.injector.press_mouse_button(button, is_down)
                
            # Mouse Scroll Wheel Actions
            elif action == "scroll":
                dx = float(params.get("dx", 0.0))
                dy = float(params.get("dy", 0.0))
                self.injector.scroll_mouse(dx, dy)
                
            # Keyboard key press / release actions
            elif action in ["key_down", "key_up"]:
                key_code = int(params.get("key", 0))
                is_down = action == "key_down"
                self.injector.inject_key_event(key_code, is_down)
                
            # Character input direct injection (Unicode)
            elif action == "char":
                text_content = params.get("text", "")
                self.injector.inject_unicode_char(text_content)
                
        except Exception as e:
            logger.error(f"Error parsing control message '{text}': {e}")

    async def screen_stream_loop(self):
        """
        Continuously captures screen frames and sends them to the connected client.
        """
        while self.is_running:
            if not (self.websocket and self.client_connected):
                await asyncio.sleep(0.1)
                continue
                
            start_time = asyncio.get_event_loop().time()
            
            try:
                frame_bytes = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.capturer.capture_frame,
                    self.monitor_index,
                    self.scale,
                    self.quality
                )
                
                if frame_bytes and self.websocket and self.client_connected:
                    # Android ClientActivity expects: first byte = 0 (video), rest = JPEG data
                    await self.websocket.send(b'\x00' + frame_bytes)
            except Exception as e:
                logger.error(f"Error in screen stream loop: {e}")
                
            # Control frame rate
            elapsed = asyncio.get_event_loop().time() - start_time
            delay = max(0.0, (1.0 / self.fps) - elapsed)
            await asyncio.sleep(delay)
