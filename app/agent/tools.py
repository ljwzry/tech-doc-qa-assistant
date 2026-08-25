from langchain_core.tools import tool
from app.rag.hybrid_retriever import hybrid_search
from ddgs import DDGS
import contextvars
import logging

logger = logging.getLogger(__name__)

# 当前项目上下文，使用 contextvars 保证线程/协程安全
_current_project = contextvars.ContextVar("current_project", default=None)

def set_current_project(project: str):
    """设置当前检索的项目范围"""
    _current_project.set(project)

@tool
def rag_search(query: str, top_k: int = 5) -> str:
    """从本地技术文档知识库中检索信息。当用户询问项目相关、技术文档相关的问题时使用此工具。
    Args:
        query: 搜索查询
        top_k: 返回结果数量
    """
    project = _current_project.get()
    results = hybrid_search(query, top_k=top_k, project=project)
    if not results:
        if project:
            return f"未在项目 '{project}' 的知识库中找到相关文档。"
        return "未在知识库中找到相关文档。"
    
    # 按文档分组，合并同一文档的多个chunk
    docs_by_source = {}
    for r in results:
        src = r["metadata"].get("source_file", "未知来源")
        proj = r["metadata"].get("project", "")
        key = f"{proj}_{src}" if proj else src
        if key not in docs_by_source:
            docs_by_source[key] = {"project": proj, "source": src, "texts": []}
        docs_by_source[key]["texts"].append(r["text"])
    
    parts = []
    max_chars_per_doc = 2000  # 每个文档最多返回2000字符
    max_total_chars = 5000    # 总共最多返回5000字符
    
    total_chars = 0
    for i, (key, data) in enumerate(docs_by_source.items(), 1):
        if total_chars >= max_total_chars:
            parts.append(f"... (还有更多文档未显示，请尝试更具体的搜索)")
            break
            
        proj = data["project"]
        src = data["source"]
        full_text = "\n".join(data["texts"])
        
        # 限制每个文档的内容长度
        if len(full_text) > max_chars_per_doc:
            full_text = full_text[:max_chars_per_doc] + "\n... (内容已截断，文档较长)"
        
        if proj:
            doc_part = f"[文档{i}] 项目: {proj} | 来源: {src}\n{full_text}"
        else:
            doc_part = f"[文档{i}] 来源: {src}\n{full_text}"
        
        parts.append(doc_part)
        total_chars += len(doc_part)
    
    return "\n\n".join(parts)

@tool
def web_search(query: str, max_results: int = 3) -> str:
    """在互联网上搜索技术资料、新闻、天气等信息。当知识库中没有相关信息或需要实时数据时使用此工具。
    Args:
        query: 搜索关键词
        max_results: 最大返回结果数（实际最少返回3条以保证相关性）
    """
    # 天气查询：用专门的天气API，不走通用搜索引擎
    weather_result = _try_weather_search(query)
    if weather_result:
        logger.info(f"[web_search] 命中天气API (query={query!r})")
        return weather_result
    
    # 保证最少3条结果，避免单条结果不相关
    actual_max = max(max_results, 3)
    
    # 搜索顺序：Bing（国内稳定）→ DuckDuckGo（cn-zh 区域）→ 百度（兜底）
    searchers = [
        ("Bing", _search_bing),
        ("DuckDuckGo", lambda q, m: _search_ddg(q, m, region="cn-zh")),
        ("百度", _search_baidu),
    ]
    
    for name, search_fn in searchers:
        try:
            results = search_fn(query, actual_max)
            if results:
                logger.info(f"[web_search] {name} 命中 {len(results)} 条 (query={query!r})")
                return _format_results(results)
            logger.debug(f"[web_search] {name} 无结果，尝试下一个 (query={query!r})")
        except Exception as e:
            logger.debug(f"[web_search] {name} 失败: {type(e).__name__} (query={query!r})")

    return "未找到相关网络搜索结果。"


