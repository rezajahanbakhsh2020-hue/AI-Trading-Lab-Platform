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

  console.log('Searching for intrinsic width expanders on 360px viewport...\n');

  for (const route of routes) {
    const url = `http://localhost:3000${route}`;
    await page.goto(url, { waitUntil: 'networkidle' });
    await page.waitForTimeout(50);

    const findings = await page.evaluate(() => {
      const results = [];
      const workspace = document.querySelector('.workspace');
      const viewportWidth = window.innerWidth;

      if (!workspace) return results;

      // Check all elements inside workspace
      const elements = workspace.querySelectorAll('*');
      elements.forEach((el) => {
        const rect = el.getBoundingClientRect();
        const scrollWidth = el.scrollWidth;
        const clientWidth = el.clientWidth;
        const className = typeof el.className === 'string' ? el.className : '';
        const tagName = el.tagName.toLowerCase();

        // Check if element bounding box or scrollWidth exceeds viewportWidth (360px)
        if (rect.width > viewportWidth + 1.5 || scrollWidth > viewportWidth + 1.5) {
          results.push({
            tag: tagName,
            className,
            rectWidth: Math.round(rect.width),
            scrollWidth,
            clientWidth,
            style: el.getAttribute('style') || '',
            textSnippet: (el.textContent || '').substring(0, 50).replace(/\s+/g, ' ')
          });
        }
      });

      return results;
    });

    if (findings.length > 0) {
      console.log(`=== Route: ${route} ===`);
      for (const f of findings.slice(0, 10)) {
        console.log(`  <${f.tag} class="${f.className}" style="${f.style}">`);
        console.log(`    rectWidth=${f.rectWidth}px, scrollWidth=${f.scrollWidth}px, clientWidth=${f.clientWidth}px`);
        console.log(`    Text: "${f.textSnippet}"`);
      }
      console.log('');
    }
  }

  await browser.close();
}

run().catch(console.error);
