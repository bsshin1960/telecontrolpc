import asyncio
import websockets
import logging
import time

logger = logging.getLogger("WebSocketClient")

class RemoteControlClient:
    def __init__(self):
        self.websocket = None
        self.is_connected = False
        self.is_windows_host = False
        
        # Queues and Tasks
        self.send_queue = asyncio.Queue()
        self.recv_task = None
        self.send_task = None
        self.trigger_task = None
        
        # Callbacks
        self.frame_callback = None
        self.status_callback = None
        self.stats_callback = None
        
        # Statistics
        self.frame_count = 0
        self.byte_count = 0
        self.last_stats_time = 0
        self.ping_latency = 0.0

    def set_callbacks(self, frame_cb=None, status_cb=None, stats_cb=None):
        self.frame_callback = frame_cb
        self.status_callback = status_cb
        self.stats_callback = stats_cb

    def log_status(self, message: str):
        logger.info(message)
        if self.status_callback:
            self.status_callback(message)

    async def connect(self, host: str, port: int = 8080):
        if self.is_connected:
            return
            
        uri = f"ws://{host}:{port}/control"
        self.log_status(f"원격 호스트에 연결 시도 중 ({uri})...")
        
        try:
            self.websocket = await websockets.connect(
                uri,
                ping_interval=15,
                ping_timeout=30,
                max_size=10 * 1024 * 1024  # 10MB limit for frames
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
                    if "device=windows" in message:
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
                                # Skip audio frames since video player doesn't handle them
                                pass
                        
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