def _try_weather_search(query: str) -> str | None:
    """天气查询专用路径：检测关键词后调用实时天气API"""
    weather_keywords = ["天气", "温度", "气温", "降水", "下雨", "下雪", "天气预报", "风力", "风向", "湿度"]
    if not any(kw in query for kw in weather_keywords):
        return None
    
    import re
    
    # 第一步：优先检查查询中是否包含已知城市（避免正则误匹配"会不会""能不#"等词）
    known_cities = [
        "北京", "上海", "广州", "深圳", "杭州", "南京", "成都", "重庆", "西安", "武汉",
        "苏州", "天津", "长沙", "郑州", "青岛", "厦门", "福州", "哈尔滨", "沈阳", "大连",
        "济南", "合肥", "昆明", "贵阳", "南宁", "海口", "兰州", "太原", "石家庄", "南昌",
        "无锡", "宁波", "佛山", "东莞", "珠海", "中山", "烟台", "潍坊", "泉州", "徐州",
        "长春", "呼和浩特", "乌鲁木齐", "拉萨", "银川", "西宁", "南宁",
    ]
    city = None
    for kw in sorted(known_cities, key=len, reverse=True):  # 优先匹配长名字（如"石家庄"）
        if kw in query:
            city = kw
            break
    
    # 第二步：如果没匹配到已知城市，用正则尝试提取
    if not city:
        city_patterns = [
            r"(.{2,10}?(?:市|地区|省))(?:今天|明天|后天|最近|几天|一周|目前|现在|当前|实时)?(?:天气|温度|气温|降水|下雨|下雪|风力|风向|湿度)",
            r"(?:今天|明天|后天|最近|几天|一周|目前|现在|当前|实时)(.{2,10}?(?:市|地区|省))的?(?:天气|温度|气温)",
            r"([\u4e00-\u9fa5]{2,4})(?:今天|明天|后天|现在|当前|的)?天气",
        ]
        for pat in city_patterns:
            m = re.search(pat, query)
            if m:
                candidate = m.group(1).strip()
                # 排除明显不是城市的词
                blacklist = ["今天", "明天", "后天", "最近", "现在", "当前", "实时", "会不会", "能不#", "多少", "怎么样", "怎么", "什么", "为什么"]
                if not any(b in candidate for b in blacklist):
                    city = candidate
                    break
    
    if not city:
        city = "北京"  # 兜底：默认北京
    
    # 去掉"市省地区"后缀
    city_clean = city.rstrip("市省地区")
    
    # wttr.in 的中文城市名匹配不精确，先用拼音映射（避免"西安"匹配到陕西小村）
    city_pinyin = {
        "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou", "深圳": "Shenzhen",
        "杭州": "Hangzhou", "南京": "Nanjing", "成都": "Chengdu", "重庆": "Chongqing",
        "西安": "Xian", "武汉": "Wuhan", "苏州": "Suzhou", "天津": "Tianjin",
        "长沙": "Changsha", "郑州": "Zhengzhou", "青岛": "Qingdao", "厦门": "Xiamen",
        "福州": "Fuzhou", "哈尔滨": "Harbin", "沈阳": "Shenyang", "大连": "Dalian",
        "济南": "Jinan", "合肥": "Hefei", "昆明": "Kunming", "贵阳": "Guiyang",
        "南宁": "Nanning", "海口": "Haikou", "兰州": "Lanzhou", "太原": "Taiyuan",
        "石家庄": "Shijiazhuang", "南昌": "Nanchang", "无锡": "Wuxi", "宁波": "Ningbo",
        "佛山": "Foshan", "东莞": "Dongguan", "珠海": "Zhuhai", "中山": "Zhongshan",
        "烟台": "Yantai", "潍坊": "Weifang", "泉州": "Quanzhou", "徐州": "Xuzhou",
        "长春": "Changchun", "呼和浩特": "Hohhot", "乌鲁木齐": "Urumqi",
        "拉萨": "Lhasa", "银川": "Yinchuan", "西宁": "Xining",
    }
    wttr_city = city_pinyin.get(city_clean, city_clean)
    
    try:
        return _get_weather_wttr(wttr_city)
    except Exception as e:
        logger.warning(f"[weather] wttr.in失败，尝试Open-Meteo: {e}")
        try:
            return _get_weather_openmeteo(city_clean)
        except Exception as e2:
            logger.warning(f"[weather] Open-Meteo也失败: {e2}")
            return None


