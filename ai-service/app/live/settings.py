from dataclasses import dataclass
from ipaddress import ip_address, ip_network
import os
from urllib.parse import urlsplit

LOCAL_RANGES = tuple(ip_network(value) for value in (
    "127.0.0.0/8", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16", "::1/128", "fc00::/7",
))


@dataclass(frozen=True)
class Settings:
    username: str
    password_hash: str
    origin: str = "http://127.0.0.1:8000"
    allowed_networks: tuple[str, ...] = ("127.0.0.0/8", "::1/128")
    session_seconds: int = 900
    camera_index: int = 0
    width: int = 960
    height: int = 540
    fps: int = 12
    frame_timeout: float = 0.75

    def __post_init__(self) -> None:
        parsed = urlsplit(self.origin)
        if not self.username or not self.password_hash.startswith("scrypt$"):
            raise ValueError("Configure LIVE_USERNAME e LIVE_PASSWORD_HASH; não há senha padrão.")
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
            raise ValueError("LIVE_ORIGIN deve ser uma origem exata, sem caminho.")
        local_http = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.scheme == "http" and not local_http:
            raise ValueError("Acesso LAN exige HTTPS. HTTP é permitido somente em loopback.")
        if not 5 <= self.session_seconds <= 3600:
            raise ValueError("Sessão deve durar entre 5 e 3600 segundos.")
        if self.camera_index < 0 or not (320 <= self.width <= 1920 and 240 <= self.height <= 1080):
            raise ValueError("Câmera ou resolução inválida.")
        if not 1 <= self.fps <= 30 or not 0.1 <= self.frame_timeout <= 2:
            raise ValueError("FPS ou validade de quadro inválidos.")
        if not self.allowed_networks:
            raise ValueError("Defina ao menos uma rede autorizada.")
        for value in self.allowed_networks:
            network = ip_network(value)
            if not any(network.version == parent.version and network.subnet_of(parent)
                       for parent in LOCAL_RANGES):
                raise ValueError("Somente sub-redes privadas/loopback explícitas são permitidas.")

    @property
    def secure_cookie(self) -> bool:
        return self.origin.startswith("https://")

    @property
    def host(self) -> str:
        return urlsplit(self.origin).netloc

    def allows(self, host: str) -> bool:
        try:
            address = ip_address(host)
            return any(address in ip_network(value) for value in self.allowed_networks)
        except ValueError:
            return False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            username=os.environ.get("LIVE_USERNAME", ""),
            password_hash=os.environ.get("LIVE_PASSWORD_HASH", ""),
            origin=os.environ.get("LIVE_ORIGIN", "http://127.0.0.1:8000"),
            allowed_networks=tuple(value.strip() for value in os.environ.get(
                "LIVE_ALLOWED_NETWORKS", "127.0.0.0/8,::1/128").split(",")),
            session_seconds=int(os.environ.get("LIVE_SESSION_SECONDS", "900")),
            camera_index=int(os.environ.get("LIVE_CAMERA_INDEX", "0")),
            width=int(os.environ.get("LIVE_WIDTH", "960")),
            height=int(os.environ.get("LIVE_HEIGHT", "540")),
            fps=int(os.environ.get("LIVE_FPS", "12")),
        )
