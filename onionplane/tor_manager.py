"""Thin wrapper over stem's controller for provisioning onion services."""
import socket

from stem.control import Controller

from . import config


class TorManager:
    def __init__(self) -> None:
        self._controller: Controller | None = None

    def connect(self) -> None:
        # stem wants an IP, not a hostname -- resolve it (Docker service name,
        # "localhost", etc.) so both local and containerized setups work.
        address = socket.gethostbyname(config.CONTROL_HOST)
        controller = Controller.from_port(address=address, port=config.CONTROL_PORT)
        if config.CONTROL_PASSWORD:
            controller.authenticate(password=config.CONTROL_PASSWORD)
        else:
            controller.authenticate()
        self._controller = controller

    def close(self) -> None:
        if self._controller is not None:
            try:
                self._controller.close()
            finally:
                self._controller = None

    @property
    def controller(self) -> Controller:
        if self._controller is None:
            raise RuntimeError("TorManager is not connected")
        return self._controller

    def _ports(self, local_port: int) -> dict:
        return {config.VIRTUAL_PORT: f"{config.DEFAULT_TARGET_HOST}:{local_port}"}

    def create_service(self, local_port: int) -> tuple[str, str]:
        resp = self.controller.create_ephemeral_hidden_service(
            self._ports(local_port),
            key_type="NEW",
            key_content="ED25519-V3",
            discard_key=False,
            await_publication=True,
        )
        return f"{resp.service_id}.onion", resp.private_key

    def register_service(self, private_key: str, local_port: int) -> str:
        key_type, _, key_content = private_key.partition(":")
        resp = self.controller.create_ephemeral_hidden_service(
            self._ports(local_port),
            key_type=key_type,
            key_content=key_content,
            await_publication=True,
        )
        return f"{resp.service_id}.onion"

    def remove_service(self, onion_address: str) -> None:
        service_id = onion_address.removesuffix(".onion")
        self.controller.remove_ephemeral_hidden_service(service_id)
