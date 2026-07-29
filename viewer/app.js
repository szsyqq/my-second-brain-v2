
// Show loading state immediately
(function() {
  var el = document.getElementById("empty-state");
  if (el) el.innerHTML = '<div style="padding:80px 20px;text-align:center;color:var(--text3)"><div style="font-size:14px;margin-bottom:8px">⏳ 正在加载知识库…</div><div style="font-size:12px;color:var(--text3)">首次加载需下载数据，请稍候</div></div>';
})();

// Global severity maps (used by renderTree/renderTreeInto/applyUpdateTags)
var sevMap = {new:'tag-new',updated:'tag-updated',major:'tag-major',viewpoint:'tag-viewpoint'};
var sevLabel = {new:'新增',updated:'更新',major:'重点更新',viewpoint:'观点改变'};
var fileTree = null;  // set in initAll()

// System monitor version data (injected at build time)
var SYS_VERSIONS = {};
// System monitor workflow links (injected at build time) — click a version to open its source
var SYS_WORKFLOW_LINKS = {"page":"","schema":{},"skills":{}};
// System monitor workflow markdown content (injected) — rendered in-page, no download
var SYS_WORKFLOW_CONTENT = {"page":"","schema":{},"skills":{}};
// System monitor update footnotes (injected) — last-updated time + what changed
var SYS_UPDATES = {"page":null,"schema":{},"skills":{}};

// Marked setup
marked.setOptions({breaks:true,gfm:true});
// Wrap tables in a responsive container for mobile horizontal scroll
var defaultTableRenderer = marked.Renderer.prototype.table;
marked.Renderer.prototype.table = function(header, body) {
  return '<div style="overflow-x:auto;-webkit-overflow-scrolling:touch;margin:10px 0;max-width:100%"><table style="min-width:100%">' + header + body + '</table></div>';
};

// === Compatibility polyfills (Safari / old Firefox safety) ===
// Some browsers lack NodeList/Element.forEach; openPage() relies on it when
// post-processing links, so a missing polyfill throws on click → blank right pane.
if (typeof NodeList !== "undefined" && !NodeList.prototype.forEach) {
  NodeList.prototype.forEach = Array.prototype.forEach;
}
if (typeof Element !== "undefined" && !Element.prototype.forEach) {
  Element.prototype.forEach = Array.prototype.forEach;
}
if (typeof window !== "undefined" && !window.requestAnimationFrame) {
  window.requestAnimationFrame = function(cb){ return setTimeout(cb, 16); };
}

// === file:// protocol guard: detect local double-click (path contains #) ===
// When the file is opened via file:// with a path containing #, the browser
// truncates at the # and shows a directory listing instead of the real page.
// This check fires early and warns the user.
(function(){
  if (location.protocol === "file:" && location.pathname.indexOf("#") >= 0) {
    document.addEventListener("DOMContentLoaded", function(){
      var ca = document.getElementById("content-area");
      if (!ca) return;
      ca.innerHTML = '<div style="padding:40px;color:#c0392b;font-family:sans-serif;text-align:center;line-height:2">' +
        '<div style="font-size:20px;font-weight:700;margin-bottom:12px">🚫 无法在本地打开</div>' +
        '<p>由于文件路径中包含 <code>#</code> 字符，浏览器无法正确加载此页面。</p>' +
        '<p>请使用以下方式访问：</p>' +
        '<p style="margin-top:14px"><b>方式一（推荐）：</b><br>' +
        '<a href="https://1ee078db29c64e80b32de54eb5a6e44f.app.codebuddy.work/" style="color:#cb6e3e">打开线上版本 ↗</a></p>' +
        '<p><b>方式二（本地）：</b><br>在终端中运行：<br>' +
        '<code style="background:#f0ece4;padding:4px 10px;border-radius:4px;font-size:14px">cd 小红书收藏/ && python3 -m http.server 8753</code><br>' +
        '然后访问 <a href="http://127.0.0.1:8753/知识库.html" style="color:#cb6e3e">http://127.0.0.1:8753/知识库.html</a></p>' +
        '<div style="margin-top:20px;font-size:12px;color:#888">请不要双击 HTML 文件打开。</div>' +
        '</div>';
    });
  }
})();

// Build version (replaced at build time) — used to bust the bundle cache.
var BUILD_VERSION = window.BUILD_VERSION || "dev";

// === Visible error reporting: turns a silent blank pane into a readable message ===
function showFatal(title, detail){
  var ca = document.getElementById("content-area");
  if (!ca) return;
  var msg = String(detail == null ? "" : detail).replace(/</g, "&lt;").replace(/>/g, "&gt;");
  ca.innerHTML = '<div style="padding:28px;color:#c0392b;font-family:ui-monospace,Menlo,Consolas,monospace;white-space:pre-wrap;font-size:13px;line-height:1.6">' +
    '<div style="font-size:15px;font-weight:600;margin-bottom:10px">⚠️ ' + title + '</div>' +
    '<div>' + msg + '</div>' +
    '<div style="margin-top:14px;color:#888;font-size:12px">请把以上红色文字截图或复制发给我，即可定位并修复问题。</div>' +
    '</div>';
}
window.addEventListener("error", function(e){
  // Ignore resource load errors (broken <img>/<link>) — only surface script errors.
  if (e && e.target && e.target !== window && (e.target.src || e.target.href)) return;
  var d = (e && e.error && e.error.stack) ? e.error.stack : (e && e.message ? e.message : "未知错误");
  showFatal("页面渲染出错（运行时异常）", d);
});
window.addEventListener("unhandledrejection", function(e){
  var r = e && e.reason;
  showFatal("未处理的 Promise 异常", (r && r.stack) ? r.stack : (r && r.message ? r.message : r));
});

// === Render visibility self-check (v1.14.1) ===
// If content is in the DOM but invisible (CSS var / layout issue), surface it.
function selfCheckContent(context){
  try {
    var ca = document.getElementById("content-area");
    if (!ca || ca.innerHTML.length < 50) return;
    var cs = getComputedStyle(ca);
    var info = {
      ctx: context,
      display: cs.display,
      visibility: cs.visibility,
      height: Math.round(ca.getBoundingClientRect().height),
      color: cs.color,
      bg: cs.backgroundColor
    };
    var txt = ca.querySelector("h1,h2,h3,p,li,div,span");
    if (txt) {
      var tcs = getComputedStyle(txt);
      info.firstTextColor = tcs.color;
      info.firstTextOpacity = tcs.opacity;
    }
    var invisible = (info.display === "none") || (info.visibility === "hidden") ||
                    (info.height < 5) || (info.firstTextOpacity === "0") ||
                    (info.firstTextColor === "rgba(0, 0, 0, 0)") || (info.firstTextColor === "transparent");
    if (invisible) {
      var box = document.createElement("div");
      box.style.cssText = "position:fixed;bottom:12px;right:12px;z-index:99999;max-width:440px;max-height:60vh;overflow:auto;background:#fff8ef;border:2px solid #e67e22;border-radius:8px;padding:14px;color:#c0392b;font:12px/1.5 ui-monospace,Menlo,monospace;box-shadow:0 4px 20px rgba(0,0,0,.2)";
      box.innerHTML = "<b>⚠️ 内容已渲染但不可见（疑似 CSS 问题）</b><br><br>" +
        '<pre style="white-space:pre-wrap;margin:0">' + JSON.stringify(info, null, 2).replace(/</g, "&lt;") + "</pre><br>" +
        '<span style="color:#888">请把以上信息截图发给我即可定位。</span>';
      document.body.appendChild(box);
    }
  } catch (e) { /* ignore */ }
}

// Display-name overrides for top-level navigation entries
function displayName(name){
  if (name === "index") return "目录";
  if (name === "overview") return "概览";
  return name;
}

