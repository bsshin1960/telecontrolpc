import sys
import asyncio
import logging
from PyQt5.QtWidgets import QApplication
from qasync import QEventLoop

from gui.main_window import MainWindow

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("debug.log", mode="w", encoding="utf-8")
    ]
)

logger = logging.getLogger("ApplicationEntrypoint")

def main():
    logger.info("Initializing TeleControl Program...")
    
    # 1. Create Qt Application
    app = QApplication(sys.argv)
    app.setApplicationName("TeleControl")
    
    # 2. Integrate asyncio and Qt event loop using qasync
    loop = QEventLoop(app)
    asyncio.set_event_loop(loop)
    
    # 3. Create and show Main GUI Dashboard
    main_window = MainWindow()
    main_window.showMaximized()
    
    logger.info("Starting integrated event loop...")
    # 4. Start Event Loop
    with loop:
        try:
            loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Application interrupted by user.")
        except Exception as e:
            logger.error(f"Application crash: {e}")
        finally:
            logger.info("Shutting down TeleControl Program.")

if __name__ == "__main__":
    main()
