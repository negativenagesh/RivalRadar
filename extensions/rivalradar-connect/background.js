/**
 * RivalRadar Connect — MV3 service worker.
 * Reads Chrome cookies for a platform and POSTs them with a pairing code.
 */

const PLATFORM_SPECS = {
  linkedin: {
    domains: ["linkedin.com"],
    urls: ["https://www.linkedin.com/", "https://linkedin.com/"],
    required: ["li_at"],
  },
  x: {
    domains: ["x.com", "twitter.com"],
    urls: ["https://x.com/", "https://twitter.com/"],
    required: ["auth_token"],
  },
  instagram: {
    domains: ["instagram.com"],
    urls: ["https://www.instagram.com/"],
    required: ["sessionid"],
  },
  tiktok: {
    domains: ["tiktok.com"],
    urls: ["https://www.tiktok.com/"],
    required: ["sessionid"],
  },
  threads: {
    domains: ["threads.net"],
    urls: ["https://www.threads.net/"],
    required: ["sessionid"],
  },
};

async function collectCookies(platform) {
  const spec = PLATFORM_SPECS[platform];
  if (!spec) throw new Error(`Unsupported platform: ${platform}`);

  const byName = new Map();
  for (const domain of spec.domains) {
    const batch = await chrome.cookies.getAll({ domain });
    for (const c of batch) {
      if (!byName.has(c.name)) byName.set(c.name, c);
    }
  }
  for (const url of spec.urls) {
    const batch = await chrome.cookies.getAll({ url });
    for (const c of batch) {
      if (!byName.has(c.name)) byName.set(c.name, c);
    }
  }

  const cookies = [...byName.values()].map((c) => ({
    name: c.name,
    value: c.value,
    domain: c.domain,
    path: c.path || "/",
    secure: c.secure,
    httpOnly: c.httpOnly,
    expirationDate: c.expirationDate,
  }));

  const have = new Set(cookies.map((c) => c.name.toLowerCase()));
  const missing = spec.required.filter((n) => !have.has(n.toLowerCase()));
  if (missing.length) {
    throw new Error(
      `Not signed in to ${platform} in Chrome (missing ${missing.join(", ")}). Open that site, stay logged in, then retry.`,
    );
  }
  return cookies;
}

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (!msg || msg.type !== "QUICK_CONNECT") return false;
  (async () => {
    try {
      const { platform, code, gatewayUrl, workspaceId } = msg;
      const base = (gatewayUrl || "").replace(/\/$/, "");
      if (!base) throw new Error("Set the RivalRadar API URL in the extension popup.");
      if (!code || String(code).trim().length < 4) {
        throw new Error("Enter the pairing code from the RivalRadar Connect dialog.");
      }
      const cookies = await collectCookies(platform);
      const res = await fetch(`${base}/connections/${platform}/quick`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code: String(code).trim().toUpperCase(),
          cookies,
          workspace_id: workspaceId || "default",
        }),
      });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail =
          typeof body.detail === "string"
            ? body.detail
            : Array.isArray(body.detail)
              ? body.detail.map((d) => d.msg || d).join("; ")
              : `HTTP ${res.status}`;
        throw new Error(detail);
      }
      sendResponse({ ok: true, status: body });
    } catch (err) {
      sendResponse({ ok: false, error: err instanceof Error ? err.message : String(err) });
    }
  })();
  return true; // async
});
