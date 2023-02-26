# -*- coding: utf8 -*-
from socketserver import BaseRequestHandler
from typing import Callable
from abc import ABCMeta
import threading
import struct

from mcdreforged.api.types import ServerInterface


class PacketType:
    COMMAND_RESPONSE = 0
    COMMAND_REQUEST = 2
    LOGIN_REQUEST = 3
    LOGIN_FAIL = -1


class Packet:
    def __init__(self, packet_id=None, packet_type=None, payload=''):
        self.packet_id = packet_id
        self.packet_type = packet_type
        self.payload = payload

    def flush(self):
        data = struct.pack('<ii', self.packet_id, self.packet_type) + bytes(self.payload + '\x00\x00', encoding='utf8')
        return struct.pack('<i', len(data)) + data


class RconHandler(BaseRequestHandler, metaclass=ABCMeta):
    BUFFER_SIZE = 2 ** 10
    running = True
    
    def __init__(self, server: ServerInterface, password: str, command_handler: Callable[[BaseRequestHandler, str], str], timeout: float, *args):
        self.password = password
        self.command_handler = command_handler
        self.timeout = timeout
        self.si = server
        super().__init__(*args)
    
    def __send(self, data):
        if type(data) is Packet:
            data = data.flush()
        self.request.send(data)
    
    def __receive(self, length):
        data = bytes()
        while len(data) < length:
            data += self.request.recv(min(self.BUFFER_SIZE, length - len(data)))
        return data

    def __receive_packet(self):
        length = struct.unpack('<i', self.__receive(4))[0]
        data = self.__receive(length)
        packet = Packet()
        packet.packet_id = struct.unpack('<i', data[0:4])[0]
        packet.packet_type = struct.unpack('<i', data[4:8])[0]
        packet.payload = data[8:-2].decode('utf8')
        return packet
    
    def setup(self):
        self.request.settimeout(self.timeout)
    
    def handle(self):
        while self.running:
            try:
                packet = self.__receive_packet()
                if packet.packet_type == PacketType.LOGIN_REQUEST:
                    password = packet.payload
                    if password == self.password:
                        self.__send(Packet(packet.packet_id, PacketType.COMMAND_RESPONSE))
                    else:
                        self.__send(Packet(PacketType.LOGIN_FAIL, PacketType.COMMAND_REQUEST))
                        self.running = False
                        break
                elif packet.packet_type == PacketType.COMMAND_REQUEST:
                    response = self.command_handler(self, packet.payload)
                    r_length = len(response)
                    start = 0
                    while start < r_length:
                        length = r_length - start
                        truncated = min(length, 2048)
                        self.__send(Packet(packet.packet_id, PacketType.COMMAND_RESPONSE, response[start:truncated]))
                        start += truncated
                else:
                    self.__send(Packet(packet.packet_id, PacketType.COMMAND_RESPONSE, f"Unknown request {hex(packet.packet_type)[2:]}"))
            except Exception:
                self.running = False
    
    def finish(self):
        self.si.logger.info(f"Thread {threading.current_thread().name} shutting down")
