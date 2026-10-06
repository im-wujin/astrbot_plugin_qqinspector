"""
群信息格式化
=============

将缓存的群数据和成员列表格式化为合并转发的 Node 列表。
"""

import time
import astrbot.api.message_components as Comp
from .sanitize import sanitize_text

# 当前群主加入时间与建群时间的容差（秒）：超过则判定该群被转让过
_FOUNDER_TOLERANCE = 60


# GB2312 一级/二级汉字按拼音排序的区位码区间 -> 拼音首字母
# 用于在不引入第三方依赖的前提下计算汉字拼音首字母
_INITIAL_RANGES = (
    (0xB0A1, 0xB0C4, 'a'),
    (0xB0C5, 0xB2C0, 'b'),
    (0xB2C1, 0xB4ED, 'c'),
    (0xB4EE, 0xB6E9, 'd'),
    (0xB6EA, 0xB7A1, 'e'),
    (0xB7A2, 0xB8C0, 'f'),
    (0xB8C1, 0xB9FD, 'g'),
    (0xB9FE, 0xBBF6, 'h'),
    (0xBBF7, 0xBFA5, 'j'),
    (0xBFA6, 0xC0AB, 'k'),
    (0xC0AC, 0xC2E7, 'l'),
    (0xC2E8, 0xC4C2, 'm'),
    (0xC4C3, 0xC5B5, 'n'),
    (0xC5B6, 0xC5BD, 'o'),
    (0xC5BE, 0xC6D9, 'p'),
    (0xC6DA, 0xC8BA, 'q'),
    (0xC8BB, 0xC8F5, 'r'),
    (0xC8F6, 0xCBF9, 's'),
    (0xCBFA, 0xCDD9, 't'),
    (0xCDDA, 0xCEF3, 'w'),
    (0xCEF4, 0xD1B8, 'x'),
    (0xD1B9, 0xD4D0, 'y'),
    (0xD4D1, 0xD7F9, 'z'),
)


def _pinyin_initial(char: str) -> str:
    """返回单个字符的拼音首字母；非汉字返回其小写形式。"""
    if '\u4e00' <= char <= '\u9fff':
        try:
            gbk = char.encode('gbk')
        except UnicodeEncodeError:
            return char
        if len(gbk) == 2:
            code = (gbk[0] << 8) + gbk[1]
            for start, end, letter in _INITIAL_RANGES:
                if start <= code <= end:
                    return letter
    return char.lower()


def _title_sort_key(title: str) -> str:
    """构造用于按拼音首字母排序的键。"""
    return ''.join(_pinyin_initial(ch) for ch in title or '')


def _flat(text: str) -> str:
    """把可能含换行的显示文本压成单行，避免合并转发中出现空行。"""
    return ' '.join((text or '').split())


