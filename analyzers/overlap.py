"""
重合度分析器
=============

计算目标用户与其他用户的群重合度（共群比例），
用于识别可能关联的账号。
"""

from dataclasses import dataclass, field
from typing import List
from cache import CacheManager


@dataclass
class OverlapItem:
    """单条重合度分析结果"""
    rank: int
    qq: str
    nickname: str
    common_groups: int
    total_groups: int
    ratio: float


class OverlapAnalyzer:
    """重合度分析器"""

    @staticmethod
    def analyze(
        cache: CacheManager,
        target_user_id: str,
        target_groups: set,
        top_n: int = 10,
    ) -> List[OverlapItem]:
        """
        分析目标用户在指定群集合中的重合度。

        :param cache: 缓存管理器
        :param target_user_id: 目标用户 QQ
        :param target_groups: 目标用户所在的群 ID 集合
        :param top_n: 返回前 N 条结果
        :returns: 按重合度降序排列的列表
        """
        if not target_groups:
            return []

        overlap_counter: dict[str, int] = {}
        nickname_map: dict[str, str] = {}

        # 批量查询所有群成员列表，单次 SQL
        members_map = cache.get_group_members_batch(list(target_groups))
        for gid in target_groups:
            members = members_map.get(gid)
            if members is None:
                continue
            for m in members:
                qq = str(m.get('user_id'))
                if not qq or qq == str(target_user_id):
                    continue
                overlap_counter[qq] = overlap_counter.get(qq, 0) + 1
                if qq not in nickname_map:
                    nickname_map[qq] = (
                        m.get('card') or m.get('nickname') or qq
                    )

        total_groups = len(target_groups)
        raw_list = [
            (qq, nickname_map[qq], cnt)
            for qq, cnt in overlap_counter.items()
        ]
        raw_list.sort(key=lambda x: x[2], reverse=True)

        results = []
        for i, (qq, name, cnt) in enumerate(raw_list[:top_n], 1):
            results.append(OverlapItem(
                rank=i,
                qq=qq,
                nickname=name,
                common_groups=cnt,
                total_groups=total_groups,
                ratio=cnt / total_groups,
            ))
        return results
