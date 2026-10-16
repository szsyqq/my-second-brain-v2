// Verify the unified 本页/全部 update-history tabs in the built knowledge base.
// 运行方式（puppeteer-core 走托管 node 与共享 node_modules）：
//   NODE_PATH=/Users/panyp/.workbuddy/binaries/node/workspace/node_modules \
//   /Users/panyp/.workbuddy/binaries/node/versions/22.22.2-3/bin/node \
//   scripts/<本文件名> "/绝对路径/知识库.html"
// 退出码 0 = 全部断言通过；改动更新历史抽屉 / tab / 页面入口后应重跑。
const puppeteer = require('puppeteer-core');
const path = process.argv[2];
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';

const PAGES = {
  noH1WithRecords: 'sources/2026-07-17-RayDalio百年风暴五大力量的作用', // 真正无 H1 → 兜底落点
  h1WithRecords: 'topics/02_投资/02-20_策略专题/02-15_S5_A股策略',
  snapsOnly: 'entities/AI Agent',
  nothing: 'Interesting_findings/01_第一期_不请自来的关联',
};

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--allow-file-access-from-files', '--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).split('\n')[0]));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text().slice(0, 160)); });

  await page.goto('file://' + path, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction('typeof files === "object" && Object.keys(files).length > 100', { timeout: 60000 });
  await sleep(700);

  const results = [];
  const ok = (name, pass, detail) => results.push({ name, pass, detail });
  const readHead = () => ({
    heading: (document.getElementById('update-drawer-heading') || {}).textContent || '',
    sub: (document.getElementById('update-drawer-subheading') || {}).textContent || '',
  });

  // ---------- 1. tab structure ----------
  const tabs = await page.evaluate(() => {
    const list = [...document.querySelectorAll('#update-drawer-tabs .upd-tab')];
    return {
      count: list.length,
      labels: list.map(b => b.textContent.replace(/\(\d+\)/g, '').trim()),
      hasStrategy: list.some(b => /策略/.test(b.textContent)),
    };
  });
  ok('抽屉恰好 2 个 tab', tabs.count === 2, JSON.stringify(tabs.labels));
  ok('两个 tab = 本页更新历史 / 全部更新历史',
    tabs.labels[0] === '本页更新历史' && tabs.labels[1] === '全部更新历史', JSON.stringify(tabs.labels));
  ok('「策略」tab 已移除', tabs.hasStrategy === false, 'hasStrategy=' + tabs.hasStrategy);

  // ---------- 2. home state: page tab disabled & refusing ----------
  const home = await page.evaluate(() => {
    switchUpdateTab('page');
    return {
      updTab,
      disabled: document.getElementById('upd-tab-page').disabled,
      allActive: document.getElementById('upd-tab-all').classList.contains('active'),
      allBadge: document.getElementById('upd-tab-all-n').textContent,
      pageBadge: document.getElementById('upd-tab-page-n').textContent,
    };
  });
  ok('首页：本页 tab 呈禁用态（首屏即生效）', home.disabled === true, JSON.stringify(home));
  ok('首页：切到本页 tab 被拒绝', home.updTab === 'all', 'updTab=' + home.updTab);
  ok('首页：全部 tab 显示记录数徽标', /^\(\d+\)$/.test(home.allBadge), 'badge=' + home.allBadge);

  // ---------- 3. top button opens 全部 tab ----------
  const globalView = await page.evaluate(async () => {
    document.getElementById('update-hist-btn').click();
    await new Promise(r => setTimeout(r, 250));
    return {
      open: document.getElementById('update-drawer').classList.contains('open'),
      updTab,
      records: document.querySelectorAll('#update-drawer-body .update-record').length,
      total: (updateRecords || []).length,
    };
  });
  ok('顶部「更新历史」→ 打开抽屉并进入全部 tab',
    globalView.open && globalView.updTab === 'all', JSON.stringify(globalView));
  ok('全部 tab 列出全部更新记录',
    globalView.records === globalView.total && globalView.total > 0, `${globalView.records}/${globalView.total}`);

  // ---------- 4. page WITHOUT h1 → fallback entry button ----------
  const fb = await page.evaluate(async (slug) => {
    closeUpdateDrawer();
    openPage(slug);
    await new Promise(r => setTimeout(r, 500));
    const b = document.getElementById('page-rec-btn');
    return {
      exists: !!b,
      label: b ? b.textContent : null,
      inHeader: b ? !!b.closest('#content-header') : false,
      inTitleRow: b ? !!b.closest('.page-title-row') : false,
      h1Count: document.querySelectorAll('#content-area h1').length,
      drawerClosed: !document.getElementById('update-drawer').classList.contains('open'),
    };
  }, PAGES.noH1WithRecords);
  ok('无 H1 页面现在也有入口按钮（兜底到头部栏）',
    fb.exists && fb.inHeader && !fb.inTitleRow && fb.h1Count === 0, JSON.stringify(fb));
  ok('打开页面不再自动弹出抽屉', fb.drawerClosed === true, 'drawerClosed=' + fb.drawerClosed);

  // ---------- 5. clicking it opens the 本页 tab with correct counts ----------
  const pageTab = await page.evaluate(async (slug) => {
    document.getElementById('page-rec-btn').click();
    await new Promise(r => setTimeout(r, 300));
    const body = document.getElementById('update-drawer-body');
    return {
      updTab,
      open: document.getElementById('update-drawer').classList.contains('open'),
      ...(() => ({ heading: (document.getElementById('update-drawer-heading') || {}).textContent,
                   sub: (document.getElementById('update-drawer-subheading') || {}).textContent }))(),
      sections: [...body.querySelectorAll('.upd-sect')].map(e => e.textContent.trim()),
      items: body.querySelectorAll('.upd-item').length,
      expected: getPageUpdateEntries(slug).length,
      snaps: getPageSnapshots(slug).length,
      pageTabText: document.getElementById('upd-tab-page').textContent,
      pageTabDisabled: document.getElementById('upd-tab-page').disabled,
    };
  }, PAGES.noH1WithRecords);
  ok('本页入口按钮 → 打开抽屉且停在 本页 tab',
    pageTab.updTab === 'page' && pageTab.open, JSON.stringify({ updTab: pageTab.updTab, open: pageTab.open }));
  ok('本页 tab 计数与数据一致',
    pageTab.items === pageTab.expected + pageTab.snaps && pageTab.expected > 0,
    `渲染 ${pageTab.items} = 记录 ${pageTab.expected} + 快照 ${pageTab.snaps}`);
  ok('本页 tab 含「本页历次更新记录」小节',
    pageTab.sections.join('|').includes('本页历次更新记录'), JSON.stringify(pageTab.sections));
  ok('有页面时本页 tab 恢复可用且带计数',
    pageTab.pageTabDisabled === false && /^本页更新历史\(\d+\)$/.test(pageTab.pageTabText.replace(/\s/g, '')),
    JSON.stringify({ t: pageTab.pageTabText, d: pageTab.pageTabDisabled }));
  ok('再点一次按钮可收起抽屉（toggle 语义一致）', await page.evaluate(async () => {
    document.getElementById('page-rec-btn').click();
    await new Promise(r => setTimeout(r, 200));
    return !document.getElementById('update-drawer').classList.contains('open');
  }), 'second click closes');

  // ---------- 6. switching tabs WHILE on the page tab (the old bug) ----------
  const switchBack = await page.evaluate(async () => {
    document.getElementById('page-rec-btn').click();       // reopen on 本页
    await new Promise(r => setTimeout(r, 250));
    document.getElementById('upd-tab-all').click();
    await new Promise(r => setTimeout(r, 200));
    const afterAll = {
      updTab,
      allCount: document.querySelectorAll('#update-drawer-body .update-record').length,
      heading: (document.getElementById('update-drawer-heading') || {}).textContent,
    };
    document.getElementById('upd-tab-page').click();
    await new Promise(r => setTimeout(r, 200));
    return { afterAll, backToPage: updTab, pageItems: document.querySelectorAll('#update-drawer-body .upd-item').length };
  });
  ok('本页 tab 状态下切「全部」生效（旧版此处失效）',
    switchBack.afterAll.updTab === 'all' && switchBack.afterAll.allCount > 0 &&
    switchBack.afterAll.heading.includes('整个知识库'),
    JSON.stringify(switchBack.afterAll));
  ok('切回本页 tab 正常', switchBack.backToPage === 'page' && switchBack.pageItems > 0,
    'items=' + switchBack.pageItems);

  // ---------- 7. navigate while drawer open on 本页 → content must follow ----------
  const follow = await page.evaluate(async (slug) => {
    openPage(slug);
    await new Promise(r => setTimeout(r, 600));
    const b = document.getElementById('page-rec-btn');
    return {
      exists: !!b,
      label: b ? b.textContent : null,
      heading: (document.getElementById('update-drawer-heading') || {}).textContent,
      sub: (document.getElementById('update-drawer-subheading') || {}).textContent,
      sections: [...document.querySelectorAll('#update-drawer-body .upd-sect')].map(e => e.textContent.trim()),
    };
  }, PAGES.snapsOnly);
  ok('快照-only 页面按钮显示为「本页历史快照」',
    follow.exists && /本页历史快照/.test(follow.label || ''), follow.label);
  ok('导航后抽屉跟随新页面（不再残留上一页）',
    follow.heading.includes('AI Agent') && follow.sub.startsWith('0 次更新记录'),
    JSON.stringify({ heading: follow.heading, sub: follow.sub }));
  ok('快照小节存在', follow.sections.join('|').includes('本页内容快照'), JSON.stringify(follow.sections));

  // ---------- 8. page with neither → no button, empty state ----------
  const nothing = await page.evaluate(async (slug) => {
    openPage(slug);
    await new Promise(r => setTimeout(r, 500));
    const hasBtn = !!document.getElementById('page-rec-btn');
    switchUpdateTab('page');
    await new Promise(r => setTimeout(r, 200));
    const body = document.getElementById('update-drawer-body');
    return { hasBtn, updTab, emptyText: (body.querySelector('#update-drawer-empty') || {}).textContent || '',
             sub: (document.getElementById('update-drawer-subheading') || {}).textContent };
  }, PAGES.nothing);
  ok('无记录无快照的页面不显示入口按钮', nothing.hasBtn === false, 'hasBtn=' + nothing.hasBtn);
  ok('该页面本页 tab 显示空状态提示', /暂无修改记录/.test(nothing.emptyText), JSON.stringify(nothing.emptyText));

  // ---------- 9. h1 page → button next to the title ----------
  const h1page = await page.evaluate(async (slug) => {
    closeUpdateDrawer();
    openPage(slug);
    await new Promise(r => setTimeout(r, 500));
    const b = document.getElementById('page-rec-btn');
    return {
      exists: !!b,
      inTitleRow: b ? !!b.closest('.page-title-row') : false,
      label: b ? b.textContent : null,
      expected: getPageUpdateEntries(slug).length,
      snaps: getPageSnapshots(slug).length,
    };
  }, PAGES.h1WithRecords);
  ok('有 H1 页面按钮落在标题行且计数正确',
    h1page.exists && h1page.inTitleRow && h1page.label === `本页更新历史 (${h1page.expected})`,
    JSON.stringify(h1page));

  // ---------- 10. 首页卡片「查看完整更新历史」 ----------
  const homeCard = await page.evaluate(async () => {
    closeUpdateDrawer();
    showHome();
    await new Promise(r => setTimeout(r, 300));
    const card = [...document.querySelectorAll('.home-card-go')].find(e => /查看完整更新历史/.test(e.textContent));
    if (!card) return { found: false };
    card.click();
    await new Promise(r => setTimeout(r, 300));
    return {
      found: true,
      open: document.getElementById('update-drawer').classList.contains('open'),
      updTab,
      records: document.querySelectorAll('#update-drawer-body .update-record').length,
      pageTabDisabled: document.getElementById('upd-tab-page').disabled,
    };
  });
  ok('首页「查看完整更新历史」打开全部 tab（原先误跳最新记录页）',
    homeCard.found && homeCard.open && homeCard.updTab === 'all' && homeCard.records > 0,
    JSON.stringify(homeCard));
  ok('回到首页后本页 tab 重新禁用', homeCard.pageTabDisabled === true, 'disabled=' + homeCard.pageTabDisabled);

  // ---------- 11. no page errors ----------
  ok('无 JS 报错', errors.length === 0, errors.slice(0, 4).join(' | '));

  let failed = 0;
  for (const r of results) {
    if (!r.pass) failed++;
    console.log(`${r.pass ? '✅' : '❌'} ${r.name}${r.pass ? '' : '  → ' + r.detail}`);
  }
  console.log(`\n${results.length - failed}/${results.length} 通过`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
