#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小鹅通圈子爬虫 (CDP WebSocket 直连，端口 9222)。
该 Chrome 的 /json HTTP 端点被关，只能走 WS。脚本封装：
  - 连浏览器、找圈子 feed_list tab
  - 滚动加载全部 feed、抓所有 feed_detail 链接
  - 逐篇进详情页，抓 标题/作者/时间/正文
  - 输出结构化 JSON + Markdown 到 raw/xiaoe/（待收录进 wiki）

用法:
  python3 xiaoe_scraper.py links          # 只抓 feed 列表的所有文章链接
  python3 xiaoe_scraper.py detail <feeds_id>   # 抓单篇详情(调试)
  python3 xiaoe_scraper.py crawl          # 全量爬: 列表+逐篇详情 -> raw/xiaoe/
"""
import socket, base64, os, json, struct, time, sys, pathlib

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222
CIRCLE = "c_64560187cf542_WEbInzlM7460"
APP_ID = "appbmkTImri3688"
ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "raw" / "xiaoe"
OUT.mkdir(parents=True, exist_ok=True)

def ws_connect(retries=6, wait=6):
    """握手带激进重试：该 Chrome CDP 对短时间频繁连接有限速/冷却，跨调用常失败，
    同调用内连续连接则稳定。故连接后应尽量在一个连接内完成全部操作。
    失败后必须等待 wait 秒让 Chrome 释放上个连接。"""
    last = None
    for i in range(retries):
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
                s.close(); continue
            return s
        except Exception as e:
            last = e
            time.sleep(wait)
    raise RuntimeError(f"CDP 连接失败: {last}")

def _recv_exact(s, n, timeout=10):
    """TCP recv 可能返回少于 n 字节，必须循环读满。"""
    s.settimeout(timeout)
    buf = b''
    while len(buf) < n:
        c = s.recv(n - len(buf))
        if not c:
            break
        buf += c
    s.settimeout(None)
    return buf

def ws_recv_frame(s, timeout=8):
    """读一个完整 WS 消息：处理 TCP 拆包 + WS 分帧（fragmentation）。"""
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
    # 若消息分帧（fin=0），继续读 continuation 帧拼起来
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
    if opcode == 9:  # ping
        return None
    return payload.decode('utf-8', 'replace')

def ws_send(s, msg):
    p = msg.encode('utf-8'); L = len(p); h = bytearray([0x81])
    if L < 126: h.append(0x80 | L)
    elif L < 65536: h.append(0x80 | 126); h += struct.pack('>H', L)
    else: h.append(0x80 | 127); h += struct.pack('>Q', L)
    m = os.urandom(4); mk = bytes(b ^ m[i % 4] for i, b in enumerate(p))
    s.sendall(bytes(h) + m + mk)

_cid = [200]
def eval_js(s, sess, js, timeout=25, cid=None):
    if cid is None:
        _cid[0] += 1
        cid = _cid[0]
    ws_send(s, json.dumps({"id": cid, "method": "Runtime.evaluate",
        "params": {"expression": js, "returnByValue": True, "timeout": timeout*1000},
        "sessionId": sess}))
    dl = time.time() + timeout
    while time.time() < dl:
        f = ws_recv_frame(s, timeout=2)
        if f:
            try:
                dd = json.loads(f)  # 每帧独立解析，忽略事件/其他消息
                if dd.get('id') == cid:
                    return dd
            except Exception:
                pass
    return None

def get_session(s):
    def wait_for(pred, timeout=12):
        dl = time.time() + timeout
        n = 0
        while time.time() < dl:
            n += 1
            try:
                f = ws_recv_frame(s, timeout=10)
            except Exception as e:
                print(f"DEBUG recv exc: {repr(e)}", file=sys.stderr)
                return None
            if f:
                try:
                    dd = json.loads(f)
                    if pred(dd):
                        return dd
                except Exception:
                    pass
            else:
                print(f"DEBUG frame#{n}: (empty)", file=sys.stderr)
        print(f"DEBUG TIMEOUT after {n}", file=sys.stderr)
        return None
    r = wait_for(lambda d: d.get('id') == 1 and 'result' in d)
    if not r:
        return None
    targets = r['result']['targetInfos']
    # 匹配 quanzi.xiaoe 的任何 tab（可能是 feed_list 或 feed_detail）
    tid = [t for t in targets if 'quanzi.xiaoe' in t.get('url', '')]
    if not tid:
        print("DEBUG: 未找到 quanzi.xiaoe target", file=sys.stderr)
        return None
    tid = tid[0]['targetId']
    ws_send(s, json.dumps({"id": 2, "method": "Target.attachToTarget",
                            "params": {"targetId": tid, "flatten": True}}))
    r = wait_for(lambda d: d.get('method') == 'Target.attachedToTarget', timeout=12)
    if not r:
        return None
    sess = r['params']['sessionId']
    ws_send(s, json.dumps({"id": 3, "method": "Runtime.enable", "params": {}, "sessionId": sess}))
    time.sleep(0.8)
    return sess

def ensure_feed_list(s, sess, max_wait=20):
    """确保页面停在 feed_list 并渲染完成。若已是 feed_list 则不重复导航。"""
    feed_url = f"https://quanzi.xiaoe-tech.com/{CIRCLE}/feed_list?app_id={APP_ID}"
    # 检查当前 URL
    r = eval_js(s, sess, "location.href", timeout=8, cid=301)
    cur = r.get('result', {}).get('result', {}).get('value', '') if r else ''
    if 'feed_list' not in cur:
        ws_send(s, json.dumps({"id": 302, "method": "Page.navigate",
                                "params": {"url": feed_url}, "sessionId": sess}))
        # 轮询等待：URL 变为 feed_list 且 body 出现内容
        dl = time.time() + max_wait
        while time.time() < dl:
            time.sleep(2)
            r = eval_js(s, sess, "JSON.stringify({u:location.href, n:document.body.innerText.length})", timeout=8, cid=303)
            if r:
                v = r.get('result', {}).get('result', {}).get('value', '')
                try:
                    d = json.loads(v)
                    if 'feed_list' in d['u'] and d['n'] > 1000:
                        break
                except Exception:
                    pass
        time.sleep(2)

def fetch_feed_links(s, sess):
    ensure_feed_list(s, sess)
    # 滚动加载（多轮，每轮多次到底）
    for round_i in range(3):
        ws_send(s, json.dumps({"id": 50 + round_i, "method": "Runtime.evaluate",
            "params": {"expression": "(function(){for(var i=0;i<15;i++){window.scrollTo(0,document.body.scrollHeight);var sc=document.querySelector('[class*=scroll],[class*=list],[class*=feed]');if(sc)sc.scrollTop=sc.scrollHeight;window.scrollBy(0,-200);}}return document.body.scrollHeight;})()",
                       "returnByValue": True}, "sessionId": sess}))
        time.sleep(2.5)
    js = r"""
    (function(){
      var seen={}; var links=[];
      Array.from(document.querySelectorAll('a')).forEach(function(a){
        var h=a.href||''; var m=h.match(/feeds_id=(d_\w+)/);
        if(m && !seen[m[1]]){ seen[m[1]]=1; links.push({id:m[1], t:a.innerText.trim().slice(0,60), h:h}); }
      });
      return JSON.stringify({n:links.length, links:links});
    })()
    """
    r = eval_js(s, sess, js, timeout=20)
    if not r:
        return []
    val = r.get('result', {}).get('result', {}).get('value', '')
    try:
        d = json.loads(val)
    except Exception:
        return []
    return d['links']

def fetch_detail(s, sess, feeds_id):
    url = f"https://quanzi.xiaoe-tech.com/{CIRCLE}/feed_detail?feeds_id={feeds_id}&app_id={APP_ID}"
    ws_send(s, json.dumps({"id": 60, "method": "Page.navigate", "params": {"url": url}, "sessionId": sess}))
    time.sleep(4.5)
    js = r"""
    (function(){
      function clean(t){return (t||'').replace(/\s+/g,' ').trim();}
      var h1 = clean((document.querySelector('h1')||{}).innerText);
      // 标题还可能不在 h1，取 article 内第一个大标题
      var title = document.title;
      var body = document.body.innerText;
      // 元信息：时间/作者
      var meta=[];
      document.querySelectorAll('[class]').forEach(function(el){
        var c=el.getAttribute('class')||'';
        if(/time|date|author|meta|publish|info/i.test(c)){
          var t=clean(el.innerText);
          if(t.length>0 && t.length<50) meta.push(t);
        }
      });
      // 正文容器：优先找带 content/article/richtext 的
      var main=document.querySelector('[class*=content],[class*=article],[class*=richtext],[class*=detail]');
      var mainText = main? clean(main.innerText): body;
      return JSON.stringify({title:title, h1:h1, meta:meta.slice(0,6), bodyLen:body.length, mainLen:(mainText||'').length, mainText:mainText.slice(0,12000)});
    })()
    """
    r = eval_js(s, sess, js, timeout=25)
    if not r:
        return None
    val = r.get('result', {}).get('result', {}).get('value', '')
    try:
        d = json.loads(val)
    except Exception:
        d = {"error": "parse", "raw": str(val)[:200]}
    d['feeds_id'] = feeds_id
    d['url'] = url
    return d

def run_links(s, sess):
    links = fetch_feed_links(s, sess)
    (OUT / "feed_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2))
    print(json.dumps(links, ensure_ascii=False, indent=2))
    print(f"\n已存 {len(links)} 条链接到 raw/xiaoe/feed_links.json", file=sys.stderr)
    return links

def run_crawl(s, sess):
    links = fetch_feed_links(s, sess)
    (OUT / "feed_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2))
    print(f"列表 {len(links)} 条", file=sys.stderr)
    results = []
    for i, lk in enumerate(links):
        print(f"爬取 {i+1}/{len(links)}: {lk['t']} ({lk['id']})", file=sys.stderr)
        d = fetch_detail(s, sess, lk['id'])
        if d:
            results.append(d)
        time.sleep(1.5)
    (OUT / "articles.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\n全量爬取完成，共 {len(results)} 篇，存至 raw/xiaoe/articles.json", file=sys.stderr)
    return results

def with_retry(fn, attempts=8):
    """整体重试：该 Chrome 的 CDP 连接时好时坏（疑似 WorkBuddy 后台共用通道，随机可用）。
    每次失败关闭连接、等待冷却、重新连接重试；撞上可用窗口后一气呵成。"""
    for attempt in range(1, attempts + 1):
        print(f"=== 尝试 {attempt}/{attempts} ===", file=sys.stderr)
        s = None
        try:
            s = ws_connect()
            sess = get_session(s)
            if not sess:
                print("DEBUG: 未获取 session", file=sys.stderr)
                continue
            result = fn(s, sess)
            print("OK", file=sys.stderr)
            return result
        except Exception as e:
            print(f"DEBUG: 异常 {type(e).__name__}: {e}", file=sys.stderr)
        finally:
            if s:
                try:
                    s.close()
                except Exception:
                    pass
        if attempt < attempts:
            wait = 6 * attempt  # 冷却递增
            print(f"冷却 {wait}s 后重试...", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"重试 {attempts} 次仍失败")

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "links"
    try:
        if mode == "links":
            with_retry(run_links)
        elif mode == "detail":
            fid = sys.argv[2]
            with_retry(lambda s, sess: print(json.dumps(fetch_detail(s, sess, fid), ensure_ascii=False, indent=2)[:3000]))
        elif mode == "crawl":
            with_retry(run_crawl)
        else:
            print(__doc__)
    except RuntimeError as e:
        print(f"FAILED: {e}", file=sys.stderr)
        sys.exit(1)
