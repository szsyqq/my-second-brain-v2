#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小鹅通「16号内参」圈子全量抓取脚本（一键版，无需人工交互）。
连接策略：该 Chrome(9222) 的 CDP 连接"时好时坏"——握手常成功但命令响应偶发丢失。
因此：连接/命令失败→关闭→等待→重试，一旦 getTargets 成功则整个会话内连续操作。
输出：raw/xiaoe/articles.json + raw/xiaoe/文章/XX.md（每篇一个 Markdown，便于收录 wiki）

用法：python3 xiaoe_full_crawl.py
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

# ---------- 基础 WS ----------
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
    if opcode == 9:  # ping
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

# ---------- CDP 会话 ----------
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

def attach(s):
    r = cmd(s, "Target.getTargets", {}, timeout=15)
    if not r or 'result' not in r:
        return None
    tids = [t for t in r['result']['targetInfos'] if 'quanzi.xiaoe' in t.get('url', '')]
    if not tids:
        return None
    tid = tids[0]['targetId']
    r = cmd(s, "Target.attachToTarget", {"targetId": tid, "flatten": True}, timeout=15)
    if not r or 'result' not in r or 'sessionId' not in r.get('result', {}):
        # 有些版本 attach 返回事件而非 result，尝试在事件里找
        return None
    return r['result']['sessionId']

def attach_via_event(s):
    """attachToTarget 的响应可能以事件 Target.attachedToTarget 推送，需专门读取。"""
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

def eval_js(s, sess, js, timeout=20):
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
                    return d
            except Exception:
                pass
    return None

def ev(s, sess, js, timeout=20):
    r = eval_js(s, sess, js, timeout=timeout)
    if not r:
        return None
    v = r.get('result', {}).get('result', {}).get('value')
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return v
    return v

# ---------- 业务 ----------
def ensure_feed_list(s, sess):
    """确保页面在 feed_list 且已渲染。"""
    feed_url = f"https://quanzi.xiaoe-tech.com/{CIRCLE}/feed_list?app_id={APP_ID}"
    cur = ev(s, sess, "location.href", timeout=8)
    if cur and 'feed_list' in str(cur):
        scroll_feed(s, sess)
        return True
    # 不在列表页则导航
    _cid[0] += 1
    ws_send(s, json.dumps({"id": _cid[0], "method": "Page.navigate",
                           "params": {"url": feed_url}, "sessionId": sess}))
    for _ in range(15):
        time.sleep(2)
        st = ev(s, sess, "JSON.stringify({u:location.href,n:document.body.innerText.length})", timeout=8)
        if st and 'feed_list' in str(st.get('u', '')) and st.get('n', 0) > 1000:
            scroll_feed(s, sess)
            return True
    return False

def scroll_feed(s, sess):
    """分次滚动 + 点击'加载更多'，每次等待渲染，触发懒加载全部 feed。"""
    for rnd in range(10):
        # 滚动到底
        ev(s, sess, "(function(){for(var i=0;i<8;i++){window.scrollTo(0,document.body.scrollHeight);var sc=document.querySelector('[class*=scroll],[class*=list],[class*=feed]');if(sc)sc.scrollTop=sc.scrollHeight;window.scrollBy(0,-300);}}return 1;})()", timeout=12)
        # 找"加载更多/查看更多"按钮并点击
        ev(s, sess, "(function(){var els=Array.from(document.querySelectorAll('button,a,div,span'));for(var i=0;i<els.length;i++){var t=(els[i].innerText||'').trim();if(/加载更多|查看更多|load.?more/i.test(t)&&t.length<20){els[i].click();return 1;}}return 0;})()", timeout=8)
        time.sleep(2.5)

def fetch_links(s, sess):
    js = r"""
    (function(){
      var seen={}; var links=[];
      Array.from(document.querySelectorAll('a')).forEach(function(a){
        var h=a.href||''; var m=h.match(/feeds_id=(d_\w+)/);
        if(m && !seen[m[1]]){ seen[m[1]]=1; var t=a.innerText.trim();
          links.push({id:m[1], t:t.length>6?t.slice(0,60):'', h:h}); }
      });
      return JSON.stringify({n:links.length, links:links});
    })()
    """
    r = ev(s, sess, js, timeout=15)
    return r.get('links', []) if r else []

