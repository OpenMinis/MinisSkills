/**
 * AppStorePriceAPI — appstoreprice.org 浏览器内 API 工具
 *
 * 必须在 appstoreprice.org 页面上下文中执行（以便访问 webpackChunk_N_E）。
 * 使用方式：将此文件内容与查询逻辑一起传入 browser_use execute_js。
 *
 * 返回对象：{ search, list, prices, prices_all }
 */
function AppStorePriceAPI() {
  // base URL 从当前页面 origin 推断，无需硬编码
  const BASE = location.origin;
  // Next.js RSC 请求头（协议标准）
  const RSC_HEADERS = { 'RSC': '1' };

  /**
   * 动态定位签名函数：
   * 遍历所有 webpack module，找到函数体含 X-Timestamp / X-Signature 的导出函数。
   * 不依赖 module ID 或导出属性名，网站重新部署后依然有效。
   *
   * 注意：签名函数内部有路径白名单检查，用任意路径探测会返回 {}，
   * 因此改为通过函数源码特征字符串识别，而非行为探测。
   */
  function _getSignFn() {
    const chunks = self.webpackChunk_N_E;
    if (!chunks) throw new Error('webpackChunk_N_E not found — 请先导航到 appstoreprice.org 页面');

    const define = (t, defs) => {
      for (const k in defs)
        Object.defineProperty(t, k, { get: defs[k], enumerable: true });
    };

    for (const chunk of chunks) {
      const [, modules] = chunk;
      if (!modules) continue;
      for (const k of Object.keys(modules)) {
        try {
          const exp = {};
          modules[k]({ exports: exp }, exp, { d: define });
          for (const fn of Object.values(exp)) {
            if (typeof fn !== 'function') continue;
            const src = fn.toString();
            // 通过函数体特征识别：同时包含签名头 key 和 FNV-1a 初始值
            if (src.includes('X-Timestamp') && src.includes('X-Signature')) {
              return fn;
            }
          }
        } catch(e) {}
      }
    }
    throw new Error('签名函数未找到 — 网站结构可能已变更');
  }

  const _sign = _getSignFn();

  async function _signedGet(path, params = {}) {
    const qs = new URLSearchParams(params).toString();
    const resp = await fetch(`${BASE}${path}?${qs}`, { headers: _sign(path) });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${await resp.text()}`);
    return resp.json();
  }

  /**
   * 搜索应用
   * @returns {{ apps: Array<{appStoreId, name, developer, iconUrl, category}>, hasMore, total }}
   */
  async function search(query, page = 1, limit = 20) {
    return _signedGet('/api/apps/search', { q: query, page, limit });
  }

  /**
   * 分页获取应用列表
   * @returns {{ apps: Array, hasMore, total }}
   */
  async function list(page = 1, limit = 20) {
    return _signedGet('/api/apps/paginated', { page, limit });
  }

  /**
   * 获取指定 App 所有订阅 tier 的全球价格
   * 适合多档订阅（如 Claude Pro/Max、ChatGPT Plus/Pro 等）
   * @returns {Array<Array<{region, regionName, currency, price, priceUsd, priceCny}>>}
   *   每个元素对应一个订阅档位，内部按 priceUsd 升序
   */
  async function prices_all(appStoreId, locale = 'zh') {
    const resp = await fetch(`${BASE}/${locale}/apps/${appStoreId}`, { headers: RSC_HEADERS });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const text = await resp.text();
    const regex = /"prices":(\[[\s\S]*?\])/g;
    let m;
    const result = [];
    while ((m = regex.exec(text)) !== null) {
      try { result.push(JSON.parse(m[1])); } catch(e) {}
    }
    return result;
  }

  /**
   * 获取指定 App 第一个 tier 的全球价格（单一订阅 App 用这个即可）
   * 多 tier 订阅请用 prices_all()
   * @returns {Array<{region, regionName, currency, price, priceUsd, priceCny}>}
   */
  async function prices(appStoreId, locale = 'zh') {
    return (await prices_all(appStoreId, locale))[0] || [];
  }

  return { search, list, prices, prices_all };
}
