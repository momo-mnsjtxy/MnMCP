#!/usr/bin/env python3
"""
MnMCP 数据包处理器
处理 Minecraft 协议数据包
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MCPPocket:
    """Minecraft 数据包"""
    packet_id: int
    data: bytes
    timestamp: datetime
    direction: str  # "in" or "out"


class MCPPocketHandler:
    """
    Minecraft 数据包处理器
    
    功能:
    - 解析数据包
    - 编码数据包
    - 事件分发
    - 数据转换
    """

    # 本处理器仅接受单个未压缩帧；长度包含 ID，不包含长度前缀。
    MAX_PACKET_SIZE = 2**21 - 1
    MAX_VARINT = 2**31 - 1
    
    def __init__(self, client):
        self.client = client
        self._handlers: Dict[int, Callable] = {}
        self.registry = {}  # 协议注册表
    
    def register_handler(self, packet_id: int, handler: Callable):
        """注册数据包处理器"""
        self._handlers[packet_id] = handler
    
    async def parse_packet(self, raw_data: bytes) -> Optional[MCPPocket]:
        """
        解析原始数据为数据包
        
        格式: [长度: VarInt] [ID: VarInt] [数据: bytes]。
        必须提供恰好一个完整的未压缩帧；无效或超限帧返回 None。
        """
        try:
            # 读取长度
            length, offset = self._read_varint(raw_data, 0)
            if length <= 0 or length > self.MAX_PACKET_SIZE:
                raise ValueError("Invalid packet length")
            frame_end = offset + length
            if frame_end != len(raw_data):
                raise ValueError("Expected exactly one complete packet")
            
            # 读取ID
            packet_id, offset = self._read_varint(raw_data, offset)
            
            # 读取数据
            data = raw_data[offset:frame_end]
            
            return MCPPocket(
                packet_id=packet_id,
                data=data,
                timestamp=datetime.now(),
                direction="in"
            )
            
        except Exception as e:
            logger.error(f"解析错误: {e}")
            return None
    
    def encode_packet(self, packet_id: int, data: bytes) -> bytes:
        """编码单个未压缩帧；无效编号或超限数据抛出 ValueError。"""
        # ID + 数据
        encoded_id = self._write_varint(packet_id)
        if len(encoded_id) + len(data) > self.MAX_PACKET_SIZE:
            raise ValueError("Packet too large")
        packet_data = encoded_id + data
        
        # 长度 + 包
        result = self._write_varint(len(packet_data)) + packet_data
        
        return result
    
    def _read_varint(self, data: bytes, offset: int) -> tuple:
        """读取编号/长度使用的非负 32 位 VarInt，不接受截断或溢出。"""
        if not isinstance(offset, int) or offset < 0 or offset >= len(data):
            raise ValueError("Invalid VarInt offset")
        result = 0
        
        for index in range(5):
            if offset >= len(data):
                raise ValueError("数据不足")
            
            byte = data[offset]
            offset += 1
            
            result |= (byte & 0x7F) << (7 * index)
            if result > self.MAX_VARINT:
                raise ValueError("VarInt out of range")
            
            if not (byte & 0x80):
                return result, offset
        raise ValueError("VarInt 太大")
    
    def _write_varint(self, value: int) -> bytes:
        """写入编号/长度使用的非负 32 位 VarInt。"""
        if type(value) is not int or not 0 <= value <= self.MAX_VARINT:
            raise ValueError("VarInt out of range")
        result = bytearray()
        
        while True:
            byte = value & 0x7F
            value >>= 7
            
            if value:
                byte |= 0x80
            
            result.append(byte)
            
            if not value:
                break
        
        return bytes(result)
    
    def _read_string(self, data: bytes, offset: int) -> tuple:
        """读取字符串"""
        length, offset = self._read_varint(data, offset)
        if length > len(data) - offset:
            raise ValueError("Incomplete string")
        string_data = data[offset:offset + length]
        return string_data.decode('utf-8'), offset + length
    
    def _write_string(self, value: str) -> bytes:
        """写入字符串"""
        encoded = value.encode('utf-8')
        return self._write_varint(len(encoded)) + encoded
