# RivalRadar Connect (Chrome extension)

Fast path to vault LinkedIn / X / Instagram / TikTok / Threads sessions **without** the noVNC Connect browser.

## Install (unpacked)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. **Load unpacked** → select this folder (`extensions/rivalradar-connect`)
4. Pin the extension

## Use

1. On RivalRadar (Vercel or local), open **Connect** for a platform → **Extension** tab
2. Copy the 6-character pairing code (expires in 5 minutes)
3. Stay signed in to that platform in Chrome
4. Click the extension → paste code → pick platform → **Connect to RivalRadar**
5. The website detects `connected` and closes the dialog

## API URL

Default: `https://rivalradar-api-fl5j.onrender.com`

For local gateway use `http://localhost:8000`. Change it in the popup; it is saved in `chrome.storage.local`.

## Privacy

- Cookies never leave Chrome except as a one-shot POST to your RivalRadar gateway with a one-time pairing code.
- No passwords are read or sent.
- Pairing codes expire in 5 minutes and are single-use.

## Supported cookies

| Platform  | Required     |
|-----------|--------------|
| LinkedIn  | `li_at`      |
| X         | `auth_token` |
| Instagram | `sessionid`  |
| TikTok    | `sessionid`  |
| Threads   | `sessionid`  |
