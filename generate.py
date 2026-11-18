#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取公开 RSS 源，生成简报风格热点首页 + 各分类完整页。"""

import html
import re
import urllib.request
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

import json

from style import CSS
from oil import build_all, PRODUCTS, OIL_SOURCE

CST = timezone(timedelta(hours=8))
UTC = timezone.utc

FEEDS = [
    ("时政", "人民网·时政", "http://www.people.com.cn/rss/politics.xml"),
    ("财经", "人民网·财经", "http://www.people.com.cn/rss/finance.xml"),
    ("财经", "中新网·财经", "http://www.chinanews.com.cn/rss/finance.xml"),
    ("科技", "IT之家", "https://www.ithome.com/rss/"),
    ("科技", "人民网·科技", "http://www.people.com.cn/rss/it.xml"),
    ("混合", "中新网·即时", "http://www.chinanews.com.cn/rss/scroll-news.xml"),
]

CAT_SLUG = {"时政": "politics", "国际": "world", "财经": "finance", "科技": "tech", "社会": "society"}
OIL_DATA_GLOBAL = {}
PREVIEW = 5
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def clean(text):
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_time(raw):
    if not raw:
        return None
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(CST)
    except Exception:
        pass
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=CST)
        except Exception:
            pass
    return None


def classify(link, default):
    if "/gn/" in link:
        return "时政"
    if "/gj/" in link:
        return "国际"
    return default


def load_items():
    items = []
    for cat, source, url in FEEDS:
        try:
            root = ET.fromstring(fetch(url))
            for node in root.findall(".//item")[:12]:
                title = clean(node.findtext("title", ""))
                link = clean(node.findtext("link", ""))
                desc = clean(node.findtext("description", ""))
                pub = parse_time(node.findtext("pubDate", ""))
                if title and link:
                    real_cat = classify(link, "社会") if cat == "混合" else cat
                    items.append({"cat": real_cat, "source": source, "title": title,
                                  "link": link, "desc": desc, "time": pub})
            print(f"OK   {source}: {len(root.findall('.//item'))} 条")
        except Exception as e:
            print(f"FAIL {source}: {e}")
    return items


def esc(s):
    return html.escape(s or "")


def news_card(i):
    t = i["time"].strftime("%Y-%m-%d %H:%M") if i["time"] else "未获取到"
    title = f'<a href="{esc(i["link"])}" target="_blank" rel="noopener">{esc(i["title"])}</a>'
    return f"""
    <article class="news">
      <div class="news-top"><h3>{title}</h3><span class="when">{t}</span></div>
      <p class="summary">{esc(i['desc'][:150]) or '摘要未获取到'}</p>
      <div class="meta"><span>来源：<a href="{esc(i['link'])}" target="_blank" rel="noopener">{esc(i['source'])}</a></span><span>发布日期：{t}</span></div>
    </article>"""


def flash_card(i, n):
    return f"""
    <div class="flash">
      <div class="flash-num">{n}</div>
      <div><h3><a href="{esc(i['link'])}" target="_blank" rel="noopener">{esc(i['title'])}</a></h3>
      <p><span class="flash-tag">{esc(i['source'])}</span>{esc(i['desc'][:80])}</p></div>
    </div>"""


def oil_html(oil_data):
    """油价卡片：省份下拉 + 4 项价格（JS 驱动），带趋势页入口。"""
    provinces = list(oil_data.keys())
    opts = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in provinces)
    default = "北京" if "北京" in oil_data else (provinces[0] if provinces else "")
    return f"""
    <div class="oil" id="oilCard">
      <div class="oil-head"><h3>今日油价</h3><span class="oil-meta" id="oilUpdate">—</span></div>
      <div class="oil-ctrl">
        <label for="provinceSel">选择地区</label>
        <select id="provinceSel">{opts}</select>
        <a class="trend-btn" href="oil-trend.html">查看油价变化趋势 →</a>
        <span class="loc-tip" id="locTip">正在自动定位…</span>
      </div>
      <div class="oil-grid" id="oilGrid"></div>
      <div class="oil-src">数据来源：<a href="{OIL_SOURCE}" target="_blank" rel="noopener">今日油价查询</a> · 各加油站实际价格可能有浮动，以现场标价为准。</div>
    </div>"""


