"""
用户信息格式化
===============

将用户基本信息和群内成员信息格式化为文本。
"""

import time
import astrbot.api.message_components as Comp
from .sanitize import sanitize_text


def _f(user_info: dict, *keys, default: str = '未知') -> str:
    """按 keys 顺序取第一个非空字符串值；命中则清洗，否则返回默认值。

    清洗用于规避合并转发 Plain 组件因 Bidi/代理项/控制字符/异常转义导致
    QQ 客户端「消息打不开」的问题。若清洗后为空（原始值全部由特殊字符组成），
    回退到 default，避免出现空白字段。
    """
    for key in keys:
        v = user_info.get(key)
        if isinstance(v, str) and v:
            cleaned = sanitize_text(v)
            return cleaned if cleaned else default
        if isinstance(v, (int, float)) and v:
            return str(v)
    return default


def build_personal_text(user_info: dict, user_id: str,
                        last_update_str: str) -> str:
    """构造用户个人基本信息的文本"""
    nickname = _f(user_info, 'nickname', default='未知')

    vip_time = (
        (
            f"{'年费' if user_info.get('is_years_vip') else ''}"
            f"VIP_{user_info.get('vip_level') or False}到期时间: "
            + (
                time.strftime(
                    '%Y-%m-%d %H:%M:%S',
                    time.localtime(
                        int(user_info.get("richTime") or "")
                        + (
                            365 * 24 * 60 * 60
                            if user_info.get('is_years_vip')
                            and user_info.get("richTime")
                            else 0
                        )
                    ),
                )
                if user_info.get("richTime")
                else '未知'
            )
        )
        if user_info.get('vip_level')
        else ""
    )

    # 清洗用户可控字段，防止合并转发因特殊字符打不开
    _SPECIAL = '_特殊字符'
    long_nick = _f(user_info, 'longNick', 'long_nick', default=_SPECIAL)
    country = _f(user_info, 'country', default=_SPECIAL)
    province = _f(user_info, 'province', default=_SPECIAL)
    city = _f(user_info, 'city', default=_SPECIAL)
    blood_type = _f(user_info, 'kBloodType', default=_SPECIAL)
    home_town = _f(user_info, 'homeTown', default=_SPECIAL)
    career = _f(user_info, 'makeFriendCareer', default=_SPECIAL)
    pos = _f(user_info, 'pos', default=_SPECIAL)
    college = _f(user_info, 'college', default=_SPECIAL)
    address = _f(user_info, 'address', default=_SPECIAL)
    interest = _f(user_info, 'interest', default=_SPECIAL)
    e_mail = _f(user_info, 'eMail', default=_SPECIAL)
    phone_num = _f(user_info, 'phoneNum', default=_SPECIAL)
    status = _f(user_info, 'status', default=_SPECIAL)

    labels = user_info.get('labels') or []
    cleaned_labels = [
        sanitize_text(str(x))
        for x in labels
        if x is not None and sanitize_text(str(x))
    ]
    labels_text = ', '.join(cleaned_labels) if cleaned_labels else '无'

    return (
        f"---{nickname}的基本信息---\n"
        f"昵称: {nickname}\n"
        f"QQ号: {user_info.get('user_id') or user_id}"
        f"[{user_info.get('qid') or '未知QID'}]\n"
        f"QQ等级: {user_info.get('qq_level') or '未知'}\n"
        f"个性签名: {long_nick}\n"
        f"{vip_time}\n"
        f"登录天数: {user_info.get('login_days') if user_info.get('login_days') is not None else '未知'}\n"
        f"注册时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(user_info.get('regTime') or user_info.get('reg_time') or 0))) if (user_info.get('regTime') or user_info.get('reg_time')) else '未知'}\n"
        f"性别: {'男' if user_info.get('sex') == 'male' else '女' if user_info.get('sex') == 'female' else '沃尔玛购物袋(未知)'}\n"
        f"年龄: {user_info.get('age') or '未知'}\n"
        f"{country}国-{province}省-{city}市\n"
        f"生日: {user_info.get('birthday_year') or '未知'}-{user_info.get('birthday_month') or '未知'}-{user_info.get('birthday_day') or '未知'}\n"
        f"星座: {['未知', '白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座'][int(user_info.get('constellation') or 0)] if str(user_info.get('constellation') or '0').isdigit() and 0 <= int(user_info.get('constellation') or 0) <= 12 else '星座信息异常'}\n"
        f"生肖: {['未知', '鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'][int(user_info.get('shengXiao') or 0)] if str(user_info.get('shengXiao') or '0').isdigit() and 0 <= int(user_info.get('shengXiao') or 0) <= 12 else '未知'}\n"
        f"血型: {blood_type}\n"
        f"家乡: {home_town}\n"
        f"职业: {career}\n"
        f"位置: {pos}\n"
        f"大学: {college}\n"
        f"邮编: {user_info.get('postCode') or '未知'}\n"
        f"地址: {address}\n"
        f"兴趣: {interest}\n"
        f"标签: {labels_text}\n"
        f"邮箱: {e_mail}\n"
        f"手机号: {phone_num}\n"
        f"状态: {status}\n"
        f"数据库最后更新时间: {last_update_str}\n"
    )


def build_member_text(member_info: dict, group_name: str,
                      gid: str, cached_info: dict) -> str:
    """构造单个群内的成员信息文本"""
    group_name = sanitize_text(group_name) if group_name else ''
    group_name = group_name if group_name else '未知群'
    nickname = sanitize_text(member_info.get('nickname') or '') or '未知'
    card = sanitize_text(member_info.get('card') or '') or nickname
    title = sanitize_text(member_info.get('title') or '') or '无'
    title_expire_time = member_info.get('title_expire_time') or -1
    if title_expire_time == 0:
        title_expire_time = "(永久)"
    elif title_expire_time == -1:
        title_expire_time = ""
    else:
        title_expire_time = (
            f"({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(title_expire_time)))})"
        )

    shut_up_time = member_info.get('shut_up_time') or 0
    if cached_info and cached_info.get('group_all_shut'):
        shut_up_time = "全员禁言"
    elif shut_up_time == 0:
        shut_up_time = "未禁言"
    else:
        shut_up_time = (
            f"{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(shut_up_time)))} 结束禁言"
        )

    return (
        f"---{nickname} 在{group_name}({gid})中的信息---\n"
        f" 群内名称: {card}\n"
        f" 等级: LV-{member_info.get('level') or '未知'}\n"
        f" 加入时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(member_info.get('join_time') or 0))) if member_info.get('join_time') else '未知'}\n"
        f" 最后发言: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(member_info.get('last_sent_time') or 0))) if member_info.get('last_sent_time') else '未知'}\n"
        f" 权限: {'成员' if member_info.get('role') == 'member' else '管理员' if member_info.get('role') == 'admin' else '群主' if member_info.get('role') == 'owner' else '未知'}\n"
        f" 禁言状态: {shut_up_time}\n"
        f" 特殊头衔: {title}{title_expire_time}\n"
    )


def build_overlap_text(overlap_list: list, idx: int,
                        qq: str, name: str,
                        cnt: int, total: int) -> str:
    """构造单条重合度分析文本"""
    ratio = cnt / total if total else 0
    return (
        f"---重合度分析---\n"
        f"排名: #{idx}\n"
        f"昵称: {sanitize_text(name) or '未知'}\n"
        f"QQ: {qq}\n"
        f"共群: {cnt}/{total}\n"
        f"重合度: {ratio*100:.1f}%\n"
    )
