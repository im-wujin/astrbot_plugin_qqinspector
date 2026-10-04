"""
查询个人信息 — 命令处理
========================
"""

import time
from astrbot.api import logger
import astrbot.api.message_components as Comp
from cache import CacheManager
from formatters.user_info import (
    build_personal_text,
    build_member_text,
)
from formatters.sanitize import sanitize_text
from analyzers.overlap import OverlapAnalyzer


async def handle_user_info(
    event,
    cache: CacheManager,
    user_id: str,
    group_id: str,
):
    """处理「查询个人信息」命令，返回 (nodes_or_none, message)"""
    client = event.bot
    sender = event.get_sender_id()

    # ---- 解析群 ID 列表 ----
    if not group_id:
        # 未指定群时默认 all：从反向索引查找该用户所在的所有群
        cached_groups = cache.get_user_groups(user_id)
        if not cached_groups:
            return None, "缓存中未找到该用户所在的群，请先使用「刷新查询数据」"
        group_id_list = list(cached_groups)
    elif group_id == "all":
        cached_groups = cache.get_user_groups(user_id)
        if not cached_groups:
            return None, "缓存中未找到该用户所在的群，请先使用「刷新查询数据」"
        group_id_list = list(cached_groups)
    else:
        group_id_list = group_id.split(",")
        cached_group_list = cache.get_group_list()
        if cached_group_list is not None:
            bot_group_ids = {str(g['group_id']) for g in cached_group_list}
            group_id_list = [
                gid for gid in group_id_list if gid in bot_group_ids
            ]
        if not group_id_list:
            return None, "未加入指定的任何群，或尚未缓存群列表，请先使用「刷新查询数据」"
    # ---- 拉取用户基本信息 ----
    user_info = cache.get_stranger_info(user_id)
    if user_info is None:
        try:
            user_info = await client.get_stranger_info(user_id=user_id)
            cache.set_stranger_info(user_id, user_info)
        except Exception as e:
            return None, f"获取用户信息失败: {e}"

    nickname = user_info.get('nickname') or '未知'

    # ---- 基本信息最后更新时间 ----
    last_update_ts = cache.get_updated_at(f"stranger_info:{user_id}")
    if last_update_ts:
        last_update_str = time.strftime(
            '%Y-%m-%d %H:%M:%S', time.localtime(int(last_update_ts))
        )
    else:
        last_update_str = '未记录'

    personal_text = build_personal_text(user_info, user_id, last_update_str)

    # ---- 从缓存获取每个群的成员信息（批量查询） ----
    group_nodes = []
    need_refresh_gids = []

    members_map = cache.get_group_members_batch(group_id_list)
    for gid in group_id_list:
        cached_members = members_map.get(gid)
        if cached_members is None:
            need_refresh_gids.append(gid)
            continue

        cached_info = cache.get_group_info(gid)
        group_name = (
            cached_info.get('group_name') if cached_info else '未知群'
        )

        member_info = None
        for m in cached_members:
            if str(m.get('user_id', '')) == str(user_id):
                member_info = m
                break

        if member_info is None:
            continue

        group_text = build_member_text(
            member_info, group_name, gid, cached_info
        )
        group_nodes.append(Comp.Node(
            uin=sender,
            name="所在群聊信息",
            content=[Comp.Plain(group_text)]
        ))

    # ---- 处理未缓存的群 ----
    if need_refresh_gids:
        for gid in need_refresh_gids:
            try:
                g_info = await client.get_group_info(group_id=int(gid))
                cache.set_group_info(gid, g_info)
                g_members = await client.get_group_member_list(
                    group_id=int(gid)
                )
                cache.set_group_members(gid, g_members)
            except Exception as e:
                logger.warning(f"缓存群 {gid} 数据失败: {e}")
        return None, f"以下群尚未缓存，已自动缓存，请再次查询：{', '.join(need_refresh_gids)}"

    if not group_nodes:
        return None, "缓存中未找到该用户在指定群中的信息，请先使用「刷新查询数据」"

    # ---- 重合度分析 ----
    target_groups = cache.get_user_groups(user_id)
    if not target_groups:
        target_groups = {
            gid for gid in group_id_list
            if cache.get_group_members(gid) is not None
        }

    overlap_items = OverlapAnalyzer.analyze(
        cache, user_id, target_groups, top_n=10
    )

    overlap_nodes = []
    if overlap_items:
        for item in overlap_items:
            node_text = (
                f"---重合度分析---\n"
                f"排名: #{item.rank}\n"
                f"昵称: {sanitize_text(item.nickname)}\n"
                f"QQ: {item.qq}\n"
                f"共群: {item.common_groups}/{item.total_groups}\n"
                f"重合度: {item.ratio*100:.1f}%\n"
            )
            overlap_nodes.append(Comp.Node(
                uin=sender,
                name="群重合度信息",
                content=[Comp.Plain(node_text)]
            ))

    # ---- 构造合并转发：3 个固定大条目 ----
    # 大条目 1：个人基本信息
    entry_personal = Comp.Node(
        Comp.Node(
            uin=sender,
            name="个人基本信息",
            content=[Comp.Plain(personal_text)]
        ),
        uin=sender,
        name="个人基本信息",
    )

    # 大条目 2：所在群聊信息（直接包含群成员节点列表）
    entry_group = Comp.Node(
        uin=sender,
        name="所在群聊信息",
        content=group_nodes if group_nodes
        else [Comp.Plain("无群内信息")]
    )

    # 大条目 3：群重合度信息（直接包含重合度节点列表）
    overlap_content = overlap_nodes if overlap_nodes else [
        Comp.Plain("暂无充足数据进行重合度分析")
    ]
    entry_overlap = Comp.Node(
        uin=sender,
        name="群重合度信息",
        content=overlap_content
    )

    return Comp.Nodes([entry_personal, entry_group, entry_overlap]), None