OIL_JS_TEMPLATE = """
<script>
var OIL_DATA = __OIL_DATA__;
var PRODUCTS = __PRODUCTS__;
function renderOil(name){{
  var d = OIL_DATA[name];
  var grid = document.getElementById('oilGrid');
  var up = document.getElementById('oilUpdate');
  if(!d || !d.prices || Object.keys(d.prices).length===0){{
    grid.innerHTML = '<p class="oil-src">该地区油价未获取到</p>';
    up.textContent = '数据未获取到';
    return;
  }}
  grid.innerHTML = PRODUCTS.map(function(p){{
    var v = d.prices[p];
    return '<div class="oil-item"><span class="oil-name">'+p+'</span><span class="oil-val">'+(v||'—')+'</span><span class="oil-unit">元/升</span></div>';
  }}).join('');
  up.textContent = name + '地区参考价 · ' + (d.update ? ('更新于 '+d.update) : '更新时间未获取到');
}}
(function(){{
  var sel = document.getElementById('provinceSel');
  if(!sel) return;
  renderOil(sel.value);
  sel.addEventListener('change', function(){{ renderOil(sel.value); }});
}})();
</script>
"""


def oil_js(oil_data):
    data_json = json.dumps(oil_data, ensure_ascii=False, separators=(",", ":"))
    prod_json = json.dumps(PRODUCTS, ensure_ascii=False)
    return OIL_JS_TEMPLATE.replace("__OIL_DATA__", data_json).replace("__PRODUCTS__", prod_json)


# 访客 IP 自动定位：主接口返回中文省份，备用接口返回英文省份，均支持跨域。
# 定位失败或无法匹配时保留手动选择，不编造地区。
GEO_JS_TEMPLATE = r"""
<script>
(function(){
  var PROVINCES = __PROVINCES__;
  var SEL_ID = '__SEL_ID__';
  var TIP_ID = '__TIP_ID__';
  var EN2CN = {
    beijing:'北京',tianjin:'天津',shanghai:'上海',chongqing:'重庆',
    hebei:'河北',shanxi:'山西',liaoning:'辽宁',jilin:'吉林',heilongjiang:'黑龙江',
    jiangsu:'江苏',zhejiang:'浙江',anhui:'安徽',fujian:'福建',jiangxi:'江西',
    shandong:'山东',henan:'河南',hubei:'湖北',hunan:'湖南',guangdong:'广东',
    hainan:'海南',sichuan:'四川',guizhou:'贵州',yunnan:'云南',shaanxi:'陕西',
    gansu:'甘肃',qinghai:'青海',xinjiang:'新疆',ningxia:'宁夏',
    'inner mongolia':'内蒙古',guangxi:'广西',xizang:'西藏',tibet:'西藏'
  };
  function norm(s){
    if(!s) return '';
    s = String(s).trim();
    if(PROVINCES.indexOf(s)>=0) return s;
    var t = s.replace(/(省|市|特别行政区|壮族自治区|回族自治区|维吾尔自治区|自治区)$/,'');
    if(PROVINCES.indexOf(t)>=0) return t;
    var t2 = t.replace(/(壮族|回族|维吾尔|自治)/g,'');
    if(PROVINCES.indexOf(t2)>=0) return t2;
    var first = s.toLowerCase().split(/[\s,]/)[0];
    if(EN2CN[first] && PROVINCES.indexOf(EN2CN[first])>=0) return EN2CN[first];
    return '';
  }
  function getJSON(url){
    return new Promise(function(res,rej){
      var ctl = window.AbortController ? new AbortController() : null;
      var timer = setTimeout(function(){ if(ctl) ctl.abort(); rej(new Error('timeout')); }, 6000);
      fetch(url,{signal:ctl?ctl.signal:undefined,cache:'no-store'})
        .then(function(r){ if(!r.ok) throw new Error('http'); return r.json(); })
        .then(function(j){ clearTimeout(timer); res(j); })
        .catch(function(e){ clearTimeout(timer); rej(e); });
    });
  }
  function fireChange(el){
    try{ el.dispatchEvent(new Event('change')); }
    catch(e){ var ev=document.createEvent('HTMLEvents'); ev.initEvent('change',true,true); el.dispatchEvent(ev); }
  }
  function apply(prov){
    if(!prov) return false;
    var sel = document.getElementById(SEL_ID);
    if(!sel) return false;
    for(var i=0;i<sel.options.length;i++){
      if(sel.options[i].value===prov){
        sel.value = prov;
        fireChange(sel);
        var tip = document.getElementById(TIP_ID);
        if(tip){ tip.textContent = '已按 IP 自动定位：'+prov+'（可手动切换）'; tip.className='loc-tip ok'; }
        return true;
      }
    }
    return false;
  }
  function fail(){
    var tip = document.getElementById(TIP_ID);
    if(tip){ tip.textContent='自动定位未成功，请手动选择'; tip.className='loc-tip warn'; }
  }
  function run(){
    getJSON('https://myip.ipip.net/json')
      .then(function(j){ var loc=j&&j.data&&j.data.location; return norm(loc&&loc[1]); })
      .catch(function(){ return ''; })
      .then(function(p){
        if(p && apply(p)) return;
        return getJSON('https://api.ip.sb/geoip')
          .then(function(k){ return norm(k&&k.region); })
          .catch(function(){ return ''; })
          .then(function(p2){ if(!p2 || !apply(p2)) fail(); });
      });
  }
  if(document.readyState==='loading') document.addEventListener('DOMContentLoaded',run);
  else run();
})();
</script>
"""


