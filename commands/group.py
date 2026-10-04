"""
查询群信息 — 命令处理
======================
"""

from astrbot.api import logger
import astrbot.api.message_components as Comp
from cache import CacheManager
from formatters.group_info import build_group_info_nodes


async def handle_group_info(
    event,
    cache: CacheManager,
    group_id: str,
):
    """处理「查询群信息」命令，返回 (nodes_or_none, message)"""
    cached_members = cache.get_group_members(group_id)
    cached_info = cache.get_group_info(group_id)

    if cached_members is None or cached_info is None:
        # 缓存未命中，自动拉取
        client = event.bot
        try:
            group_info = await client.get_group_info(group_id=int(group_id))
            cache.set_group_info(group_id, group_info)
            member_list = await client.get_group_member_list(
                group_id=int(group_id)
            )
            cache.set_group_members(group_id, member_list)
        except Exception as e:
            logger.error(f"获取群组信息失败: {e}")
            return None, f"获取群组信息失败: {e}"
        return None, f"未缓存群 {group_id} 数据，已自动缓存，请再次查询"

    sender = event.get_sender_id()
    raw_nodes = build_group_info_nodes(
        group_id, cached_info, cached_members, sender
    )
    return Comp.Nodes(raw_nodes), None