def _get_weather_wttr(city: str) -> str:
    """通过 wttr.in 获取中文天气（免费、无需key）"""
    import requests
    headers = {
        "User-Agent": "curl/8.0 (Windows NT 10.0; zh-CN)",
        "Accept-Language": "zh-CN,zh;q=0.9"
    }
    # format=j1 返回完整JSON结构
    r = requests.get(f"https://wttr.in/{city}?format=j1&lang=zh",
                     headers=headers, timeout=15)
    data = r.json()
    
    cur = data["current_condition"][0]
    area = data.get("nearest_area", [{}])[0]
    area_name = area.get("areaName", [{}])[0].get("value", city)
    region = area.get("region", [{}])[0].get("value", "")
    country = area.get("country", [{}])[0].get("value", "")
    
    temp_c = cur.get("temp_C", "?")
    feels_c = cur.get("FeelsLikeC", "?")
    humidity = cur.get("humidity", "?")
    wind_kmh = cur.get("windspeedKmph", "?")
    wind_dir = cur.get("winddir16Point", "?")
    # 优先取中文天气描述，回退英文
    weather_desc = cur.get("lang_zh", [{}])[0].get("value") if cur.get("lang_zh") else cur.get("weatherDesc", [{}])[0].get("value", "?")
    uv = cur.get("uvIndex", "?")
    vis_km = cur.get("visibility", "?")
    cloud = cur.get("cloudcover", "?")
    
    # 今日预报
    today = data.get("weather", [{}])[0]
    max_c = today.get("maxtempC", "?")
    min_c = today.get("mintempC", "?")
    sun_rise = today.get("astronomy", [{}])[0].get("sunrise", "?")
    sun_set = today.get("astronomy", [{}])[0].get("sunset", "?")
    hourly_today = today.get("hourly", [])
    rain_chance_max = 0
    for h in hourly_today:
        rc = int(h.get("chanceofrain", 0))
        if rc > rain_chance_max:
            rain_chance_max = rc
    
    # 未来2天预报
    lines = [
        f"【实时天气 - {area_name}" + (f", {region}" if region else "") + (f", {country}" if country else "") + "】",
        f"当前温度: {temp_c}°C (体感 {feels_c}°C)",
        f"天气状况: {weather_desc}",
        f"今日温度范围: {min_c}°C ~ {max_c}°C",
        f"湿度: {humidity}% | 云量: {cloud}% | 能见度: {vis_km} km | 紫外线指数: {uv}",
        f"风向风力: {wind_dir} {wind_kmh} km/h",
        f"今日降水概率: 最高 {rain_chance_max}%",
        f"日出日落: {sun_rise} ~ {sun_set}",
        "",
        "【未来2天预报】",
    ]
    for i, day in enumerate(data.get("weather", [])[1:3], 1):
        date = day.get("date", "?")
        mx = day.get("maxtempC", "?")
        mn = day.get("mintempC", "?")
        astro = day.get("astronomy", [{}])[0]
        desc_list = []
        rain_max_day = 0
        for h in day.get("hourly", []):
            rc = int(h.get("chanceofrain", 0))
            if rc > rain_max_day:
                rain_max_day = rc
        # 取中午的天气描述
        mid = day.get("hourly", [{}])[4] if len(day.get("hourly", [])) >= 5 else (day.get("hourly", [{}])[-1] if day.get("hourly") else {})
        day_desc = mid.get("lang_zh", [{}])[0].get("value") if mid.get("lang_zh") else mid.get("weatherDesc", [{}])[0].get("value", "")
        lines.append(f"第{i}天 ({date}): {mn}°C~{mx}°C | {day_desc} | 降水概率{rain_max_day}%")
    
    return "\n".join(lines)


def _get_weather_openmeteo(city: str) -> str:
    """Open-Meteo 兜底：通过中文拼音匹配城市"""
    import requests
    # 中文城市 -> 拼音映射（常见城市，避免匹配到国外同名城市）
    city_pinyin = {
        "北京": "Beijing", "上海": "Shanghai", "广州": "Guangzhou", "深圳": "Shenzhen",
        "杭州": "Hangzhou", "南京": "Nanjing", "成都": "Chengdu", "重庆": "Chongqing",
        "西安": "Xi'an", "武汉": "Wuhan", "苏州": "Suzhou", "天津": "Tianjin",
        "长沙": "Changsha", "郑州": "Zhengzhou", "青岛": "Qingdao", "厦门": "Xiamen",
        "福州": "Fuzhou", "哈尔滨": "Harbin", "沈阳": "Shenyang", "大连": "Dalian",
        "济南": "Jinan", "合肥": "Hefei", "昆明": "Kunming", "贵阳": "Guiyang",
        "南宁": "Nanning", "海口": "Haikou", "兰州": "Lanzhou", "太原": "Taiyuan",
        "石家庄": "Shijiazhuang", "南昌": "Nanchang", "无锡": "Wuxi", "宁波": "Ningbo",
    }
    city_en = city_pinyin.get(city, city)
    
    geo = requests.get(
        "https://geocoding-api.open-meteo.com/v1/search",
        params={"name": city_en, "count": 1, "language": "zh", "format": "json"},
        timeout=10
    ).json()
    if not geo.get("results"):
        raise ValueError(f"Open-Meteo 找不到城市: {city}")
    loc = geo["results"][0]
    lat, lon = loc["latitude"], loc["longitude"]
    
    weather = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": lat, "longitude": lon,
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_direction_10m,precipitation,cloud_cover",
            "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunrise,sunset",
            "timezone": "Asia/Shanghai", "forecast_days": 3
        },
        timeout=10
    ).json()
    cur = weather.get("current", {})
    daily = weather.get("daily", {})
    weather_code_map = {
        0: "晴", 1: "大部晴", 2: "局部多云", 3: "多云",
        45: "雾", 48: "冻雾",
        51: "小毛毛雨", 53: "毛毛雨", 55: "大毛毛雨",
        61: "小雨", 63: "中雨", 65: "大雨",
        71: "小雪", 73: "中雪", 75: "大雪",
        80: "阵雨", 81: "中阵雨", 82: "大阵雨",
        95: "雷暴", 96: "雷暴伴小冰雹", 99: "雷暴伴大冰雹",
    }
    wc = cur.get("weather_code", -1)
    desc = weather_code_map.get(wc, f"代码{wc}")
    wd = cur.get("wind_direction_10m", 0)
    dirs = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    wind_dir = dirs[int(wd / 45) % 8] if isinstance(wd, (int, float)) else str(wd)
    
    lines = [
        f"【实时天气 - {loc.get('name', city)}】",
        f"当前温度: {cur.get('temperature_2m')}°C (体感 {cur.get('apparent_temperature')}°C)",
        f"天气状况: {desc}",
        f"湿度: {cur.get('relative_humidity_2m')}% | 云量: {cur.get('cloud_cover')}% | 降水: {cur.get('precipitation')} mm",
        f"风向风力: {wind_dir}风 {cur.get('wind_speed_10m')} km/h",
    ]
    if daily:
        lines.append("")
        lines.append("【未来3天预报】")
        for i in range(3):
            date = daily["time"][i]
            mx = daily["temperature_2m_max"][i]
            mn = daily["temperature_2m_min"][i]
            rc = daily["precipitation_probability_max"][i]
            dwc = weather_code_map.get(daily["weather_code"][i], f"代码{daily['weather_code'][i]}")
            lines.append(f"第{i+1}天 ({date}): {mn}°C~{mx}°C | {dwc} | 降水概率{rc}%")
    return "\n".join(lines)


