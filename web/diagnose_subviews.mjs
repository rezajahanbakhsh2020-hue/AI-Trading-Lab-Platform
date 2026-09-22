import { chromium } from 'playwright';

const routes = [
  '/',
  '/dashboard',
  '/signals',
  '/screener',
  '/markets',
  '/watchlist',
  '/strategies',
  '/backtest',
  '/performance',
  '/risk',
  '/audit',
  '/intents',
  '/users',
  '/health',
  '/monitoring',
  '/providers',
  '/academy',
  '/ai',
  '/alerts',
  '/notifications',
  '/help',
  '/logs',
  '/settings'
];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const viewport = { width: 360, height: 800 };
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();

  await page.addInitScript(() => {
    localStorage.setItem('ai_trading_lab_lang', 'en');
    localStorage.setItem('ai_trading_lab_auth', JSON.stringify({
      token: 'test_admin_token',
      user: {
        userId: 'admin_owner',
        role: 'admin',
        isActive: true,
        isPermanentAdmin: true,
        allowedSymbols: ['XAUUSD', 'EURUSD', 'GBPUSD', 'BTCUSD', 'SPX500'],
        permissions: ['read:signals', 'write:intents', 'admin:all']
      }
    }));
  });

  for (const route of routes) {
    const url = `http://localhost:3000${route}`;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(50);

    const report = await page.evaluate(() => {
      const pageEl = document.querySelector('.page');
      if (!pageEl) return null;

      const items = [];
      const walk = (node) => {
        if (!node || node.nodeType !== 1) return;
        const rect = node.getBoundingClientRect();
        const sw = node.scrollWidth;
        const cw = node.clientWidth;
        const tag = node.tagName.toLowerCase();
        const cls = typeof node.className === 'string' ? node.className : '';

        // Check if node has scrollWidth > cw (internal overflow) or sw > 360
        if (sw > cw + 1 || sw > 336 + 1) {
          items.push({
            tag,
            cls,
            rectW: Math.round(rect.width),
            cw,
            sw,
            overflowX: window.getComputedStyle(node).overflowX,
            minWidth: window.getComputedStyle(node).minWidth,
            maxWidth: window.getComputedStyle(node).maxWidth
          });
        }
        for (const child of node.children) {
          walk(child);
        }
      };

      walk(pageEl);
      return {
        pageSW: pageEl.scrollWidth,
        pageCW: pageEl.clientWidth,
        items
      };
    });

    console.log(`\nRoute [${route}] -> page scrollWidth: ${report?.pageSW}px (clientWidth: ${report?.pageCW}px)`);
    if (report && report.items.length > 0) {
      console.log('  Overflowing or unconstrained elements in tree:');
      for (const item of report.items) {
        console.log(`    <${item.tag} class="${item.cls}"> -> rectW:${item.rectW}cw:${item.cw} sw:${item.sw} (overflowX:${item.overflowX}, minW:${item.minWidth}, maxW:${item.maxWidth})`);
      }
    }
  }

  await browser.close();
}

run().catch(console.error);
