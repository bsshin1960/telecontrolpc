import mss
import io
import logging
from PIL import Image

logger = logging.getLogger("ScreenCapture")

class ScreenCapturer:
    def __init__(self):
        # We don't keep mss instance open persistently in __init__ 
        # to ensure it can be safely used across threads, 
        # or we instantiate it on demand.
        pass

    def get_monitors(self):
        """
        Returns a list of dictionaries representing available monitors.
        Index 0 is the entire virtual desktop, Index 1 is the primary monitor, etc.
        """
        try:
            with mss.mss() as sct:
                monitors_list = []
                for idx, mon in enumerate(sct.monitors):
                    name = "모든 모니터" if idx == 0 else f"모니터 {idx}"
                    if idx == 1:
                        name += " (주 모니터)"
                    monitors_list.append({
                        "index": idx,
                        "name": name,
                        "left": mon["left"],
                        "top": mon["top"],
                        "width": mon["width"],
                        "height": mon["height"]
                    })
                return monitors_list
        except Exception as e:
            logger.error(f"Error getting monitors list: {e}")
            return [{"index": 0, "name": "기본 모니터", "left": 0, "top": 0, "width": 1920, "height": 1080}]

    def capture_frame(self, monitor_index: int = 1, scale: float = 0.5, quality: int = 60) -> bytes:
        """
        Captures a screenshot of the specified monitor, resizes it,
        compresses it to JPEG, and returns the byte array.
        """
        try:
            with mss.mss() as sct:
                if monitor_index >= len(sct.monitors):
                    monitor_index = 1 if len(sct.monitors) > 1 else 0
                
                monitor = sct.monitors[monitor_index]
                sct_img = sct.grab(monitor)
                
                # Convert raw BGRA data from mss to a PIL Image
                # mss raw is BGRA, so we map BGRX to RGB
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                
                # Resize if necessary
                if scale != 1.0:
                    new_w = int(sct_img.size[0] * scale)
                    new_h = int(sct_img.size[1] * scale)
                    # Use Bilinear for a good balance between speed and quality
                    img = img.resize((new_w, new_h), Image.Resampling.BILINEAR)
                
                # Save to JPEG in memory
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=quality)
                return buffer.getvalue()
        except Exception as e:
            logger.error(f"Error capturing frame: {e}")
            return b""