def _search_bing(query: str, max_results: int) -> list:
    """Bing 搜索：国内稳定可用"""
    import requests
    from bs4 import BeautifulSoup

    url = f"https://www.bing.com/search?q={query}&count={max_results}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    r = requests.get(url, headers=headers, timeout=15)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    for li in soup.select("li.b_algo"):
        title_tag = li.find("h2")
        if title_tag:
            a_tag = title_tag.find("a")
            title = a_tag.get_text(strip=True) if a_tag else title_tag.get_text(strip=True)
            href = a_tag.get("href", "") if a_tag else ""
            desc = li.find("p") or li.find("div", class_="b_caption")
            desc_text = desc.get_text(strip=True)[:200] if desc else ""
            if title:
                results.append({"title": title, "body": desc_text, "href": href})
            if len(results) >= max_results:
                break
    return results


def _search_ddg(query: str, max_results: int, region: str = "cn-zh") -> list:
    """DuckDuckGo 搜索：使用 cn-zh 区域避免被墙"""
    with DDGS(timeout=15) as ddgs:
        ddg_results = list(ddgs.text(query, max_results=max_results, region=region))
    return [
        {
            "title": r.get("title", ""),
            "body": r.get("body", "") or r.get("content", ""),
            "href": r.get("href", "") or r.get("url", ""),
        }
        for r in ddg_results
    ]


def _search_baidu(query: str, max_results: int) -> list:
    """百度搜索：使用多组选择器提升健壮性，避免百度页面结构变更导致失效"""
    import requests
    from bs4 import BeautifulSoup

    baidu_url = f"http://www.baidu.com/s?wd={query}&rn={max_results}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    r = requests.get(baidu_url, headers=headers, timeout=10)
    r.encoding = "utf-8"
    soup = BeautifulSoup(r.text, "html.parser")

    results = []
    # 多组备用选择器，应对百度页面结构调整
    selector_groups = [
        ("div", {"class": "result-op c-container xpath-log new-pmd"}),
        ("div", {"class": "result c-container"}),
        ("div", {"class": "c-container"}),
    ]
    for tag, attrs in selector_groups:
        if len(results) >= max_results:
            break
        for item in soup.find_all(tag, attrs):
            if len(results) >= max_results:
                break
            title_tag = item.find("h3") or item.find("h3", class_="t")
            # 摘要可能是多种 class
            desc_tag = (item.find("div", class_="c-abstract")
                        or item.find("span", class_="content-right_8Zs40")
                        or item.find("div", class_="c-span-last"))
            link_tag = item.find("a")
            if title_tag:
                results.append({
                    "title": title_tag.get_text(strip=True),
                    "body": desc_tag.get_text(strip=True) if desc_tag else "",
                    "href": link_tag["href"] if (link_tag and link_tag.get("href")) else ""
                })
    return results


def _format_results(results: list) -> str:
    """统一格式化搜索结果"""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[结果{i}] {r.get('title', '')}\n{r.get('body', '')}\n链接: {r.get('href', '')}\n")
    return "\n".join(parts)

ALL_TOOLS = [rag_search, web_search]