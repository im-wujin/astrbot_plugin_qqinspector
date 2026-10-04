"""
SQLite 缓存层 — 低阶 CRUD 操作
=================================

提供基于 SQLite + pickle 的键值缓存，所有读写自带线程锁保护。
对外暴露 CacheManager 供插件主类及其他模块使用。
"""

import pickle
import sqlite3
import threading
import time
from pathlib import Path
from astrbot.api import logger
from astrbot.core.utils.astrbot_path import get_astrbot_data_path


class CacheManager:
    """基于 SQLite 的持久化缓存管理器（线程安全）"""

    def __init__(self, plugin_name: str):
        db_path = str(
            Path(get_astrbot_data_path())
            / "plugin_data"
            / plugin_name
            / "cache.db"
        )
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")  # 读写不互斥
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value BLOB)"
        )
        self._conn.commit()

    # ---- 低阶 API --------------------------------------------------------

    def get(self, key: str):
        """读取缓存，不存在返回 None"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT value FROM cache WHERE key=?", (key,)
            )
            row = cur.fetchone()
        if row:
            return pickle.loads(row[0])
        return None

    def set(self, key: str, value):
        """写入缓存（UPSERT），同时记录更新时间戳"""
        now = time.time()
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (key, pickle.dumps(value)),
            )
            self._conn.execute(
                "INSERT OR REPLACE INTO cache (key, value) VALUES (?, ?)",
                (f"__updated_at:{key}", pickle.dumps(now)),
            )
            self._conn.commit()

    def get_updated_at(self, key: str):
        """获取缓存条目的最后更新时间戳（Unix 时间戳），无缓存返回 None"""
        return self.get(f"__updated_at:{key}")

    # ---- 高阶便利方法 ----------------------------------------------------

    def get_group_info(self, gid: str):
        return self.get(f"group_info:{gid}")

    def set_group_info(self, gid: str, info: dict):
        self.set(f"group_info:{gid}", info)

    def get_group_members(self, gid: str):
        return self.get(f"group_members:{gid}")

    def get_group_members_batch(self, gids: list[str]) -> dict[str, list]:
        """
        批量获取多个群的成员列表，单次 SQL 查询。
        锁内仅读取 raw bytes，反序列化在锁外执行，减少锁持有时间。

        :param gids: 群 ID 列表
        :returns: {gid: member_list} 字典
        """
        if not gids:
            return {}
        keys = [f"group_members:{gid}" for gid in gids]
        placeholders = ",".join("?" for _ in keys)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT key, value FROM cache WHERE key IN ({placeholders})",
                keys,
            )
            rows = cur.fetchall()
        result: dict[str, list] = {}
        for key, blob in rows:
            gid = key[len("group_members:"):]
            result[gid] = pickle.loads(blob)
        return result

    def set_group_members(self, gid: str, member_list: list):
        """缓存群成员列表，同时更新反向索引"""
        self.set(f"group_members:{gid}", member_list)
        for member in member_list:
            qq = str(member.get('user_id'))
            if qq:
                groups = self.get(f"user_groups:{qq}") or set()
                groups.add(gid)
                self.set(f"user_groups:{qq}", groups)

    def get_user_groups(self, user_id: str):
        """获取用户所在的所有群（反向索引）"""
        return self.get(f"user_groups:{user_id}") or set()

    def get_group_list(self):
        """获取缓存的群列表"""
        return self.get("group_list")

    def set_group_list(self, group_list: list):
        self.set("group_list", group_list)

    def get_stranger_info(self, user_id: str):
        return self.get(f"stranger_info:{user_id}")

    def set_stranger_info(self, user_id: str, info: dict):
        self.set(f"stranger_info:{user_id}", info)

    # ---- 生命周期 --------------------------------------------------------

    def close(self):
        """关闭数据库连接"""
        try:
            self._conn.close()
        except Exception:
            pass