def geo_js(sel_id, tip_id):
    prov_json = json.dumps(list(OIL_DATA_GLOBAL.keys()), ensure_ascii=False)
    return (GEO_JS_TEMPLATE.replace("__PROVINCES__", prov_json)
            .replace("__SEL_ID__", sel_id).replace("__TIP_ID__", tip_id))


def page(title, body):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="今日热点速览，来源可核查。">
<style>{CSS}</style>
</head>
<body>
{body}
</body>
</html>"""


def header_html(stamp, cat_line, title="今日热点速览", back=False):
    back_link = '<a class="back" href="index.html">← 返回首页</a>' if back else ""
    return f"""
<header><div class="h-inner">
  <span class="kicker">Daily Briefing · 公开信源核验</span>
  <h1>{title}</h1>
  <p class="dateline"><b>{stamp}</b>　|　{cat_line}</p>
  <div class="h-meta">
    <span><i class="dot"></i>内容自动抓取自公开 RSS 源</span>
    <span><i class="dot"></i>点击标题可跳转原文核对</span>
    {back_link}
  </div>
</div></header>"""


def footer_html(home=False):
    entry = ""
    if home:
        entry = """
  <div class="home-entry">
    <span>想认识我本人？</span>
    <a href="me/">进入我的个人主页 →</a>
  </div>"""
    return f"""
<footer>
  <h4>信息核实说明</h4>
  <ul>
    <li>所有条目来自公开 RSS 源（人民网、中新网、IT之家等），标题、时间与来源均可点击原文核对。</li>
    <li>发生时间以来源发布时间为准；部分源仅提供发布日期，已按原文展示。</li>
    <li>本页由脚本自动生成，为聚合展示，不代表本站观点。</li>
  </ul>{entry}
</footer>"""


TREND_JS_TEMPLATE = r"""
<script>
var HDATA = __HISTORY_DATA__;
var PRODS = __PRODUCTS__;
var COLORS = {'92号汽油':'#b91c1c','95号汽油':'#1e3a5f','98号汽油':'#92400e','0号柴油':'#15803d'};
var selProv = document.getElementById('trendProv');
var selProd = document.getElementById('trendProd');
var curProduct = PRODS[0];

function fmtDate(s){ return s ? s.slice(5) : ''; }

