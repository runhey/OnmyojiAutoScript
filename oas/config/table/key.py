"""Per-configuration key/value metadata."""

from __future__ import annotations

import secrets
import sqlite3
import uuid
from typing import TypeVar as TypingTypeVar

import msgspec

from oas.config.table.base import ConfigDB
from oas.ext.cache import cached_property
from oas.logger import logger

T_model = TypingTypeVar('T_model', bound=msgspec.Struct)


class KeyValue(msgspec.Struct):
    key: str
    value: bytes
    id: int = 0


class JwtSecret(msgspec.Struct):
    secret: bytes = b''
    macsha1: bytes = b''

    @staticmethod
    def host_macsha1() -> bytes:
        mac = uuid.getnode()
        if mac & (1 << 40):
            return b''
        return __import__('hashlib').sha1(mac.to_bytes(6, 'big')).digest()


class KeyTable(ConfigDB):
    """Store binary metadata inside one named configuration database."""

    TABLE_NAME = 'alasio'
    CREATE_TABLE = """
        CREATE TABLE "{TABLE_NAME}" (
        "id" INTEGER NOT NULL,
        "key" TEXT NOT NULL,
        "value" BLOB NOT NULL,
        PRIMARY KEY ("id"),
        UNIQUE ("key")
    );
    """
    MODEL = KeyValue

    def get_value(self, key: str, default: bytes | None = None) -> bytes | None:
        row = self.select_one(key=key)
        return default if row is None else row.value

    def set_value(self, key: str, value: bytes) -> None:
        if not isinstance(value, bytes):
            raise TypeError('KeyTable value must be bytes')
        self.upsert_row(KeyValue(key=key, value=value), conflicts='key')

    def get(self, key: str, model_cls: type[T_model]) -> T_model:
        """Decode a MsgPack value into ``model_cls``; return its default if absent."""

        value = self.get_value(key)
        if value is None:
            return model_cls()
        return msgspec.msgpack.decode(value, type=model_cls)

    def set(self, key: str, model: T_model) -> None:
        self.set_value(key, msgspec.msgpack.encode(model))

    def mod_get(self) -> str:
        try:
            value = self.get_value('Mod', b'')
        except sqlite3.DatabaseError:
            return ''
        if not value:
            return ''
        try:
            return value.decode('utf-8')
        except UnicodeDecodeError:
            return ''

    def mod_set(self, value: str) -> None:
        if not isinstance(value, str):
            raise TypeError('mod value must be str')
        self.set_value('Mod', value.encode('utf-8'))

    @cached_property
    def jwt_secret(self) -> bytes:
        """Get or create a host-bound secret for this configuration database."""

        value = self.get('JwtSecret', JwtSecret)
        length = 32
        if not value.secret:
            logger.info('New JWT secret (new secret)')
            value.secret = secrets.token_bytes(length)
            value.macsha1 = JwtSecret.host_macsha1()
            self.set('JwtSecret', value)
            return value.secret
        if len(value.secret) != length:
            logger.info('New JWT secret (length not match)')
            value.secret = secrets.token_bytes(length)
            value.macsha1 = JwtSecret.host_macsha1()
            self.set('JwtSecret', value)
            return value.secret

        macsha1 = JwtSecret.host_macsha1()
        if value.macsha1 != macsha1:
            logger.info('New JWT secret (MAC changed)')
            value.secret = secrets.token_bytes(length)
            value.macsha1 = macsha1
            self.set('JwtSecret', value)
        return value.secret


AlasioKeyTable = KeyTable

__all__ = ['AlasioKeyTable', 'JwtSecret', 'KeyTable', 'KeyValue']