def build_group_info_nodes(
    group_id: str,
    group_info: dict,
    member_list: list,
    sender: str,
) -> list:
    """构造群信息合并转发节点，所有内容合并到单个 Node 中"""
    group_name = sanitize_text(group_info.get("group_name") or "") or "未知群组"
    member_count = group_info.get("member_count") or 0
    max_member_count = group_info.get("max_member_count") or 0
    group_remark = sanitize_text(group_info.get("group_remark") or "") or ""
    group_all_shut = (
        "否" if (group_info.get('group_all_shut') or 0) == 0 else "是"
    )

    role_priority = {"owner": 0, "admin": 1, "member": 2}
    member_list.sort(
        key=lambda m: role_priority.get(m.get("role", "member"), 3)
    )

    # ---- 统计信息 ----
    admin_count = 0
    earliest_join_time = None
    earliest_member = None
    second_earliest_join_time = None
    second_earliest_member = None
    latest_sent_time = None
    latest_member = None
    earliest_sent_time = None
    earliest_sent_member = None
    latest_join_time = None
    latest_join_member = None
    highest_level = None
    highest_level_member = None
    owner_member = None
    special_titles = []
    title_counts = {}

    for member in member_list:
        role = member.get("role") or "member"
        if role == "admin":
            admin_count += 1
        if role == "owner":
            owner_member = member

        join_time = member.get("join_time") or 0
        if join_time:
            if earliest_join_time is None or join_time < earliest_join_time:
                # 新最早加入者：原最早者顺延为「第二个加入」
                second_earliest_join_time = earliest_join_time
                second_earliest_member = earliest_member
                earliest_join_time = join_time
                earliest_member = member
            elif (
                second_earliest_join_time is None
                or join_time < second_earliest_join_time
            ):
                second_earliest_join_time = join_time
                second_earliest_member = member
            if latest_join_time is None or join_time > latest_join_time:
                latest_join_time = join_time
                latest_join_member = member

        last_sent_time = member.get("last_sent_time") or 0
        if last_sent_time and (
            latest_sent_time is None or last_sent_time > latest_sent_time
        ):
            latest_sent_time = last_sent_time
            latest_member = member
        if last_sent_time and (
            earliest_sent_time is None or last_sent_time < earliest_sent_time
        ):
            earliest_sent_time = last_sent_time
            earliest_sent_member = member

        level = member.get("level") or 0
        if isinstance(level, str):
            try:
                level = int(level)
            except Exception:
                level = 0
        if highest_level is None or level > highest_level:
            highest_level = level
            highest_level_member = member

        special_title = _flat(sanitize_text(member.get("title") or ""))
        if special_title:
            user_name = _flat(
                sanitize_text(member.get('card') or '')
                or sanitize_text(member.get('nickname') or '')
                or ''
            )
            uid = member.get('user_id') or ''
            special_titles.append(
                (
                    special_title,
                    f'{user_name}({uid})拥有"{special_title}"头衔',
                )
            )
            title_counts[special_title] = (
                title_counts.get(special_title, 0) + 1
            )

    def _fmt_name(m):
        if not isinstance(m, dict):
            return '未知'
        name = (
            sanitize_text(m.get('card') or '')
            or sanitize_text(m.get('nickname') or '')
            or '未知'
        )
        return _flat(name) or '未知'

    def _fmt_id(m):
        if not isinstance(m, dict):
            return ''
        return m.get('user_id') or ''

    # ---- 建群时间与「首任群主」（判定群主是否被转让）----
    create_time = int(group_info.get("group_create_time") or 0)
    # 建群时间：优先使用群信息里的真实建群时间，缺失时回退到最早加入时间
    build_time = create_time or earliest_join_time

    # 与建群时间最接近的成员视为「首任群主 / 建群人」
    founder_member = None
    if create_time:
        candidates = [
            m for m in member_list if (m.get("join_time") or 0)
        ]
        if candidates:
            closest = min(
                candidates,
                key=lambda m: abs(int(m.get("join_time")) - create_time),
            )
            if (
                abs(int(closest.get("join_time")) - create_time)
                <= _FOUNDER_TOLERANCE
            ):
                founder_member = closest

    owner_join_time = (
        int(owner_member.get("join_time") or 0)
        if isinstance(owner_member, dict) else 0
    )
    # 当前群主的加入时间与建群时间对不上 → 该群被转让过
    transferred = bool(
        create_time
        and owner_join_time
        and abs(owner_join_time - create_time) > _FOUNDER_TOLERANCE
    )

    transfer_text = ""
    if transferred:
        transfer_text += "---群转让信息---\n"
        if founder_member is not None:
            f_nickname = _flat(
                sanitize_text(founder_member.get('nickname') or '')
            )
            f_card = _flat(sanitize_text(founder_member.get('card') or ''))
            f_level = founder_member.get('level')
            f_qq_level = founder_member.get('qq_level')
            f_last_sent = founder_member.get('last_sent_time') or 0
            f_user_id = _fmt_id(founder_member)
            transfer_text += (
                f"首任群主: {f_nickname}\n"
            )
            # 权限：群主 / 管理员 / 群员
            _role_text = {
                'owner': '群主',
                'admin': '管理员',
                'member': '群员',
            }.get(founder_member.get('role'))
            if f_user_id:
                transfer_text += f"QQ号: {f_user_id}\n"
            if _role_text:
                transfer_text += f"权限: {_role_text}\n"
            if f_level:
                transfer_text += f"群等级: LV-{f_level}\n"
            if f_qq_level:
                transfer_text += f"QQ等级: {f_qq_level}\n"
            if f_card:
                transfer_text += f"群内名称: {f_card}\n"
            if f_last_sent:
                transfer_text += (
                    "最后发言: "
                    + time.strftime(
                        '%Y-%m-%d %H:%M:%S',
                        time.localtime(int(f_last_sent)),
                    )
                    + "\n"
                )
        else:
            transfer_text += "首任群主: 未知\n"
            transfer_text += "ps: 首任群主的判断 是根据加群时间判断的 若首任群主退群 则无法获取到首任群主信息\n"
    transfer_text = Comp.Node(
                    uin=sender,
                    name=f"群转让信息",
                    content=[Comp.Plain(transfer_text)]
                ) if transfer_text else None

    # 特殊头衔按头衔拼音首字母排序
    special_titles.sort(key=lambda item: _title_sort_key(item[0]))
    titles_content = (
        '\n'.join(text for _, text in special_titles)
        if special_titles else '无特殊头衔'
    )

    # ---- 头衔占比列表：按持有该头衔的人数从高到低排序 ----
    total_titled = sum(title_counts.values())
    ratio_items = sorted(
        title_counts.items(),
        key=lambda kv: (-kv[1], _title_sort_key(kv[0])),
    )
    ratio_content = (
        '\n'.join(
            f'{title} 占比 {count / total_titled * 100:.1f}% '
            f'({total_titled}/{count})'
            for title, count in ratio_items
        )
        if ratio_items and total_titled else '无特殊头衔'
    )

    # ---- 条目 1：群基本信息 ----
    group_text = (
        f"---{group_name}的群信息---\n"
        f"名称: {group_name}\n"
        f"群号: {group_id}\n"
        f"群主: {_fmt_name(owner_member)}({_fmt_id(owner_member)})\n"
        f"建群时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(build_time))) if build_time else '未知'}\n"
        f"最早加入: {_fmt_name(second_earliest_member)}({_fmt_id(second_earliest_member)}) "
        f"加入时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(second_earliest_join_time))) if second_earliest_join_time else '未知'}\n"
        f"最后加入: {_fmt_name(latest_join_member)}({_fmt_id(latest_join_member)}) "
        f"加入时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(latest_join_time))) if latest_join_time else '未知'}\n"
        f"最早发言: {_fmt_name(earliest_sent_member)}({_fmt_id(earliest_sent_member)}) "
        f"发言时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(earliest_sent_time))) if earliest_sent_time else '未知'}\n"
        f"最后发言: {_fmt_name(latest_member)}({_fmt_id(latest_member)}) "
        f"发言时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(latest_sent_time))) if latest_sent_time else '未知'}\n"
        f"最高等级: {_fmt_name(highest_level_member)}({_fmt_id(highest_level_member)}) LV-{highest_level}\n"
        f"总成员数量: {member_count}/{max_member_count}\n"
        f"管理员数量: {admin_count}\n"
        f"普通成员数量: {member_count - admin_count}\n"
        f"全员禁言状态: {group_all_shut}\n"
    )

    # ---- 条目 2：特殊头衔信息（列表 + 占比）----
    titles_text = (
        f"---特殊头衔列表---\n"
        f"{titles_content}\n"
    )
    ratio_text = (
        f"---特殊头衔占比---\n"
        f"{ratio_content}\n"
    )

    # ---- 条目 1 内容：群基本信息 +（可选）群转让信息 ----
    basic_content = [
        Comp.Node(
            uin=sender,
            name=f"群聊基本信息",
            content=[Comp.Plain(group_text)]
        ),
    ]
    if transfer_text:
        basic_content.append(transfer_text)

    return [
        Comp.Node(
            content=basic_content,
            uin=sender,
            name=f"群聊基本信息",
        ),
        Comp.Node(
            content=[
                Comp.Node(
                    uin=sender,
                    name="特殊头衔信息",
                    content=[Comp.Plain(titles_text)]
                ),
                Comp.Node(
                    uin=sender,
                    name="特殊头衔占比",
                    content=[Comp.Plain(ratio_text)]
                ),
            ],
            uin=sender,
            name="特殊头衔信息",
        ),
    ]
