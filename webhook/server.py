"""
Webhook HTTP 服务器管理
=======================

负责根据配置启动/停止 Webhook 服务器。
"""

import threading
from http.server import HTTPServer
from astrbot.api import logger
from .handler import _WebhookHandler


class WebhookServer:
    """Webhook 服务器生命周期管理器"""

    def __init__(self):
        self._http_server: HTTPServer | None = None
        self._http_thread: threading.Thread | None = None

    # ------------------------------------------------------------
    def start(self, config: dict, cache):
        """根据配置启动 HTTP 服务器（后台线程）"""
        remote_info = config.get('remote_info', {})
        port = remote_info.get('listen_port', 10086)
        api_keys = remote_info.get('api_keys', [])

        if not api_keys:
            logger.warning(
                "远程信息获取已启用，但未配置任何 API Key，Webhook 服务器不会启动"
            )
            return

        # 注入依赖到 handler 类变量
        _WebhookHandler.cache = cache
        _WebhookHandler.api_keys = api_keys

        try:
            self._http_server = HTTPServer(('0.0.0.0', port), _WebhookHandler)

            self._http_thread = threading.Thread(
                target=self._http_server.serve_forever,
                daemon=True,
                name="WebhookServer",
            )
            self._http_thread.start()
            logger.info(
                f"Webhook 服务器已启动，HTTP 监听 0.0.0.0:{port}，"
                f"已配置 {len(api_keys)} 个 API Key"
            )
        except OSError as e:
            logger.error(
                f"Webhook 服务器启动失败（端口 {port} 可能被占用）: {e}"
            )
            self._http_server = None
            self._http_thread = None

    # ------------------------------------------------------------
    def stop(self):
        """关闭服务器"""
        if self._http_server:
            logger.info("正在关闭 Webhook 服务器...")
            try:
                self._http_server.shutdown()
            except Exception:
                pass
            self._http_server = None
            self._http_thread = None
