#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CDP (Chrome DevTools Protocol) 控制脚本 —— 接管已开 Chrome (127.0.0.1:9222)。
说明：该 Chrome 的 /json HTTP 端点被关闭，只能走 WebSocket 直连。
本脚本封装：连浏览器、列 targets、attach 页面、执行 JS、抓 DOM 文本。

用法：
  python3 cdp_chrome.py list                      # 列出所有 page target
  python3 cdp_chrome.py find <keyword>            # 按关键词找 target
  python3 cdp_chrome.py attach <targetId> eval <js>   # attach 后执行 JS
  python3 cdp_chrome.py attach <targetId> snapshot      # 抓 body 文本+链接
"""
import socket, base64, os, json, struct, time, sys

CDP_HOST = "127.0.0.1"
CDP_PORT = 9222

def ws_connect(path="/devtools/browser"):
    key = base64.b64encode(os.urandom(16)).decode()
    req = (f"GET {path} HTTP/1.1\r\nHost: {CDP_HOST}:{CDP_PORT}\r\n"
           "Upgrade: websocket\r\nConnection: Upgrade\r\n"
           f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n"
           "Sec-WebSocket-Protocol: chrome-devtools\r\n\r\n")
    s = socket.create_connection((CDP_HOST, CDP_PORT), timeout=8)
    s.sendall(req.encode())
    hdr = b''
    while b'\r\n\r\n' not in hdr and len(hdr) < 8192:
        hdr += s.recv(1)
    assert b'101' in hdr, hdr[:200]
    return s

def ws_recv_frame(s, timeout=8):
    s.settimeout(timeout)
    try:
        data = s.recv(2)
    except socket.timeout:
        return None
    if len(data) < 2:
        return None
    opcode = data[0] & 0x0f
    length = data[1] & 0x7f
    if length == 126:
        length = struct.unpack('>H', s.recv(2))[0]
    elif length == 127:
        length = struct.unpack('>Q', s.recv(8))[0]
    payload = b''
    while len(payload) < length:
        c = s.recv(length - len(payload))
        if not c:
            break
        payload += c
    return payload.decode('utf-8', 'replace')

def ws_send(s, msg):
    p = msg.encode('utf-8')
    L = len(p)
    h = bytearray([0x81])
    if L < 126:
        h.append(0x80 | L)
    elif L < 65536:
        h.append(0x80 | 126); h += struct.pack('>H', L)
    else:
        h.append(0x80 | 127); h += struct.pack('>Q', L)
    m = os.urandom(4)
    mk = bytes(b ^ m[i % 4] for i, b in enumerate(p))
    s.sendall(bytes(h) + m + mk)

class CDP:
    def __init__(self, s):
        self.s = s
        self._id = 0
    def cmd(self, method, params=None, timeout=10):
        self._id += 1
        msg = {"id": self._id, "method": method, "params": params or {}}
        ws_send(self.s, json.dumps(msg))
        buf = ""
        dl = time.time() + timeout
        while time.time() < dl:
            f = ws_recv_frame(self.s, timeout=2)
            if f:
                buf += f
                # 找匹配 id 的响应
                try:
                    d = json.loads(buf)
                    if d.get("id") == self._id:
                        return d
                except Exception:
                    pass
                if buf.strip().endswith('}') and '"id":%d' % self._id in buf:
                    try:
                        return json.loads(buf)
                    except Exception:
                        pass
            else:
                if buf:
                    break
        return None

def list_targets():
    s = ws_connect()
    c = CDP(s)
    d = c.cmd("Target.getTargets", {})
    s.close()
    if not d:
        return []
    return [t for t in d['result']['targetInfos'] if t.get('type') in ('page', 'webview')]

def find_target(keyword):
    k = keyword.lower()
    for t in list_targets():
        if k in t.get('url', '').lower() or k in t.get('title', '').lower():
            return t
    return None

def attach_and_eval(target_id, js, timeout=15):
    s = ws_connect()
    c = CDP(s)
    # 用.flat 方式：直接创建 session
    r = c.cmd("Target.attachToTarget", {"targetId": target_id, "flatten": True})
    if not r or "result" not in r:
        s.close(); return None
    session = r['result']['sessionId']
    # 通过 session 发 Runtime.evaluate
    c._id += 1
    msg = {"id": c._id, "method": "Runtime.evaluate",
           "params": {"expression": js, "returnByValue": True,
                      "awaitPromise": True}, "sessionId": session}
    ws_send(s, json.dumps(msg))
    buf = ""; dl = time.time() + timeout
    while time.time() < dl:
        f = ws_recv_frame(s, timeout=3)
        if f:
            buf += f
            try:
                d = json.loads(buf)
                if d.get("id") == c._id:
                    s.close()
                    return d
            except Exception:
                pass
        else:
            if buf:
                break
    s.close()
    return None

if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__); sys.exit(0)
    if args[0] == "list":
        for t in list_targets():
            print(f"{t['targetId']}  |  {t.get('title','')[:40]:<40}  |  {t.get('url','')[:60]}")
    elif args[0] == "find":
        kw = args[1] if len(args) > 1 else "xiaoe"
        t = find_target(kw)
        if t:
            print(f"FOUND targetId={t['targetId']}")
            print(f"  title: {t.get('title','')}")
            print(f"  url:   {t.get('url','')}")
        else:
            print(f"未找到含 '{kw}' 的页面")
    elif args[0] == "attach" and len(args) >= 4 and args[2] == "eval":
        tid = args[1]; js = args[3]
        r = attach_and_eval(tid, js)
        print(json.dumps(r, ensure_ascii=False, indent=2) if r else "无响应")
    elif args[0] == "attach" and len(args) >= 3 and args[2] == "snapshot":
        tid = args[1]
        js = """(() => {
          const body = document.body;
          const text = body.innerText;
          const links = Array.from(document.querySelectorAll('a[href]')).map(a=>({t:a.innerText.trim().slice(0,60), h:a.href})).slice(0,50);
          return JSON.stringify({title:document.title, url:location.href, len:text.length, text:text.slice(0,8000), links});
        })()"""
        r = attach_and_eval(tid, js)
        if r and 'result' in r:
            res = r['result'].get('result', {}).get('value')
            try:
                data = json.loads(res)
                print(f"标题: {data['title']}")
                print(f"URL:  {data['url']}")
                print(f"文本长度: {data['len']}")
                print("=== 正文前 8000 字 ===")
                print(data['text'])
                print("\n=== 链接样本 ===")
                for l in data['links'][:15]:
                    print(f"  {l['t']} -> {l['h']}")
            except Exception as e:
                print("解析结果失败:", e, res[:500] if res else '')
        else:
            print("快照失败:", r)
    else:
        print(__doc__)
