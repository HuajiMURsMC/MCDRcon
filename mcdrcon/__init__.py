from socketserver import BaseRequestHandler, ThreadingTCPServer
from typing import Union, List
from functools import partial
from threading import Thread
import os

from mcdreforged.api.types import PluginServerInterface, CommandSource, ServerInterface
from mcdreforged.api.utils.serializer import Serializable
from mcdreforged.api.rtext import RTextBase

from mcdrcon.rcon import RconHandler

rcon_server = None


class Config(Serializable):
    host: str = "127.0.0.1"
    port: int = 11412
    password: str = ""
    permission_level: int = 4
    timeout: float = 0.5


class RconCommandSource(CommandSource):
    def __init__(self, server: ServerInterface, address: str, permission_level: int) -> None:
        self.__server = server
        self.__address = address
        self.__permission_level = permission_level
        self.__replies = []
    
    @property
    def is_player(self) -> bool:
        return False

    @property
    def is_console(self) -> bool:
        return False
    
    def get_permission_level(self) -> int:
        return self.__permission_level
    
    def get_server(self):
        return self.__server
    
    def get_preference(self):
        return self.__server._mcdr_server.preference_manager.get_default_preference()
    
    def reply(self, message: Union[str, RTextBase], **kwargs):
        self.__replies.append(str(message))
    
    def get_replies(self) -> List[str]:
        return self.__replies
    
    def __str__(self):
        return f'RCON {self.__address}'

    def __repr__(self):
        return f'{self.__name__}[address={self.__address}]'


def command_handler(server: ServerInterface, config: Config, request_handler: BaseRequestHandler, command: str):
    src = RconCommandSource(server, request_handler.client_address[0], config.permission_level)
    server.execute_command(command, src)
    return "\n".join(src.get_replies())


def on_load(server: PluginServerInterface, old):
    global rcon_server
    
    config = server.load_config_simple(os.path.join("config", "mcdrcon.json"), in_data_folder=False, target_class=Config)
    rcon_server = ThreadingTCPServer((config.host, config.port), partial(RconHandler, server, config.password, partial(command_handler, server, config), config.timeout))
    Thread(target=rcon_server.serve_forever, name="RCON Listener", daemon=True).start()
    server.logger.info(f"RCON running on {config.host}:{config.port}")


def on_unload(server: PluginServerInterface):
    global rcon_server
    
    if rcon_server is not None:
        rcon_server.shutdown()
        rcon_server = None
