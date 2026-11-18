# -*- coding: utf-8 -*-
"""抓取各省份今日油价与历史调价数据。数据源：公开油价查询页。"""

import json
import re
import urllib.parse
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36"}
BASE = "https://youjia.abapi.cn"
OIL_SOURCE = BASE + "/p/beijing"
HISTORY_API = BASE + "/api/chart-data.php?province="

# 省份中文名 -> slug
PROVINCES = {
    "北京": "beijing", "上海": "shanghai", "天津": "tianjin", "重庆": "chongqing",
    "河北": "hebei", "山西": "shanxi", "辽宁": "liaoning", "吉林": "jilin", "黑龙江": "heilongjiang",
    "江苏": "jiangsu", "浙江": "zhejiang", "安徽": "anhui", "福建": "fujian", "江西": "jiangxi",
    "山东": "shandong", "河南": "henan", "湖北": "hubei", "湖南": "hunan", "广东": "guangdong",
    "广西": "guangxi", "海南": "hainan", "四川": "sichuan", "贵州": "guizhou", "云南": "yunnan",
    "西藏": "xizang", "陕西": "shanxi1", "甘肃": "gansu", "青海": "qinghai",
    "宁夏": "ningxia", "新疆": "xinjiang", "内蒙古": "neimenggu",
}

PRODUCTS = ["92号汽油", "95号汽油", "98号汽油", "0号柴油"]
API_KEYS = ["p92", "p95", "p98", "p0"]


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")


def fetch_oil(province="北京"):
    """返回 (update_time, {油品: 价格})，失败返回 (None, {})。"""
    slug = PROVINCES.get(province, "beijing")
    try:
        h = _get(f"{BASE}/p/{slug}")
    except Exception as e:
        print(f"FAIL 油价抓取({province}): {e}")
        return None, {}
    prices = {}
    for m in re.finditer(r'price-card-label">([^<]+)</div>\s*<div class="price-card-value">([^<]+)</div>', h):
        name, val = m.group(1).strip(), m.group(2).strip()
        if re.fullmatch(r"\d+\.\d+", val):
            prices[name] = val
    t = re.search(r"更新时间[：:]\s*([\d-]+\s[\d:]+)", h)
    return (t.group(1) if t else None), prices


def fetch_history(province):
    """返回 {dates:[], series:{油品:[...]}}，失败返回 None。"""
    try:
        url = HISTORY_API + urllib.parse.quote(province)
        d = json.loads(_get(url))
    except Exception as e:
        print(f"FAIL 历史数据({province}): {e}")
        return None
    dates = d.get("dates") or []
    if not dates:
        return None
    series = {}
    for name, key in zip(PRODUCTS, API_KEYS):
        series[name] = d.get(key) or []
    return {"dates": dates, "series": series}


def build_all(limit=None):
    """抓取全部（或前 limit 个）省份当日油价与历史，返回可内嵌的数据结构。"""
    result = {}
    provinces = list(PROVINCES.items())
    if limit:
        provinces = provinces[:limit]
    for name, slug in provinces:
        update, prices = fetch_oil(name)
        hist = fetch_history(name)
        result[name] = {"slug": slug, "prices": prices, "update": update, "history": hist}
        print(f"  油价 {name}: {len(prices)} 项, 历史 {len(hist['dates']) if hist else 0} 条")
    return result
