#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小鹅通「16号内参」圈子全量抓取 v2（列表直抓版）。
关键发现：feed_list 列表页本身渲染每篇文章的完整正文（无需进详情页）。
流程：导航列表页 → 滚动+点"加载更多"加载全部 → 按 feeds_id 分组抓容器完整文本 → 存 Markdown/JSON。

用法：python3 xiaoe_list_crawl.py
输出：raw/xiaoe/articles.json + raw/xiaoe/文章/XX.md
"""
import socket, base64, os, json, struct, time, sys, pathlib, re

CDP_HOST, CDP_PORT = "127.0.0.1", 9222
CIRCLE = "c_64560187cf542_WEbInzlM7460"
APP_ID = "appbmkTImri3688"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "xiaoe"
ART = OUT / "文章"
OUT.mkdir(parents=True, exist_ok=True)
ART.mkdir(parents=True, exist_ok=True)

# ---------- 基础 WS（同 v1） ----------
def _recv_exact(s, n, timeout=10):
    s.settimeout(timeout)
    buf = b''
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            break
        buf += c
    s.settimeout(None)
    return buf

def ws_recv_frame(s, timeout=10):
    s.settimeout(timeout)
    try:
        data = _recv_exact(s, 2, timeout=timeout)
    except socket.timeout:
        return None
    if len(data) < 2:
        return None
    fin = data[0] & 0x80
    opcode = data[0] & 0x0f
    length = data[1] & 0x7f
    if length == 126:
        ext = _recv_exact(s, 2, timeout=timeout)
        if len(ext) < 2:
            return None
        length = struct.unpack('>H', ext)[0]
    elif length == 127:
        ext = _recv_exact(s, 8, timeout=timeout)
        if len(ext) < 8:
            return None
        length = struct.unpack('>Q', ext)[0]
    payload = _recv_exact(s, length, timeout=timeout)
    if len(payload) < length:
        return None
    while not fin:
        h2 = _recv_exact(s, 2, timeout=timeout)
        if len(h2) < 2:
            return None
        fin = h2[0] & 0x80
        l2 = h2[1] & 0x7f
        if l2 == 126:
            ext = _recv_exact(s, 2, timeout=timeout)
            l2 = struct.unpack('>H', ext)[0] if len(ext) == 2 else l2
        elif l2 == 127:
            ext = _recv_exact(s, 8, timeout=timeout)
            l2 = struct.unpack('>Q', ext)[0] if len(ext) == 8 else l2
        p2 = _recv_exact(s, l2, timeout=timeout)
        if len(p2) < l2:
            return None
        payload += p2
    if opcode == 9:
        return None
    return payload.decode('utf-8', 'replace')

def ws_send(s, msg):
    p = msg.encode('utf-8')
    L = len(p)
    h = bytearray([0x81])
    if L < 126:
        h.append(0x80 | L)
    elif L < 65536:
        h.append(0x80 | 126)
        h += struct.pack('>H', L)
    else:
        h.append(0x80 | 127)
        h += struct.pack('>Q', L)
    m = os.urandom(4)
    mk = bytes(b ^ m[i % 4] for i, b in enumerate(p))
    s.sendall(bytes(h) + m + mk)

def ws_connect(max_tries=5, wait=5):
    for i in range(max_tries):
        try:
            key = base64.b64encode(os.urandom(16)).decode()
            req = (f"GET /devtools/browser HTTP/1.1\r\nHost: {CDP_HOST}:{CDP_PORT}\r\n"
                   "Upgrade: websocket\r\nConnection: Upgrade\r\n"
                   f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
                   "Sec-WebSocket-Protocol: chrome-devtools\r\n\r\n")
            s = socket.create_connection((CDP_HOST, CDP_PORT), timeout=12)
            s.settimeout(15)
            s.sendall(req.encode())
            hdr = b''
            while b'\r\n\r\n' not in hdr and len(hdr) < 8192:
                c = s.recv(1)
                if not c:
                    break
                hdr += c
            s.settimeout(None)
            if b'101' not in hdr:
                s.close()
                continue
            return s
        except Exception:
            time.sleep(wait)
    return None

_cid = [1000]
def cmd(s, method, params=None, sess=None, timeout=15):
    _cid[0] += 1
    mid = _cid[0]
    msg = {"id": mid, "method": method, "params": params or {}}
    if sess:
        msg["sessionId"] = sess
    ws_send(s, json.dumps(msg))
    dl = time.time() + timeout
    while time.time() < dl:
        f = ws_recv_frame(s, timeout=timeout)
        if f:
            try:
                d = json.loads(f)
                if d.get('id') == mid:
                    return d
            except Exception:
                pass
    return None

def attach_via_event(s):
    r = cmd(s, "Target.getTargets", {}, timeout=15)
    if not r or 'result' not in r:
        return None, None
    tids = [t for t in r['result']['targetInfos'] if 'quanzi.xiaoe' in t.get('url', '')]
    if not tids:
        return None, None
    tid = tids[0]['targetId']
    _cid[0] += 1
    mid = _cid[0]
    ws_send(s, json.dumps({"id": mid, "method": "Target.attachToTarget",
                           "params": {"targetId": tid, "flatten": True}}))
    dl = time.time() + 15
    while time.time() < dl:
        f = ws_recv_frame(s, timeout=15)
        if f:
            try:
                d = json.loads(f)
                if d.get('method') == 'Target.attachedToTarget':
                    return tid, d['params']['sessionId']
                if d.get('id') == mid and 'result' in d:
                    return tid, d['result']['sessionId']
            except Exception:
                pass
    return None, None

def ev(s, sess, js, timeout=20):
    _cid[0] += 1
    mid = _cid[0]
    ws_send(s, json.dumps({"id": mid, "method": "Runtime.evaluate",
                           "params": {"expression": js, "returnByValue": True,
                                      "timeout": timeout * 1000},
                           "sessionId": sess}))
    dl = time.time() + timeout
    while time.time() < dl:
        f = ws_recv_frame(s, timeout=timeout)
        if f:
            try:
                d = json.loads(f)
                if d.get('id') == mid:
                    v = d.get('result', {}).get('result', {}).get('value')
                    if isinstance(v, str):
                        try:
                            return json.loads(v)
                        except Exception:
                            return v
                    return v
            except Exception:
                pass
    return None

# ---------- 抓取逻辑 ----------
def navigate_feed_list(s, sess):
    feed_url = f"https://quanzi.xiaoe-tech.com/{CIRCLE}/feed_list?app_id={APP_ID}"
    cur = ev(s, sess, "location.href", timeout=8)
    if not cur or 'feed_list' not in str(cur):
        _cid[0] += 1
        ws_send(s, json.dumps({"id": _cid[0], "method": "Page.navigate",
                               "params": {"url": feed_url}, "sessionId": sess}))
    # 等待列表渲染
    for _ in range(15):
        time.sleep(2)
        st = ev(s, sess, "JSON.stringify({u:location.href,n:document.body.innerText.length})", timeout=8)
        if st and st.get('n', 0) > 800:
            return True
    return False

def load_all_feed(s, sess, max_rounds=25):
    """滚动 + 点加载更多，直到链接数稳定。"""
    last_count = -1
    stable = 0
    for rnd in range(max_rounds):
        # 滚动到底（多次）
        ev(s, sess, "(function(){for(var i=0;i<8;i++){window.scrollTo(0,document.body.scrollHeight);var sc=document.querySelector('[class*=scroll],[class*=list],[class*=feed]');if(sc)sc.scrollTop=sc.scrollHeight;window.scrollBy(0,-200);}}return 1;})()", timeout=12)
        # 点"加载更多/查看更多"
        ev(s, sess, "(function(){var els=Array.from(document.querySelectorAll('button,a,div,span'));for(var i=0;i<els.length;i++){var t=(els[i].innerText||'').trim();if(/加载更多|查看更多|load.?more/i.test(t)&&t.length<20){els[i].click();return 1;}}return 0;})()", timeout=8)
        time.sleep(2.5)
        # 统计当前链接数
        cnt = ev(s, sess, "(function(){var seen={};Array.from(document.querySelectorAll('a')).forEach(function(a){var m=(a.href||'').match(/feeds_id=(d_\\w+)/);if(m)seen[m[1]]=1;});return Object.keys(seen).length;})()", timeout=10)
        print(f"  轮次{rnd+1}: 已加载 {cnt} 篇", flush=True)
        if cnt is not None and cnt == last_count:
            stable += 1
            if stable >= 3:
                break
        elif cnt is not None:
            last_count = cnt
            stable = 0
    return last_count

def extract_articles(s, sess):
    """抓所有 feed 容器，按 feeds_id 分组，每篇取最深/最长的文本。"""
    js = r"""
    (function(){
      var map = {};
      // 抓所有含 feeds_id 链接的容器（从最深匹配起）
      var links = Array.from(document.querySelectorAll('a[href*="feeds_id"]'));
      links.forEach(function(a){
        var m = (a.href||'').match(/feeds_id=(d_\w+)/);
        if(!m) return;
        var id = m[1];
        // 向上找最近的 feed 容器
        var el = a;
        for(var up=0; up<8; up++){
          el = el.parentElement;
          if(!el) break;
          var cls = el.getAttribute('class')||'';
          if(/feed-item|feed_item|feedItem|feed-detail|feedDetail|card/.test(cls)) break;
        }
        var txt = el ? (el.innerText||'').trim() : a.innerText.trim();
        // 标题：容器内第一个较长的非空行或 h1-h4
        var title = '';
        var hs = el ? el.querySelectorAll('h1,h2,h3,h4,[class*=title]') : [];
        if(hs.length) title = hs[0].innerText.trim().slice(0,80);
        if(!title){
          var lines = txt.split('\n').filter(function(l){return l.trim().length>4;});
          title = lines[0] ? lines[0].slice(0,80) : '';
        }
        // 保留最大文本（外层容器文本更长）
        if(!map[id] || txt.length > map[id].txt.length){
          map[id] = {id:id, txt:txt, title:title, href:a.href};
        }
      });
      return JSON.stringify(map);
    })()
    """
    r = ev(s, sess, js, timeout=25)
    return r if isinstance(r, dict) else {}

def parse_article(item):
    """从容器文本解析元信息+正文。"""
    txt = item.get('txt', '')
    lines = [l.strip() for l in txt.split('\n') if l.strip()]
    # 常见结构：作者\n角色\n日期\n地点\n标题\n正文
    title = item.get('title') or ''
    author = ''
    date = ''
    # 找日期行（MM-DD 或 YYYY-MM-DD 或 小时前）
    for i, l in enumerate(lines[:6]):
        if re.search(r'\d{2}-\d{2}|\d{4}-\d{2}-\d{2}|\d+小时前|\d+天前|刚刚|昨天', l):
            date = l
            # 作者通常在日期之前 1-3 行
            for j in range(max(0, i-3), i):
                if lines[j] and lines[j] not in ('圈主', '嘉宾', '管理员'):
                    author = lines[j]
            break
    # 标题：优先 item.title；否则在日期之后找第一行
    if not title:
        idx = 0
        for i, l in enumerate(lines[:8]):
            if re.search(r'\d{2}-\d{2}|\d{4}-\d{2}-\d{2}', l):
                idx = i + 1
                break
        while idx < len(lines) and len(lines[idx]) < 4:
            idx += 1
        title = lines[idx] if idx < len(lines) else 'untitled'
    # 正文 = 标题之后的内容（去掉 title 本身）
    body = txt
    if title and title in txt:
        pos = txt.find(title)
        if pos >= 0:
            body = txt[pos + len(title):].strip()
    return {
        'feeds_id': item.get('id'),
        'title': title[:100],
        'author': author[:30],
        'date': date[:30],
        'url': item.get('href', ''),
        'body': body[:50000],
        'len': len(body),
    }

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_')[:80] or 'untitled'

def main():
    print("=== 小鹅通 16号内参 全量抓取 v2（列表直抓）===", flush=True)
    for attempt in range(1, 11):
        print(f"[尝试 {attempt}/10] 连接...", flush=True)
        s = ws_connect()
        if not s:
            time.sleep(8)
            continue
        try:
            tid, sess = attach_via_event(s)
            if not sess:
                s.close(); time.sleep(6); continue
            print("  已 attach，导航列表页...", flush=True)
            if not navigate_feed_list(s, sess):
                print("  列表页未就绪", flush=True)
                s.close(); time.sleep(6); continue
            print("  加载全部文章...", flush=True)
            total = load_all_feed(s, sess)
            print(f"  共加载 {total} 篇，开始提取正文...", flush=True)
            raw = extract_articles(s, sess)
            if not raw:
                print("  未提取到内容", flush=True)
                s.close(); time.sleep(6); continue
            articles = [parse_article(v) for v in raw.values()]
            articles.sort(key=lambda a: a.get('len', 0), reverse=True)
            # 保存 JSON
            (OUT / "articles.json").write_text(json.dumps(articles, ensure_ascii=False, indent=2))
            # 写 Markdown
            n = 0
            for i, a in enumerate(articles):
                if a.get('len', 0) < 50:
                    continue
                n += 1
                md = f"# {a['title']}\n\n"
                md += f"> 来源：小鹅通圈子「16号内参——拾榴询财小密圈」\n"
                if a.get('author'):
                    md += f"> 作者：{a['author']}\n"
                if a.get('date'):
                    md += f"> 日期：{a['date']}\n"
                md += f"> 链接：{a.get('url','')}\n"
                md += f"> 抓取时间：{time.strftime('%Y-%m-%d %H:%M')}\n\n---\n\n"
                md += a['body']
                (ART / f"{i+1:02d}_{sanitize(a['title'])}.md").write_text(md, encoding='utf-8')
            print(f"\n✅ 完成：提取 {len(articles)} 条，写入 {n} 篇 Markdown", flush=True)
            print(f"   JSON: raw/xiaoe/articles.json", flush=True)
            print(f"   Markdown: raw/xiaoe/文章/", flush=True)
            s.close()
            return
        except Exception as e:
            print(f"  异常：{type(e).__name__}: {e}", flush=True)
            try:
                s.close()
            except Exception:
                pass
            time.sleep(8)
    print("❌ 多次尝试后仍未成功", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    main()
