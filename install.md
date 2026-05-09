# Install

## Prereqs

- **macOS.** The agent runs on a Mac with the iPhone tethered via USB. (Linux + remote phones is theoretically possible via Appium-over-network, but untested.)
- **Python 3.11+**.
- **Node.js + Appium 3** globally:
  ```bash
  npm i -g appium
  appium driver install xcuitest
  ```
- **Xcode + command-line tools.** Needed by WebDriverAgent (the on-device agent Appium installs the first time you connect).
- **libimobiledevice** for `idevice_id` (used by `--doctor`):
  ```bash
  brew install libimobiledevice
  ```
- **An Apple Developer account.** Free is fine — you don't need a paid program. WebDriverAgent gets signed under your Team ID and installed on the device with a 7-day cert (Apple's free-tier rule). The device just needs to be associated with your Apple ID.

## 1. Provision the device

1. Plug the iPhone into the Mac.
2. Unlock and tap **Trust This Computer** when prompted.
3. Find the UDID — copy this for your `.env`:
   ```bash
   idevice_id -l
   # or
   xcrun xctrace list devices
   ```
4. **First-run only:** the first time WebDriverAgent runs on the device, iOS will refuse to launch it (untrusted developer). Go to **Settings → General → VPN & Device Management → [Your Apple Team] → Trust**.

## 2. Find your Apple Developer Team ID

Two easy ways:

- **From developer.apple.com:** sign in → **Membership** → **Team ID** is a 10-character alphanumeric like `ABCDE12345`.
- **From Xcode:** open any project → Signing & Capabilities → the Team dropdown shows the Team ID next to your name. Or in Terminal:
  ```bash
  security find-identity -v -p codesigning | grep "Apple Development"
  ```

## 3. Pick a WDA bundle id

Any reverse-domain string you "own" — it just has to be unique to you so it doesn't collide with another Appium user's WDA on the same device. Convention:

```
com.<your-handle>.iphone-harness.wda
```

E.g. `com.alice.iphone-harness.wda`. Doesn't need to be a real registered domain.

## 4. Configure

```bash
cp .env.example .env
$EDITOR .env
```

Fill in three values:

```
IPH_UDID=00008030-XXXX...               # from step 1
IPH_XCODE_ORG_ID=YOURTEAMID              # from step 2
IPH_WDA_BUNDLE_ID=com.you.iphone-harness.wda   # from step 3
```

## 5. Install the package

From `iphone-harness/`:

```bash
pip install -e .
# or with uv:
uv pip install -e .
```

This puts `iphone-harness` on `$PATH`.

## 6. Start Appium

In one terminal, leave running:

```bash
appium --base-path /
```

It listens on `http://127.0.0.1:4723` by default.

## 7. First call

In another terminal:

```bash
iphone-harness --doctor
# expect: Appium OK, Device OK, Daemon not running yet, no log

iphone-harness -c '
print(active_app())
print(window_size())
'
```

The daemon will spawn the first time and create an Appium session. First-time WDA installation can take 30–60 seconds; subsequent calls are near-instant.

## Troubleshooting

- **"Appium session create failed"**: confirm Appium is running and `IPH_UDID` matches a paired device (`idevice_id -l`).
- **"WebDriverAgent failed to start"**: trust the developer profile (Settings → General → VPN & Device Management → tap your Team → Trust).
- **"Trust This Computer" loops**: unplug, replug, unlock the phone, tap Trust again, wait ~10 seconds.
- **Code-signing failure on first run**: open Xcode, go to Settings → Accounts → add your Apple ID, then close Xcode and retry. Xcode caches your free-tier signing identity globally.
- **Daemon doesn't come up**: `iphone-harness --doctor` shows the last 10 log lines. `tail -f /tmp/iph-default.log` for live output.
- **Stale daemon after editing helpers**: `iphone-harness --reload` then run again.
- **WDA bundle id rejected**: pick a different one — a previous Appium install on this Mac may already own that bundle id under a different Team. The bundle id is global across Apple accounts.
- **Free-tier 7-day cert expired**: WDA stops working after 7 days on free accounts. Just `iphone-harness --reload` — the next call re-installs and re-trusts WDA. (Paid Developer Program accounts get 1-year certs.)
