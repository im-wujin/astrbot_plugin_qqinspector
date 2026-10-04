"""
刷新查询数据 — 命令处理
=========================
"""

from astrbot.api import logger
from cache import CacheManager


async def handle_refresh(client, cache: CacheManager):
    """拉取所有群及成员数据，写入缓存"""
    group_list = await client.get_group_list()
    cache.set_group_list(group_list)

    refreshed = 0
    for group in group_list:
        gid = str(group['group_id'])
        try:
            group_info = await client.get_group_info(group_id=int(gid))
            cache.set_group_info(gid, group_info)
            member_list = await client.get_group_member_list(
                group_id=int(gid)
            )
            cache.set_group_members(gid, member_list)
            refreshed += 1
        except Exception as e:
            logger.warning(f"刷新群 {gid} 数据失败: {e}")

    return refreshed, len(group_list)
