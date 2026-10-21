# FishPilot — Telegram mini app

Control panel for [FishPilot](https://github.com/SanTW3/Mediavert/tree/main/gpo-fishing-macro) (a fishing
assistant for Grand Piece Online) right inside Telegram: live stats, start/stop, screen on/off, screenshot,
catch list, alarm reset. Languages: English, Русский, Español, Português (BR).

Site: https://santw3.github.io/gpo-macro/ (GitHub Pages, branch `main`, root).

> Not affiliated with Roblox or Grand Piece Online. Fish icons and names belong to their respective owners.

## How it works

There is no server of its own. The FishPilot app on the PC and this page talk through public MQTT brokers
(over WebSocket, `vendor/mqtt.min.js`) with [ntfy](https://ntfy.sh) as a fallback.

- Topic names are a hash of a secret, so they can't be guessed.
- Status messages and commands are signed with the secret (HMAC-SHA256) and carry a time and a nonce:
  without the link nobody can control the macro, and an intercepted command can't be replayed.
- The secret travels in the link fragment (`#…`), which is never sent to GitHub. The bot sends the link only
  to your own chat. If the link leaks, press **New secret link** in FishPilot.

## Enabling GitHub Pages (once)

Settings → Pages → Build and deployment → Source: **Deploy from a branch**, Branch: **main**, folder
**/ (root)** → Save.

## License

[MIT](LICENSE). Includes [MQTT.js](https://github.com/mqttjs/MQTT.js) (MIT).
