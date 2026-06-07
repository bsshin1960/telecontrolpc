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

    def set_log_callback(self, callback):
        self.log_callback = callback

    def log_message(self, message: str):
        logger.info(message)
        if self.log_callback:
            self.log_callback(message)

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
        self.log_message(f"Starting server on {self.host}:{self.port}...")
        
        try:
            self.server = await websockets.serve(
                self.handler, 
                self.host, 
                self.port,
                ping_interval=15,
                ping_timeout=30
            )
            self.log_message("WebSocket Server running successfully.")
            
            # Start the screen streaming loop
            self.stream_task = asyncio.create_task(self.screen_stream_loop())
        except Exception as e:
            self.is_running = False
            self.log_message(f"Failed to start server: {e}")
            raise e

    async def stop(self):
        if not self.is_running:
            return
        
        self.log_message("Stopping server...")
        self.is_running = False
        
        # Cancel the stream task
        if self.stream_task:
            self.stream_task.cancel()
            try:
                await self.stream_task
            except asyncio.CancelledError:
                pass
            self.stream_task = None
            
        # Close all active client connections
        if self.active_connections:
            connections_to_close = list(self.active_connections)
            for conn in connections_to_close:
                await conn.close()
            self.active_connections.clear()
            
        # Close server
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            
        self.log_message("Server stopped.")

    async def handler(self, websocket):
        # Register connection
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.log_message(f"Client connected: {client_address}")
        self.active_connections.add(websocket)
        
        try:
            # 1. Send Handshake
            await websocket.send("device=windows")
            
            # 2. Handle incoming messages
            async for message in websocket:
                if isinstance(message, str):
                    self.parse_and_inject(message)
        except websockets.exceptions.ConnectionClosed:
            self.log_message(f"Client disconnected: {client_address}")
        except Exception as e:
            logger.error(f"Error handling client {client_address}: {e}")
        finally:
            self.active_connections.remove(websocket)
            self.log_message(f"Connection closed for: {client_address}")

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
        Continuously captures screen frames and broadcasts them to all connected clients.
        Only performs capture and compression if there are active connections.
        """
        while self.is_running:
            if not self.active_connections:
                await asyncio.sleep(0.1)
                continue
                
            start_time = asyncio.get_event_loop().time()
            
            # Capture and compress frame
            # Run in executor to avoid blocking the main asyncio event loop
            try:
                frame_bytes = await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.capturer.capture_frame,
                    self.monitor_index,
                    self.scale,
                    self.quality
                )
                
                if frame_bytes and self.active_connections:
                    # Broadcast to all clients
                    # websockets.broadcast requires a list of connections
                    websockets.broadcast(self.active_connections, frame_bytes)
            except Exception as e:
                logger.error(f"Error in screen stream loop: {e}")
                
            # Control frame rate
            elapsed = asyncio.get_event_loop().time() - start_time
            delay = max(0.0, (1.0 / self.fps) - elapsed)
            await asyncio.sleep(delay)