function drawChart(){
  var d = HDATA[selProv.value];
  var wrap = document.getElementById('chartBox');
  var stats = document.getElementById('trendStats');
  var tbody = document.getElementById('trendTbody');
  if(!d || !d.history || d.history.dates.length===0){
    wrap.innerHTML = '<p class="oil-src">该地区历史数据未获取到</p>';
    stats.innerHTML = ''; tbody.innerHTML = ''; return;
  }
  var dates = d.history.dates;
  var vals = d.history.series[curProduct] || [];
  var pts = vals.map(function(v,i){return {v:v, d:dates[i]};}).filter(function(p){return typeof p.v==='number';});
  if(pts.length===0){ wrap.innerHTML='<p class="oil-src">该产品历史数据未获取到</p>'; return; }

  var W=980, H=340, L=52, R=20, T=24, B=46;
  var iw=W-L-R, ih=H-T-B;
  var vs=pts.map(function(p){return p.v;});
  var vmin=Math.min.apply(null,vs), vmax=Math.max.apply(null,vs);
  var pad=Math.max((vmax-vmin)*0.25, 0.15);
  vmin=Math.max(0,vmin-pad); vmax=vmax+pad;
  function X(i){ return L + (pts.length===1?iw/2:i*iw/(pts.length-1)); }
  function Y(v){ return T + ih - (v-vmin)/(vmax-vmin)*ih; }

  var svg='<svg viewBox="0 0 '+W+' '+H+'" xmlns="http://www.w3.org/2000/svg" role="img">';
  // 横向网格 + Y轴刻度
  var ticks=5;
  for(var g=0; g<=ticks; g++){
    var val=vmin+(vmax-vmin)*g/ticks;
    var y=Y(val);
    svg+='<line x1="'+L+'" y1="'+y+'" x2="'+(W-R)+'" y2="'+y+'" stroke="#e5e7eb" stroke-width="1"/>';
    svg+='<text x="'+(L-8)+'" y="'+(y+4)+'" text-anchor="end" font-size="12" fill="#6b7280">'+val.toFixed(1)+'</text>';
  }
  // 折线
  var path=pts.map(function(p,i){return (i===0?'M':'L')+X(i).toFixed(1)+' '+Y(p.v).toFixed(1);}).join(' ');
  svg+='<path d="'+path+'" fill="none" stroke="'+(COLORS[curProduct]||'#1e3a5f')+'" stroke-width="2.5" stroke-linejoin="round"/>';
  // 数据点与日期标签
  pts.forEach(function(p,i){
    var x=X(i), y=Y(p.v);
    svg+='<circle cx="'+x.toFixed(1)+'" cy="'+y.toFixed(1)+'" r="4" fill="#fff" stroke="'+(COLORS[curProduct]||'#1e3a5f')+'" stroke-width="2"/>';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(y-12).toFixed(1)+'" text-anchor="middle" font-size="11" fill="#4b5563">'+p.v.toFixed(2)+'</text>';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(H-16)+'" text-anchor="middle" font-size="11" fill="#6b7280">'+fmtDate(p.d)+'</text>';
  });
  svg+='</svg>';
  wrap.innerHTML=svg;

  // 统计
  var first=pts[0].v, last=pts[pts.length-1].v;
  var change=(last-first);
  var pct=(change/first*100);
  var cls=change>0?'up':(change<0?'down':'');
  var sign=change>0?'+':'';
  stats.innerHTML=
    '<div class="stat"><span class="stat-label">当前价格</span><span class="stat-val">'+last.toFixed(2)+'</span></div>'+
    '<div class="stat"><span class="stat-label">历史最低</span><span class="stat-val">'+Math.min.apply(null,vs).toFixed(2)+'</span></div>'+
    '<div class="stat"><span class="stat-label">历史最高</span><span class="stat-val">'+Math.max.apply(null,vs).toFixed(2)+'</span></div>'+
    '<div class="stat"><span class="stat-label">区间变化</span><span class="stat-val '+cls+'">'+sign+change.toFixed(2)+' ('+sign+pct.toFixed(1)+'%)</span></div>';

  // 表格（最近 12 次，倒序）
  var rows='';
  for(var i=pts.length-1;i>=0;i--){
    var p=pts[i];
    var prev=i>0?pts[i-1].v:null;
    var delta=prev!==null?(p.v-prev):null;
    var dtxt=delta===null?'—':((delta>0?'+':'')+delta.toFixed(2));
    var dcls=delta===null?'':(delta>0?'delta-up':(delta<0?'delta-down':''));
    rows+='<tr><td>'+p.d+'</td><td>'+p.v.toFixed(2)+'</td><td class="'+dcls+'">'+dtxt+'</td></tr>';
  }
  tbody.innerHTML=rows;
}

document.getElementById('trendProv').addEventListener('change', drawChart);
document.getElementById('trendProd').addEventListener('change', function(){curProduct=this.value; drawChart();});
drawChart();
</script>
"""


def build_trend_page(stamp):
    data_json = json.dumps(OIL_DATA_GLOBAL, ensure_ascii=False, separators=(",", ":"))
    prod_json = json.dumps(PRODUCTS, ensure_ascii=False)
    provinces = list(OIL_DATA_GLOBAL.keys())
    prov_opts = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in provinces)
    prod_opts = "".join(f'<option value="{esc(p)}">{esc(p)}</option>' for p in PRODUCTS)
    js = TREND_JS_TEMPLATE.replace("__HISTORY_DATA__", data_json).replace("__PRODUCTS__", prod_json)
    return f"""
{header_html(stamp, "油价变化趋势 · 历史调价走势", title="油价变化趋势", back=True)}
<div class="wrap">
  <section>
    <div class="sec-head"><span class="sec-no">01</span><h2>历史调价走势</h2><span class="sec-note">数据来自公开油价查询页</span></div>
    <div class="trend-panel">
      <div class="trend-ctrl">
        <label for="trendProv">地区</label><select id="trendProv">{prov_opts}</select>
        <label for="trendProd">油品</label><select id="trendProd">{prod_opts}</select>
        <span class="loc-tip" id="locTipTrend">正在自动定位…</span>
      </div>
      <div class="trend-stats" id="trendStats"></div>
      <div class="chart-wrap" id="chartBox"></div>
      <div class="chart-legend">
        <span><i style="background:#b91c1c"></i>92号汽油</span>
        <span><i style="background:#1e3a5f"></i>95号汽油</span>
        <span><i style="background:#92400e"></i>98号汽油</span>
        <span><i style="background:#15803d"></i>0号柴油</span>
      </div>
      <table class="trend-table">
        <thead><tr><th>调整日期</th><th>价格（元/升）</th><th>较上次变化</th></tr></thead>
        <tbody id="trendTbody"></tbody>
      </table>
    </div>
  </section>
  {footer_html()}
