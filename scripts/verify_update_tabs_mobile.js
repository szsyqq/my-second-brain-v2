// Mobile-viewport check: the two update-history tabs must stay usable at 390px.
// 运行方式（puppeteer-core 走托管 node 与共享 node_modules）：
//   NODE_PATH=/Users/panyp/.workbuddy/binaries/node/workspace/node_modules \
//   /Users/panyp/.workbuddy/binaries/node/versions/22.22.2-3/bin/node \
//   scripts/<本文件名> "/绝对路径/知识库.html"
// 退出码 0 = 全部断言通过；改动更新历史抽屉 / tab / 页面入口后应重跑。
const puppeteer = require('puppeteer-core');
const path = process.argv[2];
const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const SLUG = 'topics/02_投资/02-20_策略专题/02-15_S5_A股策略';
const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME, headless: 'new',
    args: ['--allow-file-access-from-files', '--no-sandbox'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 390, height: 844, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e).split('\n')[0]));

  await page.goto('file://' + path, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction('typeof files === "object" && Object.keys(files).length > 100', { timeout: 60000 });
  await sleep(700);

  const r = await page.evaluate(async (slug) => {
    openPage(slug);
    await new Promise(r => setTimeout(r, 500));
    // open the drawer from the page button (mobile draws it full-width)
    const btn = document.getElementById('page-rec-btn');
    const btnVisible = !!btn && btn.offsetWidth > 0;
    if (btn) btn.click();
    await new Promise(r => setTimeout(r, 400));

    const drawer = document.getElementById('update-drawer');
    const tabs = [...document.querySelectorAll('#update-drawer-tabs .upd-tab')];
    const body = document.getElementById('update-drawer-body');

    const pageHeading = (document.getElementById('update-drawer-heading') || {}).textContent;
    // the 全部 tab holds the longest list — use it for the scroll-to-end test
    document.getElementById('upd-tab-all').click();
    await new Promise(r => setTimeout(r, 300));
    const allCount = document.querySelectorAll('#update-drawer-body .update-record').length;

    // can the drawer body be scrolled to its very end?
    body.scrollTop = body.scrollHeight;
    await new Promise(r => setTimeout(r, 120));
    const maxTop = body.scrollHeight - body.clientHeight;
    const atEnd = Math.abs(body.scrollTop - maxTop) <= 2;

    return {
      btnVisible,
      allCount,
      drawerOpen: drawer.classList.contains('open'),
      drawerWidth: Math.round(drawer.getBoundingClientRect().width),
      viewport: window.innerWidth,
      tabLabels: tabs.map(t => t.textContent.trim().replace(/\(\d+\)/, '')),
      tabWidths: tabs.map(t => Math.round(t.getBoundingClientRect().width)),
      tabClipped: tabs.some(t => t.scrollWidth > t.clientWidth + 1),
      hOverflow: drawer.scrollWidth > drawer.clientWidth + 1,
      bodyScrollable: maxTop > 0,
      atEnd,
      overscrollOk: getComputedStyle(body).overscrollBehaviorY === 'contain',
      heading: pageHeading,
    };
  }, SLUG);

  const checks = [
    ['移动端：本页入口按钮可见', r.btnVisible],
    ['移动端：抽屉全宽打开', r.drawerOpen && r.drawerWidth >= r.viewport - 2],
    ['移动端：两个 tab 文案正确', r.tabLabels[0] === '本页更新历史' && r.tabLabels[1] === '全部更新历史'],
    ['移动端：tab 文案未被裁切', r.tabClipped === false],
    ['移动端：抽屉无横向溢出', r.hOverflow === false],
    ['移动端：全部 tab 列表可滚到底（长列表）', r.allCount > 5 && r.bodyScrollable && r.atEnd],
    ['移动端：回弹隔离生效', r.overscrollOk === true],
    ['移动端：标题正确', /S5|A股策略/.test(r.heading || '')],
    ['移动端：无 JS 报错', errors.length === 0],
  ];
  let failed = 0;
  for (const [name, pass] of checks) { if (!pass) failed++; console.log(`${pass ? '✅' : '❌'} ${name}`); }
  console.log('\n明细: ' + JSON.stringify(r));
  console.log(`\n${checks.length - failed}/${checks.length} 通过`);
  await browser.close();
  process.exit(failed ? 1 : 0);
})();