// Build an onclick attribute that opens a page (slug safely escaped)
function pageClickAttr(slug){
  var s = (slug||"").replace(/'/g, "\\'");
  return "onclick=\"openPage('" + s + "')\"";
}

// Build file tree (called after data loads)
var currentUpdateTab = 'all';
function getStrategySlugs() {
  var slugs = {};
  for (var s in files) {
    if (s.indexOf('topics/02_') === 0) { slugs[s] = true; }
  }
  return slugs;
}
function getFilteredStrategyRecords() {
  var slugs = getStrategySlugs();
  return updateRecords.filter(function(rec) {
    var pages = rec.affected_pages || [];
    return pages.some(function(p) { return slugs[p.slug]; });
  });
}
function switchUpdateTab(tab) {
  currentUpdateTab = tab;
  var tabs = document.querySelectorAll('.upd-tab');
  for (var i = 0; i < tabs.length; i++) {
    tabs[i].style.borderBottomColor = 'transparent';
    tabs[i].style.color = 'var(--text2)';
    tabs[i].style.fontWeight = 'normal';
  }
  var active = document.getElementById('upd-tab-' + tab);
  if (active) {
    active.style.borderBottomColor = 'var(--accent)';
    active.style.color = 'var(--text)';
    active.style.fontWeight = '600';
  }
  renderUpdateRecords();
}

function initAll() {
  fileTree = document.getElementById("file-tree");
function fileDisplayName(name){
  var m = displayName(name);
  if (m !== name) return m;
  return name.replace(/\.md$/,"").replace(/_/g," ");
}

function renderTree(node, depth, parentPath) {
  var indent = "&nbsp;".repeat(depth * 4);
  var folderEmoji = node.emoji || "";
  if (node.type === "folder" || node.children) {
    var div = document.createElement("div");
    div.className = "tree-folder";
    div.style.paddingLeft = (depth * 18 + 4) + "px";
    var label = (folderEmoji ? folderEmoji + " " : "") + node.name;
    div.innerHTML = '<span class="tree-arrow">▸</span>' + label;
    var children = document.createElement("div");
    children.style.display = "none";
    (function(currentDiv, currentChildren) {
      currentDiv.onclick = function(e) {
        e.stopPropagation();
        var isOpen = currentChildren.style.display !== "none";
        currentChildren.style.display = isOpen ? "none" : "";
        currentDiv.querySelector(".tree-arrow").textContent = isOpen ? "▸" : "▾";
      };
    })(div, children);
    fileTree.appendChild(div);
    fileTree.appendChild(children);
    if (node.children) {
      node.children.forEach(function(child) {
        renderTreeInto(child, depth + 1, children);
      });
    }
  } else {
    var div = document.createElement("div");
    div.className = "tree-file";
    div.style.paddingLeft = (depth * 18 + 20) + "px";
    div.setAttribute("data-slug", node.slug);
    if (node.is_hub) div.setAttribute("data-is-hub", "1");
    var mark = node.is_hub ? '<span class="hub-mark">●</span> ' : '';
    var sev = node.update_severity;
    var upd = sev ? ' <span class="update-tag '+sevMap[sev]+'">'+sevLabel[sev]+'</span>' : '';
    div.innerHTML = mark + '<span class="tree-file-name">' + fileDisplayName(node.name) + '</span>' + upd;
    (function(slug, el) {
      div.onclick = function(e) { e.stopPropagation(); openPage(slug); };
    })(node.slug, div);
    fileTree.appendChild(div);
  }
}
function renderTreeInto(node, depth, parent) {
  if (node.type === "folder" || node.children) {
    var div = document.createElement("div");
    div.className = "tree-folder";
    div.style.paddingLeft = (depth * 18 + 4) + "px";
    var label2 = (node.emoji ? node.emoji + " " : "") + node.name;
    div.innerHTML = '<span class="tree-arrow">▸</span>' + label2;
    var children = document.createElement("div");
    children.style.display = "none";
    (function(currentDiv, currentChildren) {
      currentDiv.onclick = function(e) {
        e.stopPropagation();
        var isOpen = currentChildren.style.display !== "none";
        currentChildren.style.display = isOpen ? "none" : "";
        currentDiv.querySelector(".tree-arrow").textContent = isOpen ? "▸" : "▾";
      };
    })(div, children);
    parent.appendChild(div);
    parent.appendChild(children);
    if (node.children) {
      node.children.forEach(function(child) { renderTreeInto(child, depth + 1, children); });
    }
  } else {
    var div = document.createElement("div");
    div.className = "tree-file";
    div.style.paddingLeft = (depth * 18 + 20) + "px";
    div.setAttribute("data-slug", node.slug);
    if (node.is_hub) div.setAttribute("data-is-hub", "1");
    var mark2 = node.is_hub ? '<span class="hub-mark">●</span> ' : '';
    var sev2 = node.update_severity;
    var upd2 = sev2 ? ' <span class="update-tag '+sevMap[sev2]+'">'+sevLabel[sev2]+'</span>' : '';
    div.innerHTML = mark2 + '<span class="tree-file-name">' + fileDisplayName(node.name) + '</span>' + upd2;
    (function(slug, el) {
      div.onclick = function(e) { e.stopPropagation(); openPage(slug); };
    })(node.slug, div);
    parent.appendChild(div);
  }
}
if (tree.children) tree.children.forEach(function(c) { renderTree(c, 0, ""); });

// Auto-apply update tags from all records (newest first) so the sidebar reflects recent changes
autoApplyAllTags();

// Auto-expand folders at startup
setTimeout(function() {
  fileTree.querySelectorAll(".tree-folder").forEach(function(f) {
    var next = f.nextElementSibling;
    if (!next) return;
    var collapsed = (f.textContent.indexOf("sources") >= 0 || f.textContent.indexOf("entities") >= 0);
    if (collapsed) {
      if (next.style.display !== "none") { f.click(); }
    } else {
      if (next.style.display === "none") { f.click(); }
    }
  });
}, 120);

showHome();
setTimeout(function(){ try{ initGraph(); }catch(e){} }, 300);
}

// Async load wiki-bundle.json (versioned query busts CDN/browser cache on each deploy)
fetch("wiki-bundle.json?v=" + BUILD_VERSION)
  .then(function(r) { return r.json(); })
  .then(function(data) {
    window.wiki = data;
    window.files = data.files;
    window.tree = data.tree;
    // Put "index" (目录) at the front of the top-level navigation
    if (window.tree && window.tree.children) {
      var _idx = -1;
      for (var _i = 0; _i < window.tree.children.length; _i++) {
        if (window.tree.children[_i].name === "index") { _idx = _i; break; }
      }
      if (_idx > 0) { window.tree.children.unshift(window.tree.children.splice(_idx, 1)[0]); }
    }
    window.graphData = data.graph;
    window.allSlugs = Object.keys(data.files).filter(function(s){ return !(data.files[s] && data.files[s].hidden); });
    updateRecords = data.update_records || [];
    window.inboxData = data.inbox || {items:[], total:0, groups:{}, generated_at:""};
    var ib = document.getElementById("inbox-badge");
    if (ib) ib.textContent = window.inboxData.total ? window.inboxData.total : "";
    initAll();
    // Load full content in background for on-demand page rendering
    fetch("wiki-content.json?v=" + BUILD_VERSION)
      .then(function(r) { return r.json(); })
      .then(function(contentData) {
        window._wikiContent = contentData;
        for (var s in contentData) {
          if (window.files[s]) {
            window.files[s].content = contentData[s].content;
            window.files[s].history = contentData[s].history || [];
          }
        }
      })
      .catch(function(e) {
        console.warn("Content bundle not loaded", e);
      });
  })
  .catch(function(err) {
    document.getElementById("content-area").innerHTML = '<div style="padding:80px;text-align:center;color:red">⚠️ 加载失败: ' + err.message + '<br><small>请检查 wiki-bundle.json 是否存在</small></div>';
  });

// --- Version button: toggle "应用更新记录" page ---
// First click opens the app update log; second click (while on that page) returns to the previous page (or home).
var APP_UPDATE_SLUG = "应用更新记录";
function toggleAppUpdate() {
  var cur = window._currentSlug || "";
  if (cur === APP_UPDATE_SLUG) {
    var prev = window._appUpdateReturnSlug;
    if (prev && prev !== APP_UPDATE_SLUG && files[prev]) openPage(prev);
    else showHome();
  } else {
    window._appUpdateReturnSlug = cur;
    openPage(APP_UPDATE_SLUG);
  }
}

// --- Page rendering ---
// Safety wrapper: any error in openPage is caught and displayed.
// This is the SECOND line of defense (after selfCheckContent + showFatal).
// openPage now delegates to _openPageImpl inside a try/catch.



function openPage(slug, hash) {
  try {
    _openPageImpl(slug, hash);
  } catch(e) {
    try {
      document.getElementById("content-area").innerHTML = '<div style="padding:40px;color:#c0392b;font-family:sans-serif;line-height:1.8">' +
        '<div style="font-size:16px;font-weight:700;margin-bottom:8px">⚠️ 页面渲染出错</div>' +
        '<div style="font-size:13px;color:#555">' + String(e && e.message ? e.message : e).replace(/</g,"&lt;").replace(/>/g,"&gt;") + '</div>' +
        '<div style="margin-top:12px;font-size:12px;color:#999">请把以上文字截图发给我，即可定位并修复问题。</div></div>';
    } catch(e2) { /* last resort — nothing we can do */ }
  }
}
function _openPageImpl(slug, hash) {
  var info = files[slug];
  if (!info) {
    document.getElementById("content-area").innerHTML = '<div style="padding:40px;color:var(--text3)">⚠️ 页面未找到: ' + slug.replace(/</g,"&lt;") + '</div>';
    return;
  }
  try {
    var content = info.content;
    if (!content) {
      document.getElementById("content-area").innerHTML = '<div style="padding:40px;text-align:center;color:var(--text3)"><div style="font-size:40px;margin-bottom:16px">\u23f3</div><div style="font-size:14px">正在加载页面内容\u2026</div><div style="font-size:12px;margin-top:8px">内容数据下载完成后自动显示</div></div>';
      var _check_interval = setInterval(function() {
        if (window.files[slug] && window.files[slug].content) {
          clearInterval(_check_interval);
          _openPageImpl(slug, hash);
        }
      }, 200);
      return;
    }
    window._currentSlug = slug;
    window._currentHistory = info.history || [];
    // Auto-pop update drawer for pages with update severity
    if (info.update_severity) {
      setTimeout(function() { openPageUpdateHistory(); }, 100);
    }

    // Render markdown first, then SANITIZE (F-01/F-02):
    // DOMPurify strips dangerous raw HTML from notes (e.g. <img onerror>, <svg onload>)
    // BEFORE we inject our own wiki-link anchors, so the onclick handlers survive sanitization.
    var html = DOMPurify.sanitize(marked.parse(content), { ADD_ATTR: ['target'] });

    // Convert [[wikilinks]] to clickable spans or styled placeholders (on sanitized HTML)
    html = html.replace(/\[\[([^\]]+)\]\]/g, function(m, target) {
      var parts = target.split("|");
      var parts_0_hash = parts[0].split("#");
      var cleanTarget = parts_0_hash[0].trim();
      var hashTarget = parts_0_hash.length > 1 ? parts_0_hash.slice(1).join("#") : "";
      var resolved = resolveSlug(cleanTarget);
      if (resolved && files[resolved]) {
        var onclick = 'event.stopPropagation();openPage(\'' + resolved.replace(/'/g,"\\'") + '\'';
        if (hashTarget) onclick += ',\'' + hashTarget.replace(/'/g,"\\'") + '\'';
        onclick += ')';
        return '<a class="wiki-link" onclick="' + onclick + '" title="' + cleanTarget.replace(/"/g,'&quot;') + '">' + target.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</a>';
      }
      // For unresolved links that look like file paths (raw/processed/...), show as styled badge
      if (/^(raw\/|\.\/|\/)/.test(cleanTarget) || cleanTarget.endsWith(".md") || cleanTarget.includes("/")) {
        var fileName = cleanTarget.split("/").pop().replace(/\.md$/, "");
        return '<span style="color:var(--text3);font-size:12px;background:var(--bg2);padding:1px 6px;border-radius:4px;border:1px solid var(--border)" title="原始素材: ' + cleanTarget.replace(/"/g,'&quot;') + '">📎 ' + fileName.replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</span>';
      }
      return '<span style="color:#bbb">[[' + target.replace(/</g,'&lt;').replace(/>/g,'&gt;') + ']]</span>';
    });

    // Post-process: add target="_blank" to all external links + style them
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = html;
    tempDiv.querySelectorAll('a[href]').forEach(function(a) {
      var href = a.getAttribute('href');
      if (/^https?:\/\//.test(href)) {
        a.setAttribute('target', '_blank');
        a.setAttribute('rel', 'noopener noreferrer');
        a.classList.add('ext-link');
        // Truncate very long URLs for display
        if (a.textContent.length > 80 && a.textContent === href) {
          a.textContent = href.substring(0, 75) + '…';
        }
      }
    });
    html = tempDiv.innerHTML;

    // Check if diff data exists → add diff banner
    var dd = info.diff_data;
    if (dd) {
      var banner = '<div class="diff-banner" id="diff-banner">';
      var badgeText = dd.type === "new" ? "新增页面" : dd.type === "updated" ? "内容已更新" : dd.type === "metadata_only" ? "元数据更新" : "内容已更新";
      banner += '<span class="badge">' + badgeText + '</span>';
      if (dd.type === "updated" || dd.type === "new") {
        var addCount = (dd.segments||[]).filter(function(s){return s.type==="add"}).length;
        var delCount = (dd.segments||[]).filter(function(s){return s.type==="del"}).length;
        if (dd.type === "updated") {
          var bannerTime = '';
          if (info.mtime) {
            var bt = new Date(info.mtime * 1000);
            var byy = bt.getFullYear();
            var bmm = String(bt.getMonth()+1).padStart(2,"0");
            var bdd = String(bt.getDate()).padStart(2,"0");
            var bhh = String(bt.getHours()).padStart(2,"0");
            var bmn = String(bt.getMinutes()).padStart(2,"0");
            bannerTime = ' · ' + byy + '-' + bmm + '-' + bdd + ' ' + bhh + ':' + bmn;
          }
          banner += '<span style="font-size:12px;color:var(--text3)">+' + addCount + ' 行 / -' + delCount + ' 行' + bannerTime + '</span>';
        }
        banner += '<button onclick="toggleDiffView()" id="diff-toggle-btn">📋 查看更新对比</button>';
      }
      banner += '</div>';
      // Store diff data for toggle
      window._currentDiff = dd;
      html = banner + html;
    } else {
      window._currentDiff = null;
    }

    document.getElementById("content-area").innerHTML = html;
    enhanceMustRead();
    selfCheckContent("page");
    window._originalHtml = html; // save for toggle back
    window._diffViewOn = false;

    // Update breadcrumb: clickable parent links
    var parts = slug.split("/");
    var bc = "";
    for (var i = 0; i < parts.length; i++) {
      if (i > 0) bc += '<span>/</span>';
      if (i < parts.length - 1) {
        // Parent segment → try to find the hub page for this folder
        var parentPath = parts.slice(0, i + 1).join("/");
        var hubCandidate = parentPath + "/" + parts[i];   // e.g. topics/02_投资/02_投资
        var altCandidate = parentPath;                     // e.g. topics/02_投资
        var target = files[hubCandidate] ? hubCandidate : (files[altCandidate] ? altCandidate : null);
        if (target) {
          bc += '<span class="breadcrumb-link" onclick="openPage(\'' + target.replace(/'/g,"\\'") + '\')">' + displayName(parts[i]) + '</span>';
        } else {
          bc += '<span>' + displayName(parts[i]) + '</span>';
        }
      } else {
        bc += '<span>' + displayName(parts[i]) + '</span>';
      }
    }
    document.getElementById("breadcrumb").innerHTML = bc;
    // Show type, links, and update time (to minute)
    var meta = info.type + " · " + info.links.length + " 个链接";
    if (info.mtime) {
      var d = new Date(info.mtime * 1000);
      var yy = d.getFullYear();
      var mm = String(d.getMonth() + 1).padStart(2, "0");
      var dd = String(d.getDate()).padStart(2, "0");
      var hh = String(d.getHours()).padStart(2, "0");
      var mi = String(d.getMinutes()).padStart(2, "0");
      meta += " · 更新 " + yy + "-" + mm + "-" + dd + " " + hh + ":" + mi;
    }
    document.getElementById("page-meta").textContent = meta;
    // Insert merged per-page button next to the page title (本页更新 + 历史版本 in one)
    insertPageRecButton();
    document.getElementById("content-area").scrollTop = 0;

    // Scroll to anchor heading if specified in wikilink (e.g. [[index#更新记录]])
    if (hash) {
      setTimeout(function() {
        var anchorEl = document.getElementById(hash);
        if (!anchorEl) {
          // Search headings by matching text content (for Chinese/Unicode headings)
          var headings = document.querySelectorAll('#content-area h1, #content-area h2, #content-area h3, #content-area h4');
          for (var hi = 0; hi < headings.length; hi++) {
            var hText = headings[hi].textContent.replace(/^[\d.\-]+\s*/, '').trim();
            if (hText === hash) {
              anchorEl = headings[hi];
              break;
            }
            // Also try removing special chars for fuzzy match
            var hPlain = hText.replace(/[^\w\u4e00-\u9fff]/g, '');
            var hashPlain = hash.replace(/[^\w\u4e00-\u9fff]/g, '');
            if (hPlain === hashPlain) {
              anchorEl = headings[hi];
              break;
            }
          }
        }
        if (anchorEl) {
          anchorEl.scrollIntoView({behavior: 'smooth', block: 'start'});
          // Brief highlight flash
          anchorEl.style.transition = 'background 0.6s';
          anchorEl.style.background = 'var(--highlight)';
          setTimeout(function() { anchorEl.style.background = ''; }, 1500);
        }
      }, 100);
    }

    // Highlight tree item by data-slug
    var treeItems = fileTree.querySelectorAll(".tree-file");
    treeItems.forEach(function(el) { el.classList.remove("active"); });
    for (var i = 0; i < treeItems.length; i++) {
      if (treeItems[i].getAttribute("data-slug") === slug) {
        treeItems[i].classList.add("active");
        // Scroll into view
        treeItems[i].scrollIntoView({block:"nearest",behavior:"smooth"});
        break;
      }
    }

    // On mobile, close sidebar
    if (window.innerWidth <= 700) {
      closeSidebar();
    }

    // Clear update tag for this page (user has seen it)
    clearTagForSlug(slug);
  } catch(e) {
    document.getElementById("content-area").innerHTML = '<div style="padding:40px;color:red">⚠️ 渲染错误: ' + e.message + '</div>';
  }
}

function toggleDiffView() {
  var dd = window._currentDiff;
  if (!dd) return;
  var area = document.getElementById("content-area");

  if (window._diffViewOn) {
    area.innerHTML = window._originalHtml;
    window._diffViewOn = false;
  } else {
    var slug = window._currentSlug;
    var info = files[slug];
    var html = '<div class="diff-banner"><span class="badge">更新对比</span><button onclick="toggleDiffView()" class="active">返回正常视图</button></div>';

    if (dd.type === "new") {
      // New pages: render markdown normally, green background
      html += '<div class="diff-note">✨ 本页为今日新增内容</div>';
      var rendered = DOMPurify.sanitize(marked.parse(info.content));
      html += '<div class="diff-container" style="background:rgba(34,197,94,0.06);border-radius:8px;padding:12px 16px">' + rendered + '</div>';

    } else if (dd.type === "updated") {
      // Updated pages: render inline with highlight (add) and strikethrough (del)
      // embedded in the original content flow
      var addC = 0, delC = 0;
      var segs = dd.segments;
      var renderedHtml = '';
      for (var i = 0; i < segs.length; i++) {
        var s = segs[i];
        if (s.type === "add") addC++;
        if (s.type === "del") delC++;
        var renderedLine = DOMPurify.sanitize(marked.parse(s.text));
        if (s.type === "add") {
          renderedHtml += '<div class="inline-diff-add">' + renderedLine + '</div>';
        } else if (s.type === "del") {
          renderedHtml += '<div class="inline-diff-del">' + renderedLine + '</div>';
        } else {
          renderedHtml += renderedLine;
        }
      }

      html += '<div class="diff-stats">对比上一版：+' + addC + ' 行新增 / -' + delC + ' 行删除</div>';
      html += renderedHtml;

    } else if (dd.type === "no_baseline") {
      html += '<div class="diff-note">📄 本页内容已更新，但暂无上一版快照可供对比。</div>';

    } else if (dd.type === "metadata_only") {
      html += '<div class="diff-note">📝 本页仅元数据（如文件名/编号）更新，正文内容无变化。</div>';
    }

    area.innerHTML = html;
    window._diffViewOn = true;
  }
}

// --- Version History (view old versions & diff vs current) ---
function openHistoryPanel() {
  var hist = window._currentHistory || [];
  if (!hist.length) return;
  renderHistoryList();
}
function renderHistoryList() {
  var hist = window._currentHistory || [];
  if (!hist.length) return;
  var area = document.getElementById("content-area");
  var sorted = hist.slice().sort(function(a,b){ return b.version - a.version; }); // newest first
  var html = '<div class="diff-banner"><span class="badge">📜 历史版本</span><button onclick="closeHistoryPanel()" class="active">返回正常视图</button></div>';
  html += '<div class="diff-note">本页保留 ' + hist.length + ' 个历史版本（最多 3 个）。修改文件并重新构建后，旧版本会自动归档到这里。</div>';
  sorted.forEach(function(h, idx) {
    var n = sorted.length - idx;
    var recency = idx === 0 ? "（最新历史）" : "";
    html += '<div class="history-item">';
    html += '<span class="hist-ver">版本 ' + n + '/' + sorted.length + recency + '</span>';
    html += '<button class="hist-btn" onclick="showHistoryVersion(' + h.version + ')">👁 查看内容</button>';
    html += '<button class="hist-btn" onclick="diffHistoryVersion(' + h.version + ')">🔍 对比当前</button>';
    html += '</div>';
  });
  area.innerHTML = html;
  window._historyView = "list";
}
function closeHistoryPanel() {
  var area = document.getElementById("content-area");
  area.innerHTML = window._originalHtml || "";
  window._historyView = null;
  // The saved HTML does not include the injected on-page button, so re-add it
  insertPageRecButton();
}
function showHistoryVersion(v) {
  var hist = window._currentHistory || [];
  var h = null;
  for (var i = 0; i < hist.length; i++) if (hist[i].version === v) { h = hist[i]; break; }
  if (!h) return;
  var area = document.getElementById("content-area");
  var histContent = h.content || (files[window._currentSlug] && files[window._currentSlug].content) || "";
  var rendered = DOMPurify.sanitize(marked.parse(histContent));
  var html = '<div class="diff-banner"><span class="badge">历史版本 ' + v + '</span><button onclick="backToLatestPage()" class="active">返回最新页面</button></div>';
  html += '<div class="diff-note">⏳ 这是修改前的历史快照（只读）。</div>';
  html += '<div class="diff-container" style="border-radius:8px;padding:12px 16px">' + rendered + '</div>';
  area.innerHTML = html;
  window._historyView = "version";
}
function diffHistoryVersion(v) {
  var hist = window._currentHistory || [];
  var h = null;
  for (var i = 0; i < hist.length; i++) if (hist[i].version === v) { h = hist[i]; break; }
  if (!h) return;
  var segs = h.segments || [];
  var area = document.getElementById("content-area");
  var html = '<div class="diff-banner"><span class="badge">对比当前</span><button onclick="backToLatestPage()" class="active">返回最新页面</button></div>';
  var addC = 0, delC = 0, renderedHtml = '';
  for (var i = 0; i < segs.length; i++) {
    var s = segs[i];
    if (s.type === "add") addC++;
    if (s.type === "del") delC++;
    var rl = DOMPurify.sanitize(marked.parse(s.text));
    if (s.type === "add") renderedHtml += '<div class="inline-diff-add">' + rl + '</div>';
    else if (s.type === "del") renderedHtml += '<div class="inline-diff-del">' + rl + '</div>';
    else renderedHtml += rl;
  }
  html += '<div class="diff-stats">历史版本 → 当前：+' + addC + ' 行 / -' + delC + ' 行</div>';
  html += renderedHtml;
  area.innerHTML = html;
  window._historyView = "diff";
}

function toggleSidebar(){ var sb=document.getElementById("sidebar"); sb.classList.toggle("open"); syncOverlay(); }
function closeSidebar(){ document.getElementById("sidebar").classList.remove("open"); syncOverlay(); }
function syncOverlay(){ var sb=document.getElementById("sidebar"); var ov=document.getElementById("overlay"); if(ov) ov.style.display=sb.classList.contains("open")?"block":"none"; }

function getLatestUpdateSlug(){
  var best=null, bestKey="";
  for(var slug in files){
    if(slug.indexOf("更新记录/")===0 && slug>bestKey){ bestKey=slug; best=slug; }
  }
  return best;
}

// Extract "本次性质一句话" from update record content
function updSummary(rec){
  if(!rec||!rec.content) return "";
  var lines=rec.content.split("\n");
  for(var i=0;i<lines.length;i++){
    var l=lines[i].trim().replace(/\*\*/g,"");
    var m=l.match(/本次性质一句话[：:]\s*(.*)/);
    if(m) return m[1].length>200?m[1].substring(0,197)+"…":m[1];
  }
  for(var i=0;i<lines.length&&i<5;i++){
    var l=lines[i].trim().replace(/^>\s*/,"");
    if(l&&l.indexOf("##")!==0&&l.indexOf("---")!==0) return l.length>200?l.substring(0,197)+"…":l;
  }
  return (rec.affected_pages||[]).length+" 个文件更新";
}
// Render one update block
function updBlock(rec,isLatest){
  var n=(rec.slug.match(/第(\d+)次/)||["",""])[1], d=(rec.slug.match(/(\d{4}-\d{2}-\d{2})/)||["",""])[1], t=rec.title||("第"+n+"次更新");
  var h='<div class="'+(isLatest?"ub ub-l":"ub")+'"><div class="ub-hd">'+(isLatest?'<span class="ub-tag">最新</span>':'')+'<span class="ub-tit">'+t+'</span><span class="ub-d">'+d+'</span><span class="ub-c">'+(rec.affected_pages||[]).length+'</span></div>';
  var sm=updSummary(rec);
  if(sm) h+='<div class="ub-sm">'+sm.replace(/</g,'&lt;')+'</div>';
  var pp=(rec.affected_pages||[]).slice().sort(function(a,b){return(b.level||0)-(a.level||0);});
  if(pp.length){h+='<div class="ub-pg">';
    pp.forEach(function(p){
      if(!files[p.slug]) return; var fi=files[p.slug], pt=fi.title||p.slug;
      var catLabel={"new":"新增","updated":"更新","viewpoint":"观点"}[p.category]||"";
      var catCls={"new":"ub-cat-n","updated":"ub-cat-u","viewpoint":"ub-cat-v"}[p.category]||"";
      h+='<div class="ub-it" onclick="event.stopPropagation();openPage(\''+p.slug.replace(/'/g,"\\'")+'\')">';
      h+='<div class="ub-il">';
      h+='<div class="ub-ir">'+(catLabel?'<span class="ub-cat '+catCls+'">'+catLabel+'</span>':'')+levelBadge(p.level)+'<span class="ub-pt">'+pt.replace(/</g,'&lt;')+'</span></div>';
      if(p.description) h+='<div class="ub-id">'+p.description.replace(/</g,'&lt;')+'</div>';
      h+='</div></div>';
    });
  h+='</div>';}
  h+='</div>';
  return h;
}

function renderLatestUpdateOverview(){
  if(!updateRecords||!updateRecords.length) return "";
  var recs=updateRecords.slice().sort(function(a,b){
    var da=(a.slug.match(/(\d{4}-\d{2}-\d{2})/)||["","0"])[1], db=(b.slug.match(/(\d{4}-\d{2}-\d{2})/)||["","0"])[1];
    var na=parseInt((a.slug.match(/第(\d+)次/)||["",0])[1],10), nb=parseInt((b.slug.match(/第(\d+)次/)||["",0])[1],10);
    return da<db?1:(da>db?-1:(na<nb?1:-1));
  });
  var html='<div class="uv" id="uv">'+updBlock(recs[0],true);
  if(recs.length>1){
    html+='<div class="uv-tog" id="uvTog" onclick="togglePrevUpdates()">📋 展开前 '+(recs.length-1)+' 次 ▾</div><div class="uv-prv" id="uvPrv" style="display:none">';
    for(var i=1;i<recs.length;i++) html+=updBlock(recs[i],false);
    html+='</div>';
  }
  html+='</div>';
  return html;
}
function togglePrevUpdates(){
  var p=document.getElementById("uvPrv"), b=document.getElementById("uvTog");
  if(!p||!b) return;
  var o=p.style.display!="none";
  p.style.display=o?"none":"";
  b.textContent=o?"📋 展开前 "+p.querySelectorAll(".ub").length+" 次 ▾":"📋 收起 ▴";
}

// --- Welcome / home screen (first screen) ---
function showHome(){
  var total = Object.keys(files).length;
  var t = tree;
  // Build category cards from top-level folders
  function childByName(node, name){ return (node.children||[]).filter(function(c){return c.name===name;})[0]; }
  function hubSlugOf(folderNode){
    if(!folderNode) return null;
    var hub = (folderNode.children||[]).filter(function(c){return c.is_hub;})[0];
    return hub ? hub.slug : (folderNode.children&&folderNode.children[0]?folderNode.children[0].slug:null);
  }
  function countChildren(node, name){
    var fn = childByName(t, name);
    return fn ? (fn.children||[]).filter(function(c){return c.type==="file"||c.slug;}).length : 0;
  }
  var cats = [];
  var meta = [
    {name:"topics",label:"主题栏目",desc:"投资研究 · 旅游攻略 · 个人成长方法论"},
    {name:"Interesting_findings",label:"趣味发现",desc:"跨领域关联发现 · 知识网络中的意外连接"},
    {name:"sources",label:"素材摘要",desc:"小红书 · 公众号 · PDF · 80+ 原始素材"},
    {name:"entities",label:"实体卡片",desc:"NVIDIA · 可转债 · 凯利公式 — 核心概念"},
  ];
  meta.forEach(function(m){
    var fn = childByName(t, m.name);
    if(fn){ cats.push({label:m.label, desc:m.desc, slug:hubSlugOf(fn), count:(fn.children||[]).length}); }
  });
  // 第 5 张卡片：最新更新记录（保留快捷入口）
  var luSlug = getLatestUpdateSlug();
  if(luSlug){
    var luDate = (luSlug.match(/(\d{4}-\d{2}-\d{2})/)||["",""])[1];
    cats.push({label:"更新记录", desc:"历次更新了什么（"+luDate+"）", slug:luSlug});
  }

  // 第 6 张卡片：最新更新概览（按次分组，按重要性排序）
  var overviewHtml = luSlug ? renderLatestUpdateOverview() : "";
  if(overviewHtml){
    cats.push({label:"📋 近期更新", slug:luSlug, goLabel:"查看完整更新历史 →", wide:true, noCardClick:true, body:'<div class="home-overview-card-desc">'+overviewHtml+'</div>'});
  }

  var cards = cats.map(function(c){    var cardClick = (c.slug && !c.noCardClick) ? pageClickAttr(c.slug) : "";
    var footerClick = c.slug ? pageClickAttr(c.slug) : "";
    var body = c.body || ('<div class="home-card-desc">'+c.desc+'</div>');
    return '<div class="home-card'+(c.wide?' home-card-wide':'')+'" '+cardClick+'>'+
      '<div class="home-card-title">'+c.label+'</div>'+
      body+
      (c.slug?'<div class="home-card-go" '+footerClick+'>'+(c.goLabel||'进入 →')+'</div>':'')+
    '</div>';
  }).join("");
  var html = ''+
    '<div class="home">'+
      '<div class="home-hero">'+
        '<h1>第二大脑 · 知识库</h1>'+
        '<p>共 '+total+' 篇笔记，涵盖投资研究、旅行攻略与个人成长。从下方栏目进入，或点左上角「更新历史」查看历次更新。</p>'+
        '<div style="margin-top:10px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center;font-size:12px;color:var(--text2)">'+
          '<span>📊 主题 '+countChildren(t,'topics')+'</span>'+
          '<span>· 实体 '+countChildren(t,'entities')+'</span>'+
          '<span>· 素材 '+countChildren(t,'sources')+'</span>'+
          '<span>· 趣味发现 '+countChildren(t,'Interesting_findings')+'</span>'+
        '</div>'+
      '</div>'+
      '<div class="home-cards">'+cards+'</div>'+
    '</div>';
  document.getElementById("content-area").innerHTML = html;
  selfCheckContent("home");
  document.getElementById("breadcrumb").innerHTML = "<span>首页</span>";
  document.getElementById("page-meta").textContent = total + " 篇 · 已就绪";
  removePageRecButton();
  window._currentHistory = [];
  window._currentSlug = "";
  document.getElementById("content-area").scrollTop = 0;
}

function resolveSlug(name) {
  if (files[name]) return name;
  // Try last segment matching
  var needle = name.split("/").pop();
  for (var slug in files) {
    if (slug.split("/").pop() === needle) return slug;
  }
  return null;
}

function highlightTreeFile(el) {
  document.querySelectorAll(".tree-file.active").forEach(function(e) { e.classList.remove("active"); });
  el.classList.add("active");
}

// --- Search ---
var lastSearch = "";
function doSearch(q) {
  q = q.toLowerCase().trim();
  if (q === lastSearch) return;
  lastSearch = q;
  if (!q) {
    document.querySelectorAll(".tree-file,.tree-folder").forEach(function(e) { e.style.display = ""; });
    return;
  }
  document.querySelectorAll(".tree-file,.tree-folder").forEach(function(e) { e.style.display = "none"; });
  for (var slug in files) {
    var info = files[slug];
    if (slug.toLowerCase().includes(q) || info.title.toLowerCase().includes(q)) {
      // Show this file
      var items = fileTree.querySelectorAll(".tree-file");
      items.forEach(function(item) {
        if (item.textContent.toLowerCase().includes(q) || 
            (info.title.toLowerCase().includes(q) && item.textContent.includes(info.title))) {
          item.style.display = "";
          // Expand parent folders
          var p = item.parentElement;
          while (p && p !== fileTree) {
            if (p.style.display === "none") p.style.display = "";
            var prev = p.previousElementSibling;
            if (prev && prev.classList.contains("tree-folder")) {
              prev.style.display = "";
              prev.querySelector(".tree-arrow").textContent = "▾";
            }
            p = p.parentElement;
          }
        }
      });
    }
  }
}

// --- Tab switching ---
function switchTab(tab) {
  document.getElementById("tabs").querySelectorAll("button").forEach(function(b,i) {
    b.classList.toggle("active", (i===0 && tab==="files") || (i===1 && tab==="graph"));
  });
  if (tab === "files") {
    document.getElementById("content-area").style.display = "";
    document.getElementById("graph-container").style.display = "none";
  } else {
    document.getElementById("content-area").style.display = "none";
    document.getElementById("graph-container").style.display = "";
    initGraph();
  }
}

// --- Graph ---
var graphInited = false;
function initGraph() {
  if (graphInited) return;
  graphInited = true;

  var typeColors = {topic:"#cb6e3e",entity:"#4a7c59",source:"#9e8e74",insight:"#8b6fad",comparison:"#6b8fad",synthesis:"#ad7b6b",overview:"#5b7a9e",other:"#bbb"};
  var visNodes = new vis.DataSet(graphData.nodes.map(function(n) {
    return {
      id:n.id,label:n.label.length>18?n.label.slice(0,16)+"…":n.label,
      title:n.label,color:{background:typeColors[n.type]||"#bbb",border:"#fff",highlight:{background:typeColors[n.type]||"#bbb",border:"#333"}},
      size:Math.max(6,Math.min(28,6+n.linkCount*1.3)),
      font:{size:10,color:"#2c2416"},
      borderWidth:1,value:n.linkCount
    };
  }));
  var visEdges = new vis.DataSet(graphData.edges.map(function(e) {
    return {from:e.source,to:e.target,color:{color:"rgba(180,170,150,0.3)",highlight:"rgba(203,110,62,0.5)"},width:0.8,smooth:{type:"continuous"}};
  }));
  var network = new vis.Network(document.getElementById("network"),{nodes:visNodes,edges:visEdges},{
    physics:{solver:"forceAtlas2Based",forceAtlas2Based:{gravitationalConstant:-80,centralGravity:0.005,springLength:200,springConstant:0.03},stabilization:{iterations:200}},
    interaction:{hover:true,navigationButtons:false}
  });
  network.on("click",function(p) {
    var detail = document.getElementById("graph-detail");
    if (p.nodes.length > 0) {
      var info = files[p.nodes[0]];
      if (!info) return;
      detail.style.display = "";
      detail.innerHTML = '<h3>' + info.title + '</h3><span style="color:var(--text3)">' + info.type + ' · ' + info.links.length + '链接</span>' +
        '<div style="margin-top:8px"><a class="wiki-link" onclick="openPage(\''+p.nodes[0]+'\');switchTab(\'files\')">打开页面 →</a></div>';
      network.focus(p.nodes[0],{scale:1.3,animation:{duration:400}});
    } else { detail.style.display = "none"; }
  });
}

// --- Inbox drawer (raw/inbox 待处理素材) ---
function inboxEsc(s){
  return (s||"").replace(/[&<>"']/g, function(c){
    return {"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c];
  });
}
function renderInboxDrawer(){
  var body = document.getElementById("inbox-drawer-body");
  var data = window.inboxData || {items:[]};
  var items = data.items || [];
  var totalEl = document.getElementById("inbox-total");
  if (totalEl) totalEl.textContent = items.length ? ("· 共 "+items.length+" 篇") : "";
  if (!items.length){
    body.innerHTML = '<div class="inbox-empty">📭 暂无待处理文章<br><small style="color:var(--text3)">raw/inbox/ 当前为空</small></div>';
    return;
  }
  var groups = {};
  items.forEach(function(it){ (groups[it.source_type] = groups[it.source_type] || []).push(it); });
  var order = Object.keys(groups).sort(function(a,b){ return groups[b].length - groups[a].length; });
  var html = "";
  order.forEach(function(st){
    var list = groups[st];
    var label = list[0].source_label || st;
    var cls = "sb-" + st;
    html += '<div class="inbox-group" data-st="'+inboxEsc(st)+'">';
    html += '<div class="inbox-group-head" onclick="toggleInboxGroup(this)">';
    html += '<span class="inbox-group-arrow">▾</span>';
    html += '<span class="inbox-source-badge '+cls+'">'+inboxEsc(label)+'</span>';
    html += '<span class="inbox-group-count">'+list.length+' 篇</span>';
    html += '</div>';
    html += '<div class="inbox-group-body">';
    list.forEach(function(it){
      var isHttp = it.url && /^https?:/i.test(it.url);
      var openAttr = isHttp ? ' href="'+inboxEsc(it.url)+'" target="_blank" rel="noopener"' : '';
      html += '<a class="inbox-item"'+openAttr+'>';
      html += '<div class="inbox-item-top"><span class="inbox-item-title">'+inboxEsc(it.title||"(无标题)")+'</span>';
      html += '<span class="inbox-item-date">'+inboxEsc(it.saved_at||"")+'</span></div>';
      if (it.summary) html += '<div class="inbox-item-summary">'+inboxEsc(it.summary)+'</div>';
      html += '<div class="inbox-item-foot">';
      html += '<span class="inbox-source-badge '+cls+'">'+inboxEsc(label)+'</span>';
      if (isHttp) html += '<span class="inbox-open">打开原文 ↗</span>';
      (it.theme||[]).slice(0,4).forEach(function(t){ html += '<span class="inbox-theme">'+inboxEsc(t)+'</span>'; });
      html += '</div></a>';
    });
    html += '</div></div>';
  });
  body.innerHTML = html;
}
function toggleInboxGroup(head){
  head.parentElement.classList.toggle("collapsed");
}
function toggleInboxDrawer(){
  var d = document.getElementById("inbox-drawer");
  var ov = document.getElementById("inbox-overlay");
  var m = document.getElementById("main");
  if (d.classList.contains("open")){
    d.classList.remove("open"); ov.classList.remove("open"); if (m) m.classList.remove("panel-open"); return;
  }
  var ud = document.getElementById("update-drawer");
  if (ud && ud.classList.contains("open")) ud.classList.remove("open");
  var body = document.getElementById("inbox-drawer-body");
  if (!body.innerHTML) renderInboxDrawer();
  d.classList.add("open"); ov.classList.add("open"); if (m) m.classList.add("panel-open");
}

// --- Keyboard ---
document.onkeydown = function(e) {
  if (e.key === "/" && document.activeElement !== document.getElementById("search-inp")) {
    e.preventDefault(); document.getElementById("search-inp").focus();
  }
};

// (hidden-tag auto-restore removed: tags now reflect the selected update only)

// --- Resizable sidebar (desktop only) ---
(function(){
  var handle = document.getElementById("resize-handle");
  var sidebar = document.getElementById("sidebar");
  if (!handle || !sidebar) return;
  var dragging = false;
  handle.addEventListener("mousedown", function(e){
    dragging = true; handle.classList.add("dragging");
    document.body.style.userSelect = "none"; e.preventDefault();
  });
  document.addEventListener("mousemove", function(e){
    if (!dragging) return;
    var w = Math.max(200, Math.min(480, e.clientX));
    sidebar.style.width = w + "px";
  });
  document.addEventListener("mouseup", function(){
    if (dragging){ dragging = false; handle.classList.remove("dragging"); document.body.style.userSelect = ""; }
  });
})();

// --- Inbox 一键消化 ---
function triggerGxDigest() {
  var btn = document.getElementById("inbox-digest-btn");
  var status = document.getElementById("inbox-digest-status");
  if (!btn || !status) return;
  // Check if there are pending files in inbox
  var inboxItems = document.querySelectorAll("#inbox-drawer-body .inbox-item");
  if (inboxItems.length === 0) {
    status.innerHTML = '📭 Inbox 暂无待处理文件';
    btn.style.animation = "shake 0.3s ease";
    setTimeout(function(){ btn.style.animation = ""; }, 300);
    return;
  }
  // Static page cannot directly trigger WorkBuddy skill — guide user to chat
  btn.disabled = true;
  btn.style.opacity = "0.5";
  status.innerHTML = '⏳ 正在启动消化...';
  // Brief delay for visual feedback, then show guidance
  setTimeout(function() {
    status.innerHTML = '📋 已复制到剪贴板。请在下方对话输入框粘贴 <code style="background:var(--bg3);padding:1px 5px;border-radius:3px;font-size:11px;color:var(--accent2)">/gx</code> 并发送，即可启动消化流程';
    btn.disabled = false;
    btn.style.opacity = "1";
    // Copy /gx to clipboard for convenience
    try {
      navigator.clipboard.writeText("/gx").then(function(){
        status.innerHTML = '📋 <b>/gx</b> 已复制到剪贴板！请粘贴到下方对话输入框发送<br><span style="color:var(--text3)">即将自动消化 ' + inboxItems.length + ' 篇待处理素材</span>';
      }).catch(function(){
        status.innerHTML = '请在下方对话输入框输入 <code style="background:var(--bg3);padding:1px 5px;border-radius:3px;font-size:11px;color:var(--accent2)">/gx</code> 并发送，即可启动消化流程<br><span style="color:var(--text3)">' + inboxItems.length + ' 篇待处理素材</span>';
      });
    } catch(e) {
      status.innerHTML = '请在下方对话输入框输入 <code style="background:var(--bg3);padding:1px 5px;border-radius:3px;font-size:11px;color:var(--accent2)">/gx</code> 并发送，即可启动消化流程<br><span style="color:var(--text3)">' + inboxItems.length + ' 篇待处理素材</span>';
    }
  }, 600);
}

// --- Update History Drawer ---
// Global state
var updateDrawerOpen = false;
var updateDrawerMode = "global";  // "global" = whole KB; "page" = current page only
var updateRecords = [];  // will be set after bundle loads

function getFilteredRecords() {
  // Filter: only show updates that affect the current page
  var currentSlug = window._currentSlug || "";
  if (!currentSlug) return updateRecords; // fallback: show all
  return updateRecords.filter(function(rec) {
    return (rec.affected_pages || []).some(function(p) { return p.slug === currentSlug; });
  });
}

function getCurrentPageInfo() {
  var slug = window._currentSlug || "";
  if (slug && files[slug]) return files[slug];
  return null;
}

function toggleUpdateDrawer() {
  var idr = document.getElementById("inbox-drawer");
  if (idr && idr.classList.contains("open")) {
    idr.classList.remove("open");
    var iov = document.getElementById("inbox-overlay");
    if (iov) iov.classList.remove("open");
  }
  var drawer = document.getElementById("update-drawer");
  // If already showing the whole-KB view, a second click closes it.
  // If closed, or showing the per-page view, a click opens/switches to global.
  if (updateDrawerOpen && updateDrawerMode === "global") {
    updateDrawerOpen = false;
    drawer.classList.remove("open");
    var m0 = document.getElementById("main"); if (m0) m0.classList.remove("panel-open");
    return;
  }
  updateDrawerMode = "global";
  updateDrawerOpen = true;
  document.getElementById("update-hist-badge").textContent = "";
  drawer.classList.add("open");
  var m1 = document.getElementById("main"); if (m1) m1.classList.add("panel-open");
  renderUpdateRecords();
}

// Open the drawer to show the current page's own history snapshots
function openPageUpdateHistory() {
  updateDrawerMode = "page";
  updateDrawerOpen = true;
  document.getElementById("update-drawer").classList.add("open");
  var m = document.getElementById("main"); if (m) m.classList.add("panel-open");
  renderPageHistory();
}

// Toggle the per-page update history: open if closed/other-mode, retract if already open in page mode
function togglePageUpdateHistory() {
  if (updateDrawerOpen && updateDrawerMode === "page") {
    closeUpdateDrawer();
    return;
  }
  openPageUpdateHistory();
}

function closeUpdateDrawer() {
  var drawer = document.getElementById("update-drawer");
  if (drawer) drawer.classList.remove("open");
  var m = document.getElementById("main"); if (m) m.classList.remove("panel-open");
  updateDrawerOpen = false;
}

function renderPageHistory() {
  var body = document.getElementById("update-drawer-body");
  var pageInfo = getCurrentPageInfo();
  var title = pageInfo ? (pageInfo.title || window._currentSlug) : "本页";
  var info = window._currentSlug ? files[window._currentSlug] : null;
  var hist = (info && info.history) || [];
  hist = hist.slice().sort(function(a, b){ return b.version - a.version; });

  // Find which update records mention this page
  var slug = window._currentSlug;
  var pageUpdates = [];
  if (slug && updateRecords) {
    for (var ri = 0; ri < updateRecords.length; ri++) {
      var rec = updateRecords[ri];
      var pages = rec.affected_pages || [];
      for (var pj = 0; pj < pages.length; pj++) {
        if (pages[pj].slug === slug) {
          pageUpdates.push({ rec: rec, desc: pages[pj].description, cat: pages[pj].category, level: pages[pj].level });
          break;
        }
      }
    }
  }

  var html = '<div style="padding:14px 16px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg)">';
  html += '<div style="font-size:13px;font-weight:700;color:var(--accent);cursor:pointer" onclick="switchToGlobalHistory()">← 全部更新</div>';
  html += '<div style="font-size:14px;font-weight:700;color:var(--accent)">📋 ' + title + '</div>';
  html += '<div style="font-size:11px;color:var(--text3);margin-top:2px">' + (pageUpdates.length || hist.length) + ' 次修改记录</div>';
  html += '</div>';

  if (pageUpdates.length === 0 && hist.length === 0) {
    html += '<div id="update-drawer-empty">该页面暂无修改记录</div>';
    body.innerHTML = html;
    return;
  }

  // Show update records that affected this page (newest first)
  pageUpdates.sort(function(a,b){
    var da = (a.rec.slug.match(/(\d{4}-\d{2}-\d{2})/)||["","0"])[1];
    var db = (b.rec.slug.match(/(\d{4}-\d{2}-\d{2})/)||["","0"])[1];
    return da < db ? 1 : (da > db ? -1 : 0);
  });

  if (pageUpdates.length > 0) {
    for (var ui = 0; ui < pageUpdates.length; ui++) {
      var pu = pageUpdates[ui];
      var recN = (pu.rec.slug.match(/第(\d+)次/)||["",""])[1];
      var recDate = (pu.rec.slug.match(/(\d{4}-\d{2}-\d{2})/)||["",""])[1];
      var recTitle = "第" + recN + "次更新";
      var catLabel = {"new":"新增","updated":"更新","viewpoint":"观点改变"}[pu.cat] || "";

      html += '<div style="padding:12px 16px;border-bottom:1px solid var(--border)">';
      // Header: level + update number + date + category
      html += '<div style="display:flex;align-items:center;gap:5px;flex-wrap:wrap;margin-bottom:4px">';
      html += levelBadge(pu.level);
      html += '<span style="font-size:13px;font-weight:700;color:var(--accent);cursor:pointer" onclick="switchToGlobalHistory()">' + recTitle + '</span>';
      html += '<span style="font-size:11px;color:var(--text3)">' + recDate + '</span>';
      if (catLabel) html += '<span style="font-size:10px;font-weight:700;padding:1px 6px;border-radius:3px;background:var(--bg3)">' + catLabel + '</span>';
      html += '</div>';
      // Description: what changed for this specific page
      if (pu.desc) html += '<div style="font-size:12px;color:var(--text2);line-height:1.5;margin-bottom:3px">📝 ' + pu.desc.replace(/</g,'&lt;') + '</div>';
      // Snapshot action buttons: both lists are newest-first. hist[0] is the latest
      // commit (≈ current content), so the "before this update" snapshot for record
      // #ui is hist[ui+1]. Records older than the kept snapshots (max 3) get greyed
      // buttons with a hint instead of vanishing.
      var hidx = ui + 1;
      if (hidx < hist.length) {
        html += '<div style="display:flex;gap:6px;margin-top:6px">';
        html += '<button class="upd-page-btn" onclick="viewPageHistoryVersion(' + hist[hidx].version + ')">查看快照</button>';
        html += '<button class="upd-page-btn main" onclick="diffPageHistoryVersion(' + hist[hidx].version + ')">对比当前</button>';
        html += '</div>';
      } else {
        html += '<div style="display:flex;gap:6px;margin-top:6px">';
        html += '<button class="upd-page-btn" disabled title="快照仅保留最近数个版本，此记录对应的旧快照已超出保留范围">查看快照</button>';
        html += '<button class="upd-page-btn" disabled title="旧快照已超出保留范围，无法对比">对比当前</button>';
        html += '</div>';
      }
      html += '</div>';
    }
  } else if (hist.length > 0) {
    // Fallback: show snapshots only if no update records matched
    for (var i = 0; i < hist.length; i++) {
      var h = hist[i];
      var n = hist.length - i;
      html += '<div style="padding:12px 16px;border-bottom:1px solid var(--border);display:flex;align-items:center;justify-content:space-between">';
      html += '<span class="upd-ver-label">快照 ' + n + '/' + hist.length + (i === 0 ? '（最新）' : '') + '</span>';
      html += '<div style="display:flex;gap:6px">';
      html += '<button class="upd-page-btn" onclick="viewPageHistoryVersion(' + h.version + ')">查看</button>';
      html += '<button class="upd-page-btn main" onclick="diffPageHistoryVersion(' + h.version + ')">对比当前</button>';
      html += '</div></div>';
    }
  }

  body.innerHTML = html;
}

function viewPageHistoryVersion(v) {
  var slug = window._currentSlug;
  if (!slug || !files[slug]) return;
  window._currentHistory = files[slug].history || [];
  closeUpdateDrawer();
  showHistoryVersion(v);
}

function diffPageHistoryVersion(v) {
  var slug = window._currentSlug;
  if (!slug || !files[slug]) return;
  window._currentHistory = files[slug].history || [];
  closeUpdateDrawer();
  diffHistoryVersion(v);
}

// --- On-page "更新历史" button: opens this page's update history directly (no dropdown) ---
function insertPageRecButton() {
  removePageRecButton();
  var ca = document.getElementById("content-area");
  if (!ca) return;
  var h1 = ca.querySelector("h1");
  if (!h1) return;
  // Count how many update records mention this page
  var slug = window._currentSlug || "";
  var finfo = files[slug];
  if (!finfo || finfo.hidden) return; // synthetic/hidden pages: no button
  var recCount = (updateRecords || []).filter(function(rec) {
    return (rec.affected_pages || []).some(function(p) { return p.slug === slug; });
  }).length;
  // git history only counts as "update history" when there is more than the initial version
  var histCount = Math.max(0, (finfo.history_versions || 0) - 1);
  // Wrap the title + button in a flex row so the button sits to the right of the title
  var row = document.createElement("div");
  row.className = "page-title-row";
  h1.parentNode.insertBefore(row, h1);
  row.appendChild(h1);
  var btn = document.createElement("button");
  btn.id = "page-rec-btn";
  btn.className = "page-rec-btn";
  if (recCount > 0 || histCount > 0) {
    btn.innerHTML = "页面更新历史 (" + (recCount || histCount) + ")";
    btn.onclick = function(e) { e.stopPropagation(); togglePageUpdateHistory(); };
  } else {
    // Always render the button; grey it out when the page has no history yet
    btn.innerHTML = "页面更新历史";
    btn.disabled = true;
    btn.title = "该页暂无更新历史";
  }
  row.appendChild(btn);
}
function removePageRecButton() {
  var b = document.getElementById("page-rec-btn");
  if (b) {
    var row = b.parentNode;
    var h1 = row ? row.querySelector("h1") : null;
    if (h1 && row.parentNode) row.parentNode.insertBefore(h1, row);
    if (row) row.remove();
  }
}

// Switch back to the whole-KB view from within the per-page view
function switchToGlobalHistory() {
  updateDrawerMode = "global";
  renderUpdateRecords();
}










function renderUpdateRecords() {
  var body = document.getElementById("update-drawer-body");
  var pageInfo = getCurrentPageInfo();
  var title, filtered;
  if (updateDrawerMode === "page") {
    filtered = getFilteredRecords();
    title = pageInfo ? (pageInfo.title || window._currentSlug) : "本页";
  } else if (currentUpdateTab === "strategy") {
    filtered = getFilteredStrategyRecords();
    title = "策略相关更新";
  } else {
    filtered = updateRecords;
    title = "知识库全部更新";
  }

  var html = '<div style="padding:14px 16px;border-bottom:1px solid var(--border);position:sticky;top:0;background:var(--bg)">';
  if (updateDrawerMode === "page") {
    html += '<div style="font-size:13px;font-weight:700;color:var(--accent);cursor:pointer" onclick="switchToGlobalHistory()">← 全部更新</div>';
  }
  html += '<div style="font-size:14px;font-weight:700;color:var(--accent)">📋 '+title+'</div>';
  html += '<div style="font-size:11px;color:var(--text3);margin-top:2px">'+filtered.length+' 次更新</div>';
  html += '</div>';

  if (filtered.length === 0) {
    html += '<div id="update-drawer-empty">暂无相关更新记录</div>';
    body.innerHTML = html;
    return;
  }

  // Sort: newest first — by date desc, then by 第N次更新 number desc (same-day tiebreak)
  var sorted = filtered.slice().sort(function(a,b){
    var d = (b.created||"").localeCompare(a.created||"");
    if (d !== 0) return d;
    return getUpdateNum(b) - getUpdateNum(a);
  });
  for (var i = 0; i < sorted.length; i++) {
    var rec = sorted[i];
    var recId = "upd-rec-" + i;
    html += '<div class="update-record" id="' + recId + '">';
    html += '<div class="update-record-header collapsed" onclick="toggleUpdateRecord(\'' + recId + '\', this)">';
    html += '<div>';
    html += '<div class="update-record-title">' + rec.title + '</div>';
    html += '<div class="update-record-meta">' + rec.update_type + '</div>';
    html += '</div>';
    html += '<span class="update-record-arrow">▼</span>';
    html += '</div>';
    html += '<div class="update-record-body collapsed" id="' + recId + '-body">';
    // Show a brief summary of what was updated
    var summary = getUpdateSummary(rec);
    if (summary) {
      html += '<div class="upd-summary">' + DOMPurify.sanitize(marked.parse(summary)) + '</div>';
    }
    html += '<div class="upd-toolbar">';
    html += '<button class="upd-back-btn" onclick="openPage(\'' + rec.slug.replace(/'/g,"\\'") + '\')">📄 查看完整更新记录</button>';
    html += '<button class="upd-back-btn" onclick="applyUpdateTags(\'' + rec.slug.replace(/'/g,"\\'") + '\')">🏷 恢复此更新的标签</button>';
    html += '</div>';
    html += renderAffectedPages(rec);
    html += '</div>';
    html += '</div>';
  }
  body.innerHTML = html;
}

// Extract the update sequence number (第N次更新) from a record's title or slug
function getUpdateNum(rec) {
  if (!rec) return 0;
  var m = ((rec.title || "") + " " + (rec.slug || "")).match(/第\s*(\d+)\s*次/);
  return m ? parseInt(m[1], 10) : 0;
}

// Extract a brief summary from the update record's content
function getUpdateSummary(rec) {
  if (!rec || !rec.content) return "";
  var body = rec.content;
  // Strip frontmatter
  if (body.startsWith("---")) {
    var parts = body.split("---", 3);
    if (parts.length >= 3) body = parts[2];
  }
  // Remove the "# " title line
  body = body.replace(/^# .*\n?/, "");
  // Remove the "## 📌 必看清单" section (everything from it to the next ##)
  body = body.replace(/## 📌 必看清单[\s\S]*?(?=## )/, "");
  // Remove "## 观点变化" section if empty
  body = body.replace(/## 观点变化\n\n\*\*无重大变化。\*\*[\s\S]*?(?=## )/, "");
  body = body.replace(/## 观点变化\n\n无重大变化[\s\S]*?(?=## )/, "");
  // Take the first non-empty paragraph
  var lines = body.split("\n");
  var summary = "";
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (line && !line.startsWith("#") && !line.startsWith(">") && !line.startsWith("---") && !line.startsWith("|")) {
      summary = line;
      break;
    }
  }
  // Truncate long summaries
  if (summary.length > 200) summary = summary.substring(0, 200) + "…";
  return summary || "（本次更新详情见下方受影响页面）";
}

// Map an update-record page category to a severity tag key
function categoryToSev(cat) {
  if (cat === "new") return "new";
  if (cat === "viewpoint") return "viewpoint";
  return "updated";
}

// 1-5 重要度等级（替代星星，统一徽章样式）
var LEVEL_META = {
  5: { label: "必看", cls: "lv5" },
  4: { label: "重要", cls: "lv4" },
  3: { label: "有价值", cls: "lv3" },
  2: { label: "常规", cls: "lv2" },
  1: { label: "次要", cls: "lv1" }
};
function levelBadge(lv) {
  if (!lv) return "";
  var m = LEVEL_META[lv];
  if (!m) return "";
  return '<span class="lv-badge ' + m.cls + '">Lv.' + lv + " " + m.label + "</span>";
}
// 清理描述里的星星与多余分隔符（源 md 里常带 "⭐ | ..."）
function cleanDesc(desc) {
  if (!desc) return "";
  return desc.replace(/⭐/g, "").replace(/^\s*\|+\s*/, "").replace(/\s+/g, " ").trim();
}

// Post-process the "必看清单" section: turn "[N · 标签]" tokens into a styled
// 1-5 score badge (no stars). Handles old "[⭐⭐ | 5]" and new "[5 · 必看]" formats.
function enhanceMustRead() {
  var area = document.getElementById("content-area");
  if (!area) return;
  var lis = area.querySelectorAll("li");
  lis.forEach(function(li){
    var m = li.textContent.match(/^\s*\[[⭐\s|]*?(\d+)\s*(?:[·•\-]\s*([^\[\]()]*?))?\s*\]/);
    if (!m) return;
    var lv = parseInt(m[1], 10);
    var label = (m[2] || "").trim();
    var meta = LEVEL_META[lv];
    if (meta && !label) label = meta.label;
    var cls = meta ? meta.cls : "lv3";
    var badge = '<span class="lv-badge ' + cls + '">' + lv + '分 · ' + (label || "") + '</span> ';
    li.innerHTML = li.innerHTML.replace(/^(\s*)\[[⭐\s|]*?\d+\s*(?:[·•\-]\s*[^\[\]()]*?)?\s*\]/, function(mm, p){ return p + badge; });
  });
}

// Toggle an update-record accordion item in the drawer list
function toggleUpdateRecord(recId, header) {
  var body = document.getElementById(recId + "-body");
  if (!body) return;
  var expanded = body.classList.toggle("expanded");
  header.classList.toggle("collapsed", !expanded);
}

function renderAffectedPages(rec) {
  var pages = rec.affected_pages || [];
  if (pages.length === 0) return '<div class="upd-empty">本更新未记录具体页面</div>';
  var html = '';
  for (var i = 0; i < pages.length; i++) {
    var p = pages[i];
    var info = files[p.slug];
    if (!info) continue;
    var ptitle = info.title || p.slug;
    var catSev = categoryToSev(p.category);
    // Override to "major" if the file has build-time major severity
    if (info.update_severity === "major") { catSev = "major"; }
    var catLabel = sevLabel[catSev];
    var hist = (info.history || []).slice().sort(function(a,b){ return b.version - a.version; });
    var recent = hist.slice(0, 2);
    var rowId = "aff-pg-" + i;
    html += '<div class="upd-page-block">';
    html += '<div class="upd-page-row" onclick="toggleAffectedPage(\'' + rowId + '\')">';
    html += '<span class="update-tag ' + sevMap[catSev] + '" style="font-size:10px;padding:1px 6px;flex-shrink:0">' + catLabel + '</span>';
    html += levelBadge(p.level);
    html += '<span class="upd-page-title" title="' + ptitle + '">' + ptitle + '</span>';
    html += '<span class="upd-page-chevron">▸</span>';
    html += '</div>';
    var desc = cleanDesc(p.description);
    if (desc) html += '<div class="upd-page-desc">' + desc + '</div>';
    html += '<div class="upd-page-detail collapsed" id="' + rowId + '">';
    if (recent.length) {
      for (var k = 0; k < recent.length; k++) {
        var h = recent[k];
        var n = hist.length - hist.indexOf(h);
        html += '<div class="upd-ver-row">';
        html += '<span class="upd-ver-label">版本 ' + n + '/' + hist.length + (k === 0 ? '（最新历史）' : '') + '</span>';
        html += '<button class="upd-page-btn" onclick="event.stopPropagation();viewAffectedVersion(\'' + p.slug.replace(/'/g,"\\'") + '\',' + h.version + ')">查看</button>';
        html += '<button class="upd-page-btn main" onclick="event.stopPropagation();diffAffectedVersion(\'' + p.slug.replace(/'/g,"\\'") + '\',' + h.version + ')">对比当前</button>';
        html += '</div>';
      }
    } else {
      html += '<div class="upd-page-nohist">该页面暂无历史版本快照（修改并重新构建后自动归档）</div>';
    }
    html += '</div>';
    html += '</div>';
  }
  return html;
}
function toggleAffectedPage(rowId) {
  var row = document.getElementById(rowId);
  if (!row) return;
  var detail = row.nextElementSibling;
  while (detail && !detail.classList.contains("upd-page-detail")) detail = detail.nextElementSibling;
  if (!detail) return;
  var expanded = detail.classList.toggle("expanded");
  row.classList.toggle("expanded", expanded);
}
function viewAffectedVersion(slug, v) {
  window._currentSlug = slug;
  window._currentHistory = (files[slug] && files[slug].history) || [];
  showHistoryVersion(v);
}
function diffAffectedVersion(slug, v) {
  window._currentSlug = slug;
  window._currentHistory = (files[slug] && files[slug].history) || [];
  diffHistoryVersion(v);
}


// Close the update drawer and open a specific page
function closeDrawerThenOpenPage(slug) {
  var drawer = document.getElementById("update-drawer");
  if (drawer) { drawer.classList.remove("open"); updateDrawerOpen = false; }
  openPage(slug);
}




// Return from the update drawer to the latest (current) page, or home if none
function backToLatestPage() {
  var drawer = document.getElementById("update-drawer");
  if (drawer) { drawer.classList.remove("open"); updateDrawerOpen = false; }
  var slug = window._currentSlug;
  if (slug && files[slug]) openPage(slug);
  else showHome();
}

// Apply the severity tags (新增 / 更新 / 观点改变) of a specific update onto the file tree
function applyTagsForRecord(rec) {
  if (!rec) return;
  var pages = rec.affected_pages || [];
  for (var j = 0; j < pages.length; j++) {
    var p = pages[j];
    var sev = categoryToSev(p.category);
    // Check if the file has "major" build-time severity — use "major" tag instead
    var fileInfo = window.files ? window.files[p.slug] : null;
    if (fileInfo && fileInfo.update_severity === "major") {
      sev = "major";
    }
    var items = fileTree ? fileTree.querySelectorAll('.tree-file') : [];
    for (var k = 0; k < items.length; k++) {
      if (items[k].getAttribute('data-slug') === p.slug) {
        if (items[k].querySelector('.update-tag')) break; // keep newest tag for this slug
        items[k].insertAdjacentHTML('beforeend', '<span class="update-tag '+sevMap[sev]+'">'+sevLabel[sev]+'</span>');
        break;
      }
    }
  }
}
function applyUpdateTags(slug) {
  var rec = null;
  for (var i = 0; i < updateRecords.length; i++) {
    if (updateRecords[i].slug === slug) { rec = updateRecords[i]; break; }
  }
  if (!rec) { setUpdateTagStatus("未找到该更新记录"); return; }
  // Clear existing tags first, then apply this record's tags only
  if (fileTree) {
    fileTree.querySelectorAll('.update-tag').forEach(function(el){ el.remove(); });
  }
  applyTagsForRecord(rec);
  // Re-apply read state from localStorage
  try {
    var read = JSON.parse(localStorage.getItem('wiki_read_tags')||'[]');
    read.forEach(function(s){ clearTagForSlug(s); });
  } catch(e){}
  setUpdateTagStatus('已恢复「' + rec.title + '」标签');
}
function autoApplyAllTags() {
  if (!updateRecords || updateRecords.length === 0) return;
  if (!fileTree) return;
  fileTree.querySelectorAll('.update-tag').forEach(function(el){ el.remove(); });
  var sorted = updateRecords.slice().sort(function(a,b){
    var d = (b.created||"").localeCompare(a.created||"");
    if (d !== 0) return d;
    return getUpdateNum(b) - getUpdateNum(a);
  });
  sorted.forEach(function(rec){ applyTagsForRecord(rec); });
  // Re-apply read state from localStorage
  try {
    var read = JSON.parse(localStorage.getItem('wiki_read_tags')||'[]');
    read.forEach(function(s){ clearTagForSlug(s); });
  } catch(e){}
}

// Clear the update tag for a specific slug (called when user opens a page)
function clearTagForSlug(slug) {
  if (!fileTree) return;
  var items = fileTree.querySelectorAll('.tree-file');
  for (var i = 0; i < items.length; i++) {
    if (items[i].getAttribute('data-slug') === slug) {
      var tag = items[i].querySelector('.update-tag');
      if (tag) { tag.remove(); }
      break;
    }
  }
  // Persist to localStorage
  try {
    var read = JSON.parse(localStorage.getItem('wiki_read_tags')||'[]');
    if (read.indexOf(slug) === -1) { read.push(slug); }
    localStorage.setItem('wiki_read_tags', JSON.stringify(read));
  } catch(e){}
}

function setUpdateTagStatus(msg) {
  var el = document.getElementById("update-tag-status");
  if (el) el.textContent = msg;
}

// --- System Monitor (right rail, bottom-right, collapsed by default) ---
function escHtml(s){
  return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; });
}
// Open the workflow source for a version entry — render in-page (no download)
function openWorkflow(cat, key){
  if(typeof SYS_WORKFLOW_CONTENT === 'undefined') return;
  var c = (cat === 'page') ? SYS_WORKFLOW_CONTENT.page : (SYS_WORKFLOW_CONTENT[cat] ? SYS_WORKFLOW_CONTENT[cat][key] : null);
  if(!c) return;
  var label = (cat === 'page') ? '应用更新记录' : key;
  var rawLink = (typeof SYS_WORKFLOW_LINKS !== 'undefined') ? ((cat === 'page') ? SYS_WORKFLOW_LINKS.page : (SYS_WORKFLOW_LINKS[cat] ? SYS_WORKFLOW_LINKS[cat][key] : null)) : null;
  var html = DOMPurify.sanitize(marked.parse(c), { ADD_ATTR: ['target'] });
  document.getElementById('wf-modal-title').textContent = label + (cat === 'page' ? '（应用更新记录）' : '（工作流）');
  var body = document.getElementById('wf-modal-body');
  body.innerHTML = html;
  if(rawLink){
    body.insertAdjacentHTML('beforeend', '<p class="wf-modal-raw"><a href="' + escHtml(rawLink) + '" target="_blank" rel="noopener">查看原始文件 ↗</a></p>');
  }
  var modal = document.getElementById('wf-modal');
  modal.classList.add('open');
  modal.setAttribute('aria-hidden', 'false');
}
function closeWfModal(){
  var modal = document.getElementById('wf-modal');
  if(!modal) return;
  modal.classList.remove('open');
  modal.setAttribute('aria-hidden', 'true');
  document.getElementById('wf-modal-body').innerHTML = '';
}
document.addEventListener('keydown', function(e){ if(e.key === 'Escape'){ closeWfModal(); closeUvModal(); } });
// Toggle the collapsed/expanded state of the monitor card
function toggleSysMon(){
  var card = document.getElementById('sysmon-card');
  var toggle = document.getElementById('sysmon-toggle');
  if(!card) return;
  var open = card.classList.toggle('open');
  if(toggle) toggle.classList.toggle('collapsed', !open);
}
function renderSysMon(){
  var body = document.getElementById('sysmon-body');
  if(!body) return;
  var data = (typeof SYS_VERSIONS !== 'undefined' && SYS_VERSIONS) ? SYS_VERSIONS : {page:'?',schema:{},skills:{}};
  var links = (typeof SYS_WORKFLOW_LINKS !== 'undefined' && SYS_WORKFLOW_LINKS) ? SYS_WORKFLOW_LINKS : null;
  var upd = (typeof SYS_UPDATES !== 'undefined' && SYS_UPDATES) ? SYS_UPDATES : null;
  function clickable(cat, key){
    if(!links) return false;
    return (cat === 'page') ? !!links.page : !!(links[cat] && links[cat][key]);
  }
  function metaHtml(cat, key){
    var ver = (cat === 'page') ? (data.page || '') : ((data[cat] && data[cat][key]) ? 'v' + data[cat][key] : '');
    var when = '';
    if(upd){
      var u = (cat === 'page') ? upd.page : (upd[cat] ? upd[cat][key] : null);
      if(u) when = u.rel || u.date;
    }
    var parts = [];
    if(when) parts.push('📝 ' + escHtml(when));
    if(ver) parts.push(escHtml(String(ver)));
    return parts.join(' · ');
  }
  function rowsHtml(cat, obj){
    return Object.keys(obj).map(function(k){
      var c = clickable(cat, k);
      var click = c ? ' onclick="openWorkflow(\'' + cat + '\',\'' + k + '\')" title="点击查看 ' + escHtml(k) + ' 工作流"' : '';
      var arrow = c ? '<span class="arrow">↗</span>' : '';
      return '<div class="sysmon-ver-row"' + click + '><span class="sysmon-ver-name">' + escHtml(k) + arrow + '</span><span class="sysmon-ver-meta">' + metaHtml(cat, k) + '</span></div>';
    }).join('');
  }
  function groupHtml(title, cat, obj){
    if(!obj || !Object.keys(obj).length) return '';
    return '<div class="sysmon-group"><div class="sysmon-group-title">' + title + '</div>' + rowsHtml(cat, obj) + '</div>';
  }
  var html = '';
  html += '<div class="sysmon-group"><div class="sysmon-group-title">页面</div><div class="sysmon-ver-row" onclick="openWorkflow(\'page\',\'\')" title="点击查看页面更新工作流"><span class="sysmon-ver-name">页面<span class="arrow">↗</span></span><span class="sysmon-ver-meta">' + metaHtml('page','') + '</span></div></div>';
  html += groupHtml('Schema', 'schema', data.schema);
  html += groupHtml('Skills', 'skills', data.skills);
  body.innerHTML = html;
  // collapsed toggle shows the page version at a glance
  var lbl = document.getElementById('sysmon-toggle-label');
  if(lbl) lbl.textContent = '系统监控 v' + (data.page || '?');
}
renderSysMon();
