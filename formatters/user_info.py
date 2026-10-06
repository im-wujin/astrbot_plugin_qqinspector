"""
用户信息格式化
===============

将用户基本信息和群内成员信息格式化为文本。
"""

import time
import astrbot.api.message_components as Comp
from .sanitize import sanitize_text


def _f(user_info: dict, *keys,) -> str:
    """按 keys 顺序取第一个非空字符串值；命中则清洗
    """
    for key in keys:
        v = user_info.get(key, None)
        if isinstance(v, str) and v:
            cleaned = sanitize_text(v)
            return cleaned if cleaned else None
        if isinstance(v, (int, float)) and v:
            return str(v)
    return None


def build_personal_text(user_info: dict, user_id: str,
                        last_update_str: str) -> str:
    """构造用户个人基本信息的文本"""
    # 清洗用户可控字段，防止合并转发因特殊字符打不开
    long_nick = _f(user_info, 'longNick', 'long_nick')
    country = _f(user_info, 'country')
    province = _f(user_info, 'province')
    city = _f(user_info, 'city')
    blood_type = _f(user_info, 'kBloodType')
    home_town = _f(user_info, 'homeTown')
    career = _f(user_info, 'makeFriendCareer')
    pos = _f(user_info, 'pos')
    college = _f(user_info, 'college')
    address = _f(user_info, 'address')
    interest = _f(user_info, 'interest')
    e_mail = _f(user_info, 'eMail')
    phone_num = _f(user_info, 'phoneNum')
    status = _f(user_info, 'status')
    nickname = _f(user_info, 'nickname') or user_id
    qid = user_info.get('qid')
    qq_level = user_info.get('qq_level')
    uid = user_info.get('user_id') or user_id
    login_days = user_info.get('login_days')
    reg_time = user_info.get('regTime') or user_info.get('reg_time')
    sex = user_info.get('sex')
    age = user_info.get('age')
    birthday_year = user_info.get('birthday_year')
    birthday_month = user_info.get('birthday_month')
    birthday_day = user_info.get('birthday_day')
    constellation = user_info.get('constellation')
    sheng_xiao = user_info.get('shengXiao')
    post_code = user_info.get('postCode')

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
                else ""
            )
        )
        if user_info.get('vip_level') and user_info.get("richTime")
        else ""
    )

    labels = user_info.get('labels') or []
    cleaned_labels = [
        sanitize_text(str(x))
        for x in labels
        if x is not None and sanitize_text(str(x))
    ]
    labels_text = ', '.join(cleaned_labels) if cleaned_labels else '无'

    reg_time_text = (
        time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(reg_time)))
        if reg_time else None
    )
    constellation_text = (
        [None, '白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '摩羯座', '水瓶座', '双鱼座'][int(constellation or 0)]
        if str(constellation or '0').isdigit() and 0 <= int(constellation or 0) <= 12
        else None
    )
    sheng_xiao_text = (
        [None, '鼠', '牛', '虎', '兔', '龙', '蛇', '马', '羊', '猴', '鸡', '狗', '猪'][int(sheng_xiao or 0)]
        if str(sheng_xiao or '0').isdigit() and 0 <= int(sheng_xiao or 0) <= 12
        else None
    )

    # 位置：只展示获取到的部分；全部缺失则不展示（连换行也不要）
    location_parts = []
    if country:
        location_parts.append(f"{country}国")
    if province:
        location_parts.append(f"{province}省")
    if city:
        location_parts.append(f"{city}市")
    location_text = '-'.join(location_parts)

    # 生日：只展示获取到的部分；全部缺失则不展示
    birthday_parts = [
        str(p) for p in (birthday_year, birthday_month, birthday_day) if p
    ]
    birthday_text = '-'.join(birthday_parts)

    return_text = f"---{nickname}的基本信息---\n"
    return_text += f"昵称: {nickname}\n"
    return_text += f"QQ号: {uid}"
    return_text += f"[{qid}]\n" if qid else "\n"
    return_text += f"QQ等级: {qq_level}\n" if qq_level else ""
    return_text += f"个性签名: {long_nick}\n" if long_nick else ""
    return_text += f"{vip_time}\n" if vip_time else ""
    return_text += f"登录天数: {login_days}\n" if login_days is not None else ""
    return_text += f"注册时间: {reg_time_text}\n" if reg_time_text else ""
    return_text += f"性别: {'男' if sex == 'male' else '女'}\n" if sex in ('male', 'female') else ""
    return_text += f"年龄: {age}\n" if age else ""
    return_text += f"{location_text}\n" if location_text else ""
    return_text += f"生日: {birthday_text}\n" if birthday_text else ""
    return_text += f"星座: {constellation_text}\n" if constellation_text else ""
    return_text += f"生肖: {sheng_xiao_text}\n" if sheng_xiao_text else ""
    return_text += f"血型: {blood_type}\n" if blood_type else ""
    return_text += f"家乡: {home_town}\n" if home_town else ""
    return_text += f"职业: {career}\n" if career else ""
    return_text += f"位置: {pos}\n" if pos else ""
    return_text += f"大学: {college}\n" if college else ""
    return_text += f"邮编: {post_code}\n" if post_code else ""
    return_text += f"地址: {address}\n" if address else ""
    return_text += f"兴趣: {interest}\n" if interest else ""
    return_text += f"标签: {labels_text}\n" if labels_text else ""
    return_text += f"邮箱: {e_mail}\n" if e_mail else ""
    return_text += f"手机号: {phone_num}\n" if phone_num else ""
    return_text += f"状态: {status}\n" if status else ""
    return_text += f"数据库最后更新时间: {last_update_str}\n"
    return return_text


def build_member_text(member_info: dict, group_name: str,
                      gid: str, cached_info: dict) -> str:
    """构造单个群内的成员信息文本"""
    group_name = sanitize_text(group_name) if group_name else ''
    group_name = group_name if group_name else '未知群'
    nickname = sanitize_text(member_info.get('nickname') or '') or member_info.get('user_id')
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
        f" 等级: LV-{member_info.get('level') or None}\n"
        f" 加入时间: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(member_info.get('join_time') or 0))) if member_info.get('join_time') else None}\n"
        f" 最后发言: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(member_info.get('last_sent_time') or 0))) if member_info.get('last_sent_time') else None}\n"
        f" 权限: {'成员' if member_info.get('role') == 'member' else '管理员' if member_info.get('role') == 'admin' else '群主' if member_info.get('role') == 'owner' else None}\n"
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
        f"昵称: {sanitize_text(name) or None}\n"
        f"QQ: {qq}\n"
        f"共群: {cnt}/{total}\n"
        f"重合度: {ratio*100:.1f}%\n"
    )