def fetch_detail(s, sess, feeds_id):
    url = f"https://quanzi.xiaoe-tech.com/{CIRCLE}/feed_detail?feeds_id={feeds_id}&app_id={APP_ID}"
    _cid[0] += 1
    ws_send(s, json.dumps({"id": _cid[0], "method": "Page.navigate",
                           "params": {"url": url}, "sessionId": sess}))
    # 轮询等待正文渲染（最多 25 秒）
    ok = False
    for _ in range(12):
        time.sleep(2)
        st = ev(s, sess, "JSON.stringify({n:document.body.innerText.length, r:document.readyState})", timeout=8)
        if st and st.get('n', 0) > 2000:
            ok = True
            break
    if not ok:
        time.sleep(3)
    js = r"""
    (function(){
      function clean(t){return (t||'').replace(/\s+/g,' ').trim();}
      var title = document.title;
      var h1 = clean((document.querySelector('h1')||{}).innerText);
      var body = document.body.innerText;
      var meta=[];
      document.querySelectorAll('[class]').forEach(function(el){
        var c=el.getAttribute('class')||'';
        if(/time|date|author|meta|publish|info/i.test(c)){
          var t=clean(el.innerText);
          if(t.length>0 && t.length<50) meta.push(t);
        }
      });
      var main=document.querySelector('[class*=content],[class*=article],[class*=richtext],[class*=detail]');
      var mainText = main? clean(main.innerText): body;
      return JSON.stringify({title:title, h1:h1, meta:meta.slice(0,6),
                             bodyLen:body.length, mainLen:(mainText||'').length,
                             mainText:(mainText||'').slice(0,50000)});
    })()
    """
    r = ev(s, sess, js, timeout=20)
    if not r:
        return None
    r['feeds_id'] = feeds_id
    r['url'] = url
    return r

def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|\s]+', '_', name)
    return name.strip('_')[:80] or 'untitled'

# ---------- 主流程 ----------
def main():
    print("=== 小鹅通 16号内参 全量抓取 ===", flush=True)
    total_attempts = 12
    for attempt in range(1, total_attempts + 1):
        print(f"[尝试 {attempt}/{total_attempts}] 连接 CDP...", flush=True)
        s = ws_connect()
        if not s:
            print("  连接失败，等待重试", flush=True)
            time.sleep(8)
            continue
        try:
            tid, sess = attach_via_event(s)
            if not sess:
                print("  attach 失败（可能连接不稳）", flush=True)
                s.close()
                time.sleep(6)
                continue
            print("  attach 成功，确认列表页...", flush=True)
            ok = ensure_feed_list(s, sess)
            if not ok:
                print("  列表页未就绪", flush=True)
                s.close()
                time.sleep(6)
                continue
            links = fetch_links(s, sess)
            print(f"  抓到 {len(links)} 篇文章链接", flush=True)
            if not links:
                s.close()
                time.sleep(6)
                continue
            # 保存链接
            (OUT / "feed_links.json").write_text(json.dumps(links, ensure_ascii=False, indent=2))
            # 逐篇抓详情
            results = []
            for i, lk in enumerate(links):
                print(f"  [{i+1}/{len(links)}] {lk['t'] or lk['id']}", flush=True)
                d = None
                for try2 in range(2):  # 单篇重试
                    d = fetch_detail(s, sess, lk['id'])
                    if d and d.get('mainLen', 0) > 200:
                        break
                    time.sleep(2)
                if d:
                    results.append(d)
                    # 写 Markdown
                    title = d.get('h1') or d.get('title') or lk['t'] or lk['id']
                    md = f"# {title}\n\n"
                    md += f"> 来源：小鹅通圈子「16号内参——拾榴询财小密圈」\n"
                    md += f"> 链接：{d.get('url','')}\n"
                    if d.get('meta'):
                        md += f"> 元信息：{'；'.join(d['meta'])}\n"
                    md += f"> 抓取时间：{time.strftime('%Y-%m-%d %H:%M')}\n\n"
                    md += "---\n\n"
                    md += (d.get('mainText') or '')
                    fname = f"{i+1:02d}_{sanitize(title)}.md"
                    (ART / fname).write_text(md, encoding='utf-8')
                time.sleep(1.5)
            # 保存 JSON
            (OUT / "articles.json").write_text(json.dumps(results, ensure_ascii=False, indent=2))
            print(f"\n✅ 完成：共 {len(results)} 篇", flush=True)
            print(f"   JSON: raw/xiaoe/articles.json", flush=True)
            print(f"   Markdown: raw/xiaoe/文章/（{len(results)} 个文件）", flush=True)
            s.close()
            return
        except Exception as e:
            print(f"  异常：{type(e).__name__}: {e}", flush=True)
            try:
                s.close()
            except Exception:
                pass
            time.sleep(8)
    print("❌ 多次尝试后仍未成功，请检查 Chrome 是否仍打开小鹅通页面", flush=True)
    sys.exit(1)

if __name__ == "__main__":
    main()
