'use strict';

const BRAND_TITLE = '\u5e73\u884c\u7ebf \u00b7 AI \u804a\u5929';
const LOGO_URL = '/logo-lines-mark.png';
const FAVICON_URL = '/favicon.svg';

/** Brand only the document shell; native conversation titles are never inspected. */
function applyShellBranding(html) {
  if (typeof html !== 'string' || !/<\/head\s*>/i.test(html)) {
    throw new TypeError('Expected the pinned LibreChat HTML shell');
  }
  const withoutOldIcons = html.replace(/<link\b[^>]*>\s*/gi, tag => {
    const rel = /\brel\s*=\s*(["'])(.*?)\1/i.exec(tag)?.[2]?.toLowerCase().split(/\s+/) || [];
    return rel.some(value => ['icon', 'apple-touch-icon', 'apple-touch-icon-precomposed'].includes(value)) ? '' : tag;
  });
  const titled = withoutOldIcons.replace(/<title\b[^>]*>[\s\S]*?<\/title\s*>/i, `<title>${BRAND_TITLE}</title>`);
  return titled.replace(/<\/head\s*>/i,
    `<link rel="icon" type="image/svg+xml" href="${FAVICON_URL}">\n` +
    `<link rel="apple-touch-icon" href="${LOGO_URL}">\n</head>`);
}

/** Fixed public brand asset only; no user-controlled target or file directory exposure. */
function installBrandLogoRoute(app) {
  app.get('/assets/logo.svg', (_req, res) => {
    res.set('Cache-Control', 'public, max-age=300');
    return res.redirect(302, LOGO_URL);
  });
}

module.exports = { applyShellBranding, installBrandLogoRoute, BRAND_TITLE, LOGO_URL, FAVICON_URL };
