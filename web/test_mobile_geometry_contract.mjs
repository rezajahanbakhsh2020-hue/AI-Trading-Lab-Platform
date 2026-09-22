import { chromium } from 'playwright';

/**
 * Mobile Viewport Geometry Contract Verification Suite
 *
 * Verifies that no route, page, subview, table, flex item, card, modal, or language setting
 * causes global horizontal viewport expansion across all mobile, landscape, and desktop viewports.
 */

const routes = [
  '/',
  '/dashboard',
  '/timeline',
  '/screener',
  '/markets',
  '/watchlist',
  '/signals',
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
  '/settings'
];

const languages = ['en', 'fa', 'ar', 'tr'];

const viewports = [
  { name: '360x800 (Galaxy S23-ish small)', width: 360, height: 800 },
  { name: '390x844 (iPhone 12/13/14)', width: 390, height: 844 },
  { name: '430x932 (iPhone Pro Max)', width: 430, height: 932 },
  { name: '800x360 (Landscape)', width: 800, height: 360 },
  { name: '1280x800 (Desktop)', width: 1280, height: 800 },
];

async function run() {
  const browser = await chromium.launch({ headless: true });
  const violations = [];

  for (const lang of languages) {
    for (const vp of viewports) {
      const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
      const page = await context.newPage();

      await page.addInitScript(({ lang }) => {
        localStorage.setItem('ai_trading_lab_lang', lang);
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
      }, { lang });

      for (const route of routes) {
        const url = `http://localhost:3000${route}`;
        await page.goto(url, { waitUntil: 'networkidle' });
        await page.waitForTimeout(50);

        const geometry = await page.evaluate(() => {
          const docWidth = document.documentElement.scrollWidth;
          const bodyWidth = document.body.scrollWidth;
          const viewportWidth = window.innerWidth;
          const appShell = document.querySelector('.app-shell');
          const workspace = document.querySelector('.workspace');
          const boundedContainer = document.querySelector('.bounded-page-container');

          const appShellWidth = appShell ? appShell.scrollWidth : 0;
          const workspaceWidth = workspace ? workspace.scrollWidth : 0;
          const containerWidth = boundedContainer ? boundedContainer.scrollWidth : 0;

          // Find elements wider than viewport
          const wideElements = [];
          const all = document.querySelectorAll('*');
          all.forEach((el) => {
            if (el.scrollWidth > viewportWidth + 1.5) { // 1.5px rounding tolerance
              const className = typeof el.className === 'string' ? el.className : '';
              const tag = el.tagName;
              const textSnippet = (el.textContent || '').substring(0, 40).replace(/\s+/g, ' ');
              const rect = el.getBoundingClientRect();
              wideElements.push({
                tag,
                className,
                scrollWidth: el.scrollWidth,
                rectWidth: rect.width,
                textSnippet
              });
            }
          });

          return {
            docWidth,
            bodyWidth,
            viewportWidth,
            appShellWidth,
            workspaceWidth,
            containerWidth,
            hasOverflow: docWidth > viewportWidth + 1.5,
            wideElements
          };
        });

        if (geometry.hasOverflow) {
          violations.push({
            lang,
            viewport: vp.name,
            route,
            viewportWidth: geometry.viewportWidth,
            docWidth: geometry.docWidth,
            appShellWidth: geometry.appShellWidth,
            workspaceWidth: geometry.workspaceWidth,
            containerWidth: geometry.containerWidth,
            wideElements: geometry.wideElements
          });
        }
      }
      await context.close();
    }
  }

  await browser.close();

  console.log('\n================ MOBILE GEOMETRY CONTRACT VERIFICATION ================');
  if (violations.length === 0) {
    console.log('✅ CONTRACT VERIFIED: ZERO HORIZONTAL OVERFLOW DETECTED ACROSS ALL 23 ROUTES, 4 LANGUAGES, AND 5 VIEWPORTS!');
    process.exit(0);
  } else {
    console.log(`❌ FOUND ${violations.length} GEOMETRY CONTRACT VIOLATIONS:\n`);
    for (const v of violations) {
      console.log(`Route: ${v.route} [Lang: ${v.lang} | Viewport: ${v.viewport}]`);
      console.log(`  Viewport Width: ${v.viewportWidth}px | Document scrollWidth: ${v.docWidth}px (Overflow: +${v.docWidth - v.viewportWidth}px)`);
      console.log(`  AppShell scrollWidth: ${v.appShellWidth}px | Workspace scrollWidth: ${v.workspaceWidth}px | Container: ${v.containerWidth}px`);
      console.log('  Top Wide Elements:');
      for (const el of v.wideElements.slice(0, 5)) {
        console.log(`    - <${el.tag} class="${el.className}"> scrollWidth=${el.scrollWidth}px rectWidth=${Math.round(el.rectWidth)}px text="${el.textSnippet}"`);
      }
      console.log('--------------------------------------------------\n');
    }
    process.exit(1);
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
