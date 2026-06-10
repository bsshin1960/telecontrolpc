import os
import json
import logging

logger = logging.getLogger("Config")

CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".telecontrol_config.json")

DEFAULT_RELAY_HOST = "54.242.81.228"
DEFAULT_RELAY_PORT = 8080
DEFAULT_AUTO_START = False


def load_config() -> dict:
    """
    ~/.telecontrol_config.json 에서 설정을 불러옵니다.
    파일이 없거나 손상된 경우 기본값을 반환합니다.
    """
    defaults = {
        "relay_host": DEFAULT_RELAY_HOST,
        "relay_port": DEFAULT_RELAY_PORT,
        "auto_start": DEFAULT_AUTO_START,
    }
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                # 필수 키가 있는지 확인하고 기본값으로 보완
                defaults.update(data)
        except Exception as e:
            logger.warning(f"설정 파일 읽기 실패, 기본값 사용: {e}")
    return defaults


def save_config(relay_host: str, relay_port: int, auto_start: bool = DEFAULT_AUTO_START):
    """
    릴레이 서버 설정을 ~/.telecontrol_config.json 에 저장합니다.
    """
    data = {
        "relay_host": relay_host,
        "relay_port": relay_port,
        "auto_start": auto_start,
    }
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.info(f"설정 저장 완료: {relay_host}:{relay_port}, auto_start={auto_start}")
    except Exception as e:
        logger.error(f"설정 파일 저장 실패: {e}")


def get_relay_host() -> str:
    return load_config().get("relay_host", DEFAULT_RELAY_HOST)


def get_relay_port() -> int:
    return int(load_config().get("relay_port", DEFAULT_RELAY_PORT))


def get_auto_start() -> bool:
    return bool(load_config().get("auto_start", DEFAULT_AUTO_START))
