import asyncio
import websockets
import logging
import time

try:
    from PyQt5.QtMultimedia import QAudioOutput, QAudioFormat
    HAS_AUDIO = True
except ImportError:
    HAS_AUDIO = False


logger = logging.getLogger("WebSocketClient")

class RemoteControlClient:
    def __init__(self):
        self.websocket = None
        self.is_connected = False
        self.is_windows_host = False
        self.going_to_settings = False  # 휴대폰이 설정 화면 중인지 여부
        
        # Audio properties
        self.audio_output = None
        self.audio_device = None
        
        # Queues and Tasks
        self.send_queue = asyncio.Queue()
        self.recv_task = None
        self.send_task = None
        self.trigger_task = None
        
        # Callbacks
        self.frame_callback = None
        self.status_callback = None
        self.stats_callback = None
        self.file_callback = None
        self.settings_status_callback = None  # 설정 화면 이동/복굼 알림
        
        # Statistics
        self.frame_count = 0
        self.byte_count = 0
        self.last_stats_time = 0
        self.ping_latency = 0.0

    def set_callbacks(self, frame_cb=None, status_cb=None, stats_cb=None, settings_status_cb=None):
        self.frame_callback = frame_cb
        self.status_callback = status_cb
        self.stats_callback = stats_cb
        self.settings_status_callback = settings_status_cb

    def set_file_callback(self, cb):
        self.file_callback = cb

    def log_status(self, message: str):
        logger.info(message)
        if self.status_callback:
            self.status_callback(message)

    async def connect(self, host: str, port: int = 80, session_id: str = ""):
        if self.is_connected:
            return
            
        if session_id:
            uri = f"ws://{host}:{port}/join/{session_id}"
        else:
            uri = f"ws://{host}:{port}/control"
            
        self.log_status(f"원격 호스트에 연결 시도 중 ({uri})...")
        
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=30,
                ping_timeout=60,
                max_size=80 * 1024 * 1024  # 80MB limit for frames
            )
            self.is_connected = True
            self.is_windows_host = False # reset
            
            # Start background tasks
            self.recv_task = asyncio.create_task(self.receive_loop())
            self.send_task = asyncio.create_task(self.send_loop())
            self.trigger_task = asyncio.create_task(self.trigger_ready_loop())
            
            self.last_stats_time = time.time()
            self.frame_count = 0
            self.byte_count = 0
            
            if session_id:
                self.log_status("릴레이 서버 접속 완료. 상대방 연결을 기다리는 중...")
            else:
                self.log_status("원격 호스트에 성공적으로 연결되었습니다.")
        except Exception as e:
            self.is_connected = False
            self.log_status(f"연결 실패: {e}")
            raise e

    async def disconnect(self):
        if not self.is_connected:
            return
            
        self.log_status("연결 해제 중...")
        self.is_connected = False
        
        # Stop audio playback
        if self.audio_output:
            try:
                self.audio_output.stop()
            except Exception as e:
                logger.error(f"Error stopping audio output: {e}")
            self.audio_output = None
        self.audio_device = None
        
        # Cancel tasks
        if self.recv_task:
            self.recv_task.cancel()
            try:
                await self.recv_task
            except asyncio.CancelledError:
                pass
            self.recv_task = None
            
        if self.send_task:
            self.send_task.cancel()
            try:
                await self.send_task
            except asyncio.CancelledError:
                pass
            self.send_task = None
            
        if hasattr(self, "trigger_task") and self.trigger_task:
            self.trigger_task.cancel()
            try:
                await self.trigger_task
            except asyncio.CancelledError:
                pass
            self.trigger_task = None
            
        # Clear send queue
        while not self.send_queue.empty():
            try:
                self.send_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
                
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        self.log_status("연결이 해제되었습니다.")

    async def receive_loop(self):
        """
        Listens for incoming frames from the WebSocket.
        - Handshake message may be 'device=windows'
        - Binary messages are screen JPEG frames.
        """
        try:
            logger.debug("Starting client receive loop")
            async for message in self.websocket:
                # Stats calculation
                current_time = time.time()
                
                # Check for handshake
                if isinstance(message, str):
                    logger.debug(f"Received text message: {message}")
                    if message.startswith("FS_"):
                        if self.file_callback:
                            self.file_callback(message)
                        continue
                    if message == "CONNECTED":
                        self.log_status("원격 호스트와 연결되었습니다 (릴레이 서버 매칭 성공).")
                        continue
                    elif message == "HOST_DISCONNECTED":
                        self.log_status("원격 호스트의 접속이 종료되었습니다.")
                        asyncio.create_task(self.disconnect())
                        continue
                    elif message.startswith("GOING_TO_SETTINGS|"):
                        # 휴대폰이 설정 화면으로 이동한 경우 — 연결 끊김이 아닙니다!
                        setting_name = message.split("|", 1)[1] if "|" in message else ""
                        self.going_to_settings = True
                        status_msg = f"📱 휴대폰이 [{setting_name}] 화면으로 이동 중... (앞 화면이 잊시 미표시될 수 있습니다)"
                        self.log_status(status_msg)
                        if self.settings_status_callback:
                            self.settings_status_callback("going", setting_name)
                        continue
                    elif message == "RETURNED_FROM_SETTINGS":
                        # 화면에서 돌아왔을 때
                        self.going_to_settings = False
                        self.log_status("✅ 휴대폰이 설정에서 돌아왔습니다. 화면 스트림이 재개됩니다.")
                        if self.settings_status_callback:
                            self.settings_status_callback("returned", "")
                        continue
                    elif "device=windows" in message:
                        self.is_windows_host = True
                        if hasattr(self, "trigger_task") and self.trigger_task:
                            self.trigger_task.cancel()
                            self.trigger_task = None
                        self.log_status("Windows 원격 호스트 감지: 확장 키보드/마우스 입력 기능이 활성화되었습니다.")
                        continue
                
                # Process message
                if isinstance(message, bytes):
                    logger.debug(f"Received binary message: {len(message)} bytes")
                    if self.is_windows_host:
                        if hasattr(self, "trigger_task") and self.trigger_task:
                            self.trigger_task.cancel()
                            self.trigger_task = None
                        self.frame_count += 1
                        self.byte_count += len(message)
                        if self.frame_callback:
                            try:
                                self.frame_callback(message)
                            except Exception as cb_err:
                                logger.error(f"Error calling frame callback: {cb_err}")
                    else:
                        # Android host: first byte is frame type (0 = video, 1 = audio)
                        if len(message) > 1:
                            frame_type = message[0]
                            if frame_type == 0:  # Video frame
                                if hasattr(self, "trigger_task") and self.trigger_task:
                                    self.trigger_task.cancel()
                                    self.trigger_task = None
                                self.frame_count += 1
                                self.byte_count += len(message) - 1
                                if self.frame_callback:
                                    try:
                                        self.frame_callback(message[1:])
                                    except Exception as cb_err:
                                        logger.error(f"Error calling frame callback: {cb_err}")
                            elif frame_type == 1:  # Audio frame
                                if HAS_AUDIO and len(message) > 1:
                                    if self.audio_output is None:
                                        try:
                                            format = QAudioFormat()
                                            format.setSampleRate(16000)
                                            format.setChannelCount(1)
                                            format.setSampleSize(16)
                                            format.setCodec("audio/pcm")
                                            format.setByteOrder(QAudioFormat.LittleEndian)
                                            format.setSampleType(QAudioFormat.SignedInt)
                                            self.audio_output = QAudioOutput(format)
                                            self.audio_device = self.audio_output.start()
                                            logger.info("PCM Audio Output started (16kHz, mono, 16bit)")
                                        except Exception as ae:
                                            logger.error(f"Error initializing QAudioOutput: {ae}")
                                    
                                    if self.audio_device:
                                        try:
                                            self.audio_device.write(message[1:])
                                        except Exception as ae:
                                            logger.error(f"Error writing to audio device: {ae}")
                        
                # Update statistics every second
                delta = current_time - self.last_stats_time
                if delta >= 1.0:
                    fps = self.frame_count / delta
                    kb_s = (self.byte_count / 1024.0) / delta
                    # Get ping latency if available in websockets API
                    if self.websocket and hasattr(self.websocket, 'latency'):
                        self.ping_latency = self.websocket.latency * 1000.0  # ms
                        
                    if self.stats_callback:
                        self.stats_callback(fps, kb_s, self.ping_latency)
                        
                    # Reset stats accumulators
                    self.frame_count = 0
                    self.byte_count = 0
                    self.last_stats_time = current_time
                    
        except websockets.exceptions.ConnectionClosed:
            self.log_status("원격 호스트에 의해 연결이 종료되었습니다.")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in client receive loop: {e}")
            self.log_status(f"오류 발생: {e}")
        finally:
            # Trigger disconnection from client side
            asyncio.create_task(self.disconnect())

    async def send_loop(self):
        """
        Takes commands from queue and sends them to the server.
        """
        try:
            while self.is_connected:
                cmd = await self.send_queue.get()
                if self.websocket and self.is_connected:
                    await self.websocket.send(cmd)
                self.send_queue.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in client send loop: {e}")

    def send_command(self, cmd_str: str):
        if self.is_connected:
            self.send_queue.put_nowait(cmd_str)

    def send_touch_event(self, action: int, x_ratio: float, y_ratio: float, button: str = "left"):
        """
        Sends a touch / mouse move event to the server.
        Compatible with Android Host protocol:
        action: 0=down, 1=up, 2=move
        """
        # Always clamp coordinates to 0.0 - 1.0 range
        x = max(0.0, min(1.0, x_ratio))
        y = max(0.0, min(1.0, y_ratio))
        
        # Format matching the reference Android Host: action=<int>,x=<float>,y=<float>
        # We append button parameter. The Android Host will split by comma and ignore unknown parameters.
        # This makes it fully backward-compatible!
        if self.is_windows_host:
            cmd = f"action={action},x={x:.5f},y={y:.5f},button={button}"
        else:
            # Pure Android compatible
            cmd = f"action={action},x={x:.5f},y={y:.5f}"
            
        self.send_command(cmd)

    def send_extended_mouse_event(self, action: str, x_ratio: float, y_ratio: float):
        """
        Sends extended mouse clicks (right/middle down/up).
        Ignored by Android Host due to custom action string.
        """
        if not self.is_windows_host:
            # Fallback: if user right-clicks on an Android screen, 
            # we don't send right clicks since Android won't understand it, 
            # or we map it to Back if desired. For now, skip to prevent crashing.
            return
            
        x = max(0.0, min(1.0, x_ratio))
        y = max(0.0, min(1.0, y_ratio))
        
        cmd = f"action={action},x={x:.5f},y={y:.5f}"
        self.send_command(cmd)

    def send_scroll_event(self, dx: float, dy: float):
        """
        Sends mouse wheel scroll. Only for Windows Host.
        """
        if not self.is_windows_host:
            return
        cmd = f"action=scroll,dx={dx:.3f},dy={dy:.3f}"
        self.send_command(cmd)

    def send_key_event(self, action: str, key_code: int):
        """
        Sends keyboard key down / key up. Only for Windows Host.
        action: 'key_down' or 'key_up'
        """
        if not self.is_windows_host:
            return
        cmd = f"action={action},key={key_code}"
        self.send_command(cmd)

    def send_char_event(self, text: str):
        """
        Sends text character input. Only for Windows Host.
        """
        if not self.is_windows_host:
            return
        # Escape comma to avoid parsing splitting bugs
        escaped_text = text.replace(",", "\\,")
        cmd = f"action=char,text={escaped_text}"
        self.send_command(cmd)

    async def trigger_ready_loop(self):
        """
        Periodically sends CLIENT_READY to Android host every 200ms
        until the first video frame or handshake is received, prompting immediate redraw.
        """
        try:
            while self.is_connected:
                self.send_command("CLIENT_READY")
                await asyncio.sleep(0.2)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error in trigger_ready_loop: {e}")
