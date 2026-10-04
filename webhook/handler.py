"""
Webhook HTTP 请求处理器
========================

处理远程设备推送的群数据，包含身份验证、路由分发和数据合并逻辑。
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
from astrbot.api import logger


class _WebhookHandler(BaseHTTPRequestHandler):
    """接收远程设备推送的 HTTP 回调处理器"""

    cache = None       # 由 WebhookServer.start 注入 CacheManager 实例
    api_keys = []      # 由 WebhookServer.start 注入有效 API Key 列表

    # ------------------------------------------------------------
    def do_POST(self):
        path = urlparse(self.path).path

        content_length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(content_length) if content_length > 0 else b'{}'

        if not self._check_auth():
            return self._send_json(401, {"error": "未授权，请提供有效的 API Key"})

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return self._send_json(400, {"error": "请求体不是合法的 JSON"})

        if path == '/updata/group':
            self._handle_group_update(data)
        elif path == '/updata/user':
            self._handle_user_update(data)
        else:
            self._send_json(404, {"error": f"未知路径: {path}"})

    # ------------------------------------------------------------
    def _check_auth(self) -> bool:
        api_key = (
            self.headers.get('X-API-Key', '')
            or self.headers.get('Authorization', '').replace('Bearer ', '')
        )
        if not api_key:
            return False
        return any(
            entry.get('key') == api_key
            for entry in self.__class__.api_keys
        )

    # ------------------------------------------------------------
    def _handle_group_update(self, data: dict):
        cache = self.__class__.cache
        try:
            for gid_str, group_data in data.items():
                if not isinstance(group_data, dict):
                    continue
                self._merge_group_info(cache, gid_str, group_data)
                raw_members = group_data.get("member_list")
                if raw_members and isinstance(raw_members, list):
                    self._merge_member_list(cache, gid_str, raw_members)
            self._send_json(200, {"status": "ok"})
            logger.info(
                f"Webhook: 成功处理 {len(data)} 个群的数据更新"
            )
        except Exception as e:
            logger.error(f"Webhook 处理群数据失败: {e}")
            self._send_json(500, {"error": f"服务器内部错误: {e}"})

    # ------------------------------------------------------------
    @staticmethod
    def _merge_group_info(cache, gid: str, group_data: dict):
        existing = cache.get_group_info(gid) or {}
        for key in ('group_name', 'member_count'):
            if key in group_data:
                existing[key] = group_data[key]
        cache.set_group_info(gid, existing)

    # ------------------------------------------------------------
    @staticmethod
    def _merge_member_list(cache, gid: str, raw_members: list):
        existing = cache.get_group_members(gid) or []
        existing_map: dict[str, dict] = {}
        for m in existing:
            uid = str(m.get('user_id', ''))
            if uid:
                existing_map[uid] = m

        saved_uids = []
        for raw in raw_members:
            uid = str(raw.get('user_id', ''))
            if not uid:
                continue
            if uid in existing_map:
                existing_map[uid].update(raw)
            else:
                existing.append(raw)
                existing_map[uid] = raw
            saved_uids.append(uid)

            # ---- 同步更新/创建个人信息（stranger_info） ----
            _WebhookHandler._merge_stranger_info(cache, uid, raw)

            # ---- 确保反向索引包含此群 ----
            groups = cache.get(f"user_groups:{uid}") or set()
            if gid not in groups:
                groups.add(gid)
                cache.set(f"user_groups:{uid}", groups)

        # 使用 cache.set_group_members 确保反向索引和成员列表同步
        cache.set_group_members(gid, existing)
        logger.info(
            f"Webhook: 群 {gid} 成员列表已保存, "
            f"共 {len(existing)} 人, 本次处理 {len(saved_uids)} 人: {saved_uids}"
        )

    # ------------------------------------------------------------
    @staticmethod
    def _merge_stranger_info(cache, uid: str, member_data: dict):
        """
        用 API 上传的 name 字段覆盖个人信息。
        name 为用户跨群不变的真实名称，每次上传都刷新，确保不被 API 回填覆盖。
        """
        name = member_data.get('name')
        if not name:
            return  # 没有 name 字段，不处理

        cache.set(f"stranger_info:{uid}", {
            'user_id': uid,
            'nickname': name,
        })

    # ------------------------------------------------------------
    def _handle_user_update(self, data: dict):
        """
        处理 /updata/user 上传的个人信息。
        仅覆盖上传数据中存在的字段，不丢失已有数据。
        支持批量：{"user_id": {...fields...}} 或单条：{...fields...}
        """
        cache = self.__class__.cache
        try:
            if 'user_id' in data:
                # 单条格式
                items = [data]
            else:
                # 批量格式 {user_id: {...}, ...}
                items = [
                    {"user_id": uid, **fields}
                    for uid, fields in data.items()
                    if isinstance(fields, dict)
                ]

            updated = 0
            for item in items:
                uid = str(item.get('user_id', ''))
                if not uid:
                    continue
                existing = cache.get(f"stranger_info:{uid}") or {}
                changed = False
                for key, value in item.items():
                    if key == 'user_id':
                        continue
                    if existing.get(key) != value:
                        existing[key] = value
                        changed = True
                if changed:
                    cache.set(f"stranger_info:{uid}", existing)
                    updated += 1

            self._send_json(200, {"status": "ok", "updated": updated})
            logger.info(
                f"Webhook: 个人信息更新完成, 更新 {updated}/{len(items)} 条"
            )
        except Exception as e:
            logger.error(f"Webhook 处理个人信息失败: {e}")
            self._send_json(500, {"error": f"服务器内部错误: {e}"})

    # ------------------------------------------------------------
    def _send_json(self, status_code: int, body: dict):
        payload = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        logger.info(f"[Webhook] {format % args}")