</div>
{js}
{geo_js("trendProv", "locTipTrend")}"""


def main():
    items = load_items()
    now = datetime.now(CST)

    seen = set()
    deduped = []
    for i in items:
        if i["title"] not in seen:
            seen.add(i["title"])
            deduped.append(i)
    items = deduped

    cutoff = now - timedelta(days=3)
    items = [i for i in items if i["time"] and i["time"] >= cutoff]
    items.sort(key=lambda x: x["time"], reverse=True)

    today = now.strftime("%Y年%m月%d日")
    weekday = "一二三四五六日"[now.weekday()]
    stamp = f"{today}　星期{weekday}　{now.strftime('%H:%M')} 更新"

    groups = {c: [i for i in items if i["cat"] == c] for c in CAT_SLUG}
    groups = {c: g for c, g in groups.items() if g}
    top = items[:6]

    cat_line = " · ".join(groups.keys())
    flash = "".join(flash_card(i, n) for n, i in enumerate(top, 1))

    print("正在抓取各地区油价与历史数据...")
    global OIL_DATA_GLOBAL
    OIL_DATA_GLOBAL = build_all()
    oil_data = OIL_DATA_GLOBAL

    sections = []
    for idx, (cat, group) in enumerate(groups.items(), 1):
        slug = CAT_SLUG[cat]
        cards = "".join(news_card(i) for i in group[:PREVIEW])
        more = (f'<a class="more" href="{slug}.html">更多 {len(group)} 条 →</a>'
                if len(group) > PREVIEW else "")
        sections.append(f"""
    <section>
      <div class="sec-head">
        <span class="sec-no">{idx:02d}</span>
        <h2>{cat}</h2>
        <span class="sec-note">{len(group)} 条</span>
        {more}
      </div>
      <div class="news-list">{cards}
      </div>
    </section>""")

    body = f"""
{header_html(stamp, cat_line)}
<div class="wrap">
  <section>
    <div class="sec-head"><span class="sec-no">00</span><h2>最值得关注</h2><span class="sec-note">今日速览 TOP 6 + 油价</span></div>
    {oil_html(oil_data)}
    <div class="flash-grid">{flash}
    </div>
  </section>
  {''.join(sections)}
  {footer_html(home=True)}
</div>
{oil_js(oil_data)}
{geo_js("provinceSel", "locTip")}"""
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(page(f"今日热点速览 · {today}", body))

    # 生成油价趋势页
    trend_body = build_trend_page(stamp)
    with open("oil-trend.html", "w", encoding="utf-8") as f:
        f.write(page(f"油价变化趋势 · {today}", trend_body))

    for cat, group in groups.items():
        slug = CAT_SLUG[cat]
        cards = "".join(news_card(i) for i in group)
        body = f"""
{header_html(stamp, f"{cat} · 共 {len(group)} 条", title=f"{cat} · 全部热点", back=True)}
<div class="wrap">
  <section>
    <div class="sec-head"><span class="sec-no">01</span><h2>{cat}热点</h2><span class="sec-note">{len(group)} 条</span></div>
    <div class="news-list">{cards}
    </div>
  </section>
  {footer_html()}
</div>"""
        with open(f"{slug}.html", "w", encoding="utf-8") as f:
            f.write(page(f"{cat}热点 · {today}", body))

    print(f"\n生成完成：首页 + {len(groups)} 个分类页，共 {len(items)} 条，{now.strftime('%Y-%m-%d %H:%M')}")
    for cat, group in groups.items():
        print(f"  {cat}: {len(group)} 条 -> {CAT_SLUG[cat]}.html")


if __name__ == "__main__":
    main()
