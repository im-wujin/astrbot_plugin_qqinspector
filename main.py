"""
QQInspector — QQ 群/用户数据检查插件
=====================================

AstrBot 插件，提供群信息和用户信息的查询、缓存及远程 Webhook 数据同步功能。
"""

import os
import sys

_plugin_dir = os.path.dirname(os.path.abspath(__file__))
if _plugin_dir not in sys.path:
    sys.path.insert(0, _plugin_dir)

# ---- 强制清除子模块缓存（应对 AstrBot 热重载只刷新 main.py 的问题） ----
_sub_module_prefixes = ('cache', 'webhook', 'commands', 'formatters', 'analyzers')
for mod_name in list(sys.modules.keys()):
    if mod_name.startswith(_sub_module_prefixes):
        del sys.modules[mod_name]
# -------------------------------------------------------------------

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from cache import CacheManager
from webhook import WebhookServer
from commands import handle_refresh, handle_group_info, handle_user_info


@register("QQInspector", "WuJin", "QQ群/用户数据检查", "1.2.5")
class QQInspector(Star):
    """QQ 群/用户数据检查插件"""

    def __init__(self, context: Context, config):
        super().__init__(context)
        self.config = config
        self.cache = CacheManager(self.name)

        # ---- 远程 Webhook 服务 ----
        self.webhook_server = WebhookServer()
        remote_info = config.get('remote_info', {})
        if remote_info.get('enabled', False):
            self.webhook_server.start(config, self.cache)

    # ================================================================
    # 命令：刷新查询数据
    # ================================================================
    @filter.command("刷新查询数据")
    async def refresh_data(self, event: AstrMessageEvent):
        """拉取所有群及成员数据，写入缓存"""
        yield event.plain_result("开始刷新所有群数据...")
        try:
            refreshed, total = await handle_refresh(event.bot, self.cache)
            yield event.plain_result(
                f"刷新完成！已缓存 {refreshed}/{total} 个群的数据"
            )
        except Exception as e:
            logger.error(f"刷新数据失败: {e}")
            yield event.plain_result(f"刷新数据失败: {e}")

    # ================================================================
    # 命令：查询群信息
    # ================================================================
    @filter.command("查询群聊信息", alias={'group_info', 'gi'})
    async def get_group_info(
        self, event: AstrMessageEvent, group_id: str = ""
    ):
        """
        获取指定群组的信息（优先使用缓存）
        使用方法: 查询群信息 [群组ID]
        如果不指定群组ID，则获取当前群组的信息
        """
        if event.get_group_id() and not group_id:
            group_id = event.get_group_id()
        if not group_id:
            yield event.plain_result("请在群聊中使用此命令或直接指定群号")
            return

        nodes, msg = await handle_group_info(event, self.cache, group_id)
        if msg:
            yield event.plain_result(msg)
            return
        yield event.chain_result([nodes])

    # ================================================================
    # 命令：查询个人信息
    # ================================================================
    @filter.command("查询个人信息", alias={'user_info', 'ui'})
    async def get_user_info(
        self,
        event: AstrMessageEvent,
        user_id: str = "",
        group_id: str = "",
    ):
        """
        获取指定用户的个人信息以及群内信息（优先使用缓存）
        使用方法: 查询用户信息 [用户ID] [群ID 用,分割 或 all]
        """
        if not user_id:
            user_id = event.get_sender_id()

        nodes, msg = await handle_user_info(
            event, self.cache, user_id, group_id
        )
        if msg:
            yield event.plain_result(msg)
            return
        yield event.chain_result([nodes])

    # ================================================================
    # 插件生命周期
    # ================================================================
    async def terminate(self):
        """插件卸载/停用时关闭 Webhook 服务器并清理缓存连接"""
        self.webhook_server.stop()
        self.cache.close()
