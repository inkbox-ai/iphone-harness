# SETUP — From Zero to Working

This is the long-form, **start from absolutely nothing** guide. You have a Mac and an iPhone with a USB cable. By the end, `iphone-harness -c 'print(active_app())'` will print the foreground app on the phone.

If you already know what you're doing and just need the cheat-sheet, see `install.md`.

---

## What you're building

Five things have to line up before any of this works:

```
your script  ───►  iphone-harness CLI  ───►  iphone-harness daemon  ───►  Appium server  ───►  WebDriverAgent (on iPhone)
                                                                            (port 4723)         (signed by your Apple ID)
```

The setup is about getting **WebDriverAgent (WDA)** — a tiny helper app — built, signed, installed on your iPhone, and trusted by iOS. Everything else is plumbing on top of that.

The hard part is Apple's signing system, not the code.

---

## Part 1 — System tools (Mac side)

### 1.1 Install Xcode (the full thing, not just CLT)

Open the App Store, search **Xcode**, click Get. It's ~10 GB and takes a while. Command-line tools alone are **not enough** — Appium uses the full Xcode toolchain to build WebDriverAgent.

Once installed, open Xcode once and accept the license prompt + any "install additional components" dialog. Then point the system at it:

```bash
sudo xcode-select -s /Applications/Xcode.app/Contents/Developer
```

Verify:

```bash
xcodebuild -version
# expected: Xcode 16.x or 26.x, Build version ...
```

### 1.2 Install Homebrew (skip if you already have it)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 1.3 Install libimobiledevice

```bash
brew install libimobiledevice ideviceinstaller
```

This gives you `idevice_id`, `ideviceinfo`, and `ideviceinstaller` for talking to the phone over USB.

### 1.4 Install Node.js

If you don't have Node:

```bash
brew install node
```

(Or use nvm if you prefer.)

### 1.5 Install Appium and the XCUITest driver

```bash
npm i -g appium
appium driver install xcuitest
```

⚠️ **Important: pin the xcuitest driver to a stable version.** The 11.x line has a tunnel-registry bug on some setups (writes the port to root's keychain while the server reads from yours, causing `Tunnel registry port not found`). 10.43.1 is the last known-good before that regression:

```bash
appium driver install --source=npm appium-xcuitest-driver@10.43.1
# or, if it's already installed:
appium driver uninstall xcuitest
appium driver install --source=npm appium-xcuitest-driver@10.43.1
```

Verify:

```bash
appium --version           # 3.x
appium driver list         # xcuitest@10.43.1 should be installed
```

### 1.6 Install `uv` (the Python tool we use here)

```bash
brew install uv
```

---

## Part 2 — Plug in the phone

### 2.1 Cable

Use a real **data cable**. Apple's white cable is fine; cheap unbranded ones are often charge-only. Quick test: plug the iPhone in while unlocked. If a "Trust This Computer?" prompt pops up on the phone, it's a data cable. If it just charges silently, it's not.

### 2.2 Trust the Mac

When you plug in, the iPhone shows **"Trust This Computer?"** — tap **Trust** and enter your iPhone passcode (or set up the test phone with no passcode, which is what this repo assumes).

### 2.3 Confirm USB connection

```bash
idevice_id -l
# expected: 00008030-XXXXXXXXXXXXXXXX  (your UDID)
```

If empty:
- The phone is locked or the Trust prompt was dismissed — unlock and replug.
- The cable is charge-only — try a different one.
- `system_profiler SPUSBDataType -json` returning empty is a **false negative on Apple Silicon** — don't trust it; trust `idevice_id` and `ioreg`.

```bash
ideviceinfo | head -20
# should show ProductType, ProductVersion (iOS version), DeviceName, etc.
```

**Save these values** — you'll plug them into `.env` shortly:
- `UDID` from `idevice_id -l`
- `iOS version` from `ideviceinfo | grep ProductVersion` (e.g. `18.3.2`)
- `Device name` from `ideviceinfo | grep DeviceName` (e.g. `My iPhone`)

### 2.4 Enable Developer Mode on the iPhone

On the iPhone:

1. **Settings → Privacy & Security → Developer Mode**
2. Toggle it **On**.
3. The phone reboots. After reboot, confirm "Turn On" when prompted.

If "Developer Mode" isn't visible in Settings yet, it appears after Xcode tries to install something to the phone — easiest way to make it appear is to do a Test build from Xcode in step 4.4 below, then come back here.

---

## Part 3 — Apple ID, Team ID, and the signing certificate

This part trips everyone up the first time. You need an Apple ID, a "Personal Team" (free), a development certificate in your Mac's keychain, and a Team ID to plug into Appium.

### 3.1 Sign into Xcode with an Apple ID

A free Apple ID works for personal device automation. (Paid $99 only matters if you want certs that don't expire weekly — but **the WDA cert from a free account also lasts ~7 days at a time**, so realistically rebuild every week.)

1. Open Xcode.
2. **Xcode → Settings → Accounts** (`⌘,` → Accounts tab).
3. Click **+** in the bottom-left → **Apple ID** → sign in.
4. Your account appears in the left list. The right pane shows "Personal Team" only after step 3.2 below.

### 3.2 Trigger creation of your "Personal Team"

A fresh Apple ID has no team until Apple provisions one. Easiest way to make Apple do that:

1. Xcode → **File → New → Project** → **iOS → App** → Next.
2. Fill in:
   - **Product Name:** `Trigger` (anything)
   - **Team:** click dropdown → there might be nothing yet; pick whatever shows your Apple ID.
   - **Organization Identifier:** `com.<yourname>` (anything unique-ish)
3. Save anywhere — you don't have to run the project.
4. Open the project, click the blue project root in the left sidebar → TARGETS → your app target → **Signing & Capabilities** tab → **Team** dropdown → pick **"Your Name (Personal Team)"**.

If the Bundle Identifier shows red ("Failed Registering Bundle Identifier"), change it to something more unique like `com.<yourname>.trigger.20260502xyz`. Apple's free tier remembers every bundle ID you've ever tried, so don't waste them.

If you see *"Your team has no devices from which to generate a provisioning profile"* — at the top of the Xcode window there's a device selector. Click it, pick your real iPhone (under "iOS Device" / "Connected"). Selecting it as the build target registers it with Apple. The error should clear.

### 3.3 Create the development certificate

Xcode's Personal Team doesn't auto-create the signing cert — you have to ask for it.

1. Xcode → **Settings → Accounts** → click your Apple ID on the left.
2. In the right pane, click your team row.
3. Click **Manage Certificates…** (bottom-right of that pane).
4. A dialog opens. Bottom-left corner: click **+** → **Apple Development**.
5. After a few seconds, an entry named after your Mac (e.g. **"Alice's MacBook Pro"**) appears. Done — close the dialog.

### 3.4 Find your Team ID (the value Appium needs)

The Team ID is a 10-character alphanumeric string (e.g. `ABCDE12345`). There are several ways to grab it:

**Easiest** — from Keychain Access:
1. Open **Keychain Access** (Spotlight → "Keychain Access").
2. Left sidebar: **login**. Top: **My Certificates**.
3. Find **"Apple Development: <your-email> (XXXXXXXXXX)"**.
4. Right-click → **Get Info** → look at **"Organizational Unit"**. That's your Team ID.

**Alternative** — read it from the trigger project:
```bash
grep -A1 DEVELOPMENT_TEAM /path/to/Trigger.xcodeproj/project.pbxproj
```

Save this value. It goes in `IPH_XCODE_ORG_ID`.

### 3.5 Stop codesign popup spam (the keychain "Allow all" fix)

Without this, every WDA build triggers an avalanche of "codesign wants to use the cert" popups that block the build until you click them all.

1. Open **Keychain Access** → **login** → **My Certificates**.
2. Click the **▶ triangle** next to **"Apple Development: …"** to expand it. A private key appears underneath.
3. **Double-click the private key** (NOT the cert above it).
4. Click the **Access Control** tab.
5. Select **"Allow all applications to access this item"**.
6. Click **Save Changes** — enter your Mac password.

This is a one-time fix.

---

## Part 4 — Make sure Xcode can talk to *this* iPhone's iOS version

Xcode ships with device-support files only for iOS versions that existed when that Xcode was released. If your phone is on a newer iOS, Xcode can't deploy to it until you grab the matching support files.

### 4.1 Check what Xcode has

In Xcode: **Window → Devices and Simulators** (`⇧⌘2`). Click your iPhone in the left sidebar.

If it says **"Preparing device for development"** or **"iOS X.Y.Z is not supported by this version of Xcode"**, Xcode is auto-downloading what it needs. **Leave it for 5–15 minutes** — it can take a while. The progress bar isn't always visible.

You can verify the support files exist when it's done:

```bash
ls "$HOME/Library/Developer/Xcode/iOS DeviceSupport/"
# expected: a folder like "iPhone12,1 18.3.2 (22D82)"
```

### 4.2 If it's stuck — manual route

Don't use `xcodebuild -downloadAllPlatforms` — it tends to stall. Use the Xcode UI:

- **Xcode → Settings → Components** (or **Platforms**, depending on Xcode version) → find iOS X.Y → click download. ~3-5 GB.

### 4.3 Why this matters

Without it, you'll get cryptic `xcodebuild failed with code 65` errors when Appium tries to build WDA. The actionable error will be in the **Appium server log**, not the Python traceback — always look there.

### 4.4 (Optional but useful) — Install a trivial app from Xcode once

This is what makes "Developer Mode" appear on the iPhone if you couldn't find it earlier, and proves end-to-end that Xcode can deploy to your device:

1. Open the `Trigger` project from 3.2.
2. Top of Xcode window: scheme = your app, destination = your iPhone.
3. Hit the **Run ▶** button (or `⌘R`).
4. It builds, installs, and tries to launch. Likely fails to launch with the trust error — that's fine.
5. On the iPhone: **Settings → General → VPN & Device Management → Developer App → tap your profile → Trust → confirm.**
6. Hit Run again — the app launches. You're done with this dummy project; you can delete it.

---

## Part 5 — Pre-build and pre-sign WebDriverAgent

This is the step everyone skips and then spends 4 hours debugging. Appium *can* sign WDA automatically, but its automatic signing breaks on the second bundle ID (the `.xctrunner` test runner) and you'll go in circles trying to fix it from the outside.

The reliable path: open the WDA Xcode project yourself, sign it once manually, and `⌘U` it onto the phone. Then Appium just reuses the signed build.

### 5.1 Open the WDA project

```bash
open ~/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj
```

If `open` can't find it (hidden folders), in Xcode use **File → Open** then `⌘⇧G` and paste the path.

### 5.2 Pick a stable WDA bundle ID

You'll use this same string every time — pick once, never change. Apple's free tier has a "10 app IDs / 7 days" limit; cycling bundle IDs will lock you out.

Format: `com.<your-handle>.iphone-harness.wda` (or any reverse-domain string you "own"). E.g. `com.alice.iphone-harness.wda`. **Save this value** — it goes in `IPH_WDA_BUNDLE_ID`.

### 5.3 Sign the WebDriverAgentRunner target

In the open WDA project:

1. **Left sidebar:** click the blue **WebDriverAgent** project root at the very top.
2. **Center pane:** TARGETS list → click **WebDriverAgentRunner**.
3. **Top tabs:** **Signing & Capabilities**.
4. Check **"Automatically manage signing"**.
5. **Team:** dropdown → pick **"Your Name (Personal Team)"**.
6. **Bundle Identifier:** change to your stable one from 5.2.
7. Wait a few seconds — Xcode auto-generates the provisioning profile. Both the main runner and the auto-derived `<bundle>.xctrunner` should both show no errors.

If you get *"Failed Registering Bundle Identifier"* — pick a more unique string and try again. (You're hitting Apple's "this ID was used before" memory.)

If the Team dropdown shows red after changing the bundle, re-select the team — Xcode sometimes clears it on bundle changes.

### 5.4 Build and install WDA on the phone

1. Top of Xcode window — set:
   - **Scheme:** `WebDriverAgentRunner`
   - **Destination:** your iPhone (under "iOS Device" / "Connected")
2. **Product → Test** (`⌘U`).

It will:
- Build (1-3 min first time).
- Install WDA on the phone.
- Try to *launch* WDA — and **fail with the trust error**. That's expected and good.

The crucial part: **Xcode does not auto-uninstall on launch failure.** So WDA stays on the phone long enough for you to trust it. (Appium would have uninstalled it immediately, which is why you can't drive this from Appium first.)

### 5.5 Trust the developer profile on the iPhone

Now that WDA is installed on the phone, the developer profile finally appears in iOS settings:

1. On the iPhone: **Settings → General → VPN & Device Management**.
2. Under "Developer App" you'll see something like **"Apple Development: <your-email>"**.
3. Tap it → **Trust** → confirm.

Once trusted, this profile sticks around for ~7 days (free Apple ID). When it expires, you'll need to re-run step 5.4 (`⌘U`) to push a freshly-signed WDA, then re-trust.

### 5.6 Verify WDA launches

Optional but reassuring: in Xcode, hit `⌘U` again. This time WDA should *actually launch* (a blank/black screen on the iPhone for a moment), then Xcode's test will eventually time out — that's fine, the launch is what we needed to confirm.

---

## Part 6 — Wire up iphone-harness

Now that WDA can run, get the harness pointing at it.

### 6.1 Configure the harness

```bash
cd /path/to/iphone-control/iphone-harness
cp .env.example .env
```

Edit `.env` and fill in the four required values from the work above:

```bash
IPH_UDID=00008030-XXXXXXXXXXXXXXXX        # from `idevice_id -l`
IPH_PLATFORM_VERSION=18.3.2                # from `ideviceinfo | grep ProductVersion`
IPH_XCODE_ORG_ID=ABCDE12345                # your Team ID from 3.4
IPH_WDA_BUNDLE_ID=com.you.iphone-harness.wda           # the stable one from 5.2
```

Optional knobs (uncomment if needed):

```bash
# IPH_DEVICE_NAME=My iPhone
# IPH_APPIUM_URL=http://127.0.0.1:4723
# IPH_NEW_COMMAND_TIMEOUT=600
```

### 6.2 Install the harness package

From `iphone-harness/`:

```bash
uv pip install -e .
# or:  pip install -e .
```

This puts `iphone-harness` on your `$PATH`.

### 6.3 Start Appium

In one terminal, leave this running:

```bash
appium --base-path /
```

Expected log:

```
[Appium] Welcome to Appium v3.x.x
[Appium] XCUITestDriver has been successfully loaded
[Appium] Appium REST http interface listener started on http://0.0.0.0:4723
```

If it crashes with `Tunnel registry port not found` — your xcuitest driver is on 11.x. Go back to step 1.5 and downgrade to 10.43.1.

### 6.4 First call

In a second terminal:

```bash
iphone-harness --doctor
```

Expected output:
- ✅ Appium reachable at `http://127.0.0.1:4723`
- ✅ Device `<UDID>` paired
- ⚠️ Daemon not running yet (that's fine — first call below spawns it)

Now run a real command — this is the moment of truth:

```bash
iphone-harness -c '
print(active_app())
print(window_size())
'
```

What happens:
1. The harness CLI spawns the daemon (`/tmp/iph-default.sock`).
2. The daemon connects to Appium.
3. Appium pushes the pre-signed WDA to the phone (fast — already built and trusted).
4. WDA launches, exposes its automation API.
5. The daemon queries it and prints the result.

**First call** can take 30-60s while WDA initializes. Subsequent calls are instant.

Expected output (something like):

```
{'processArguments': {...}, 'name': '', 'pid': 34, 'bundleId': 'com.apple.springboard'}
{'width': 414, 'height': 896}
```

The exact `bundleId` reflects whatever app is currently foregrounded on the phone (`com.apple.springboard` is the iOS home screen). The `width`/`height` are logical points — what you'll pass to `tap_at_xy()` later. If you see those — congratulations, the whole stack works.

### 6.5 Try a real action

```bash
iphone-harness -c '
unlock()
appium("mobile: launchApp", bundleId="com.apple.MobileSMS")
wait_for_app("com.apple.MobileSMS")
print("foreground:", active_app()["bundleId"])
print("first 5 visible elements:")
for el in ui_tree(visible_only=True)[:5]:
    print(" ", el["type"], "|", el["label"] or el["name"])
'
```

This unlocks the device, opens Messages, and reads the first few elements of its accessibility tree. If that runs cleanly, you've got the whole loop working.

From here, see `SKILL.md` for the doctrine + the full helper API, and `agent-workspace/domain-skills/` for example per-app playbooks.

---

## Troubleshooting (when it doesn't)

### `Appium session create failed`
- Confirm Appium is running: `curl http://127.0.0.1:4723/status`
- Check `IPH_UDID` matches `idevice_id -l` exactly.
- Check `IPH_WDA_BUNDLE_ID` matches what you set in Xcode in step 5.3.

### `xcodebuild failed with code 65`
- Look at the **Appium server log** (not the Python traceback). The real error is in there — usually one of:
  - `Developer App Certificate is not trusted` → re-do step 5.5 (Trust on phone).
  - `No profiles for '...xctrunner' were found` → re-do step 5.3 in Xcode.
  - `Could not locate device support files` → re-do step 4.
  - `code signing is required` after a 7-day expiry → re-run `⌘U` in the WDA project.

### `Tunnel registry port not found`
- xcuitest 11.x bug. Downgrade to 10.43.1 (step 1.5).

### Codesign popup spam during builds
- Step 3.5 wasn't done. Open Keychain Access, set the dev key's Access Control to "Allow all applications".

### `Trust This Computer` loops
- Unplug, replug, unlock, tap Trust again, wait 10s. Sometimes the lockdown daemon on macOS gets confused — `sudo killall -9 lockdownd` and replug.

### WDA worked yesterday but `xcodebuild failed with code 65` today
- Free Apple ID certs expire every ~7 days. Open the WDA project in Xcode, hit `⌘U`, re-trust the profile on the phone (step 5.4 → 5.5). About a 2-minute fix.

### Daemon won't come up
- `iphone-harness --doctor` shows the last 10 log lines.
- `tail -f /tmp/iph-default.log` for live output.
- After a code change inside `src/iphone_harness/`: `iphone-harness --reload` then call again. (The agent-workspace files are hot-loaded and don't need a reload.)
- After a hard kill (`kill -9`): `rm /tmp/iph-default.sock /tmp/iph-default.pid`, then re-run.

### Long messages or special-char input hangs / truncates
- `type_text(...)` on iMessage with em-dashes / curly quotes / em-spaces / emoji is slow and can time out the IPC client. For text > ~80 characters or anything non-ASCII, use `set_value("name == 'fieldName'", text)` instead — atomic and Unicode-safe.

### Picker wheel won't move with `send_keys`
- `mobile: setPickerValue` is `NotImplementedError` in this XCUITest version, and `send_keys` is unreliable. Use `pick_wheel(predicate, target_substring, direction='next' or 'previous')` — it iterates one row at a time until match.

### `mobile: setPasteboard` fails with "Setting pasteboard content can only be performed on Simulator"
- That call really is simulator-only on real devices. Use `set_value` to write into the field directly instead of going through the clipboard.

### `idevice_id -l` is empty even though phone is plugged in
- `system_profiler SPUSBDataType -json` is unreliable on Apple Silicon — don't trust it.
- Try `ioreg -p IOUSB -w0 -l | grep -i iphone`.
- Unlock the phone, dismiss any dialogs, replug.

---

## What you end up with

- WDA installed and trusted on the iPhone (good for ~7 days on a free Apple ID; 1 year on the paid Developer Program).
- Appium running on `:4723`, reusing the signed WDA each session.
- iphone-harness daemon at `/tmp/iph-default.sock`, hot-loading agent helpers from `agent-workspace/agent_helpers.py`.
- `iphone-harness -c '...'` for arbitrary Python against the device, with helpers pre-imported.

Re-running on a new day usually means: plug in iPhone, `appium --base-path /` in one terminal, `iphone-harness -c '...'` in another. Everything else stays put.

When the WDA cert expires (~weekly with free Apple ID):
1. Open the WDA project (step 5.1).
2. `⌘U` to rebuild + reinstall.
3. On the phone: Settings → General → VPN & Device Management → tap your profile → Trust.

About a 2-minute fix.

## Where to next

- **`SKILL.md`** — the doctrine (tree-first, screenshots-second, escape-hatch-by-default) and the full helper API.
- **`README.md`** — public-facing summary and contributing guide.
- **`interaction-skills/*.md`** — generic iOS UI mechanics: dialogs, picker wheels, OCR fallback, the home-bar gesture zone, scroll-into-view, animation timing.
- **`agent-workspace/domain-skills/<bundleId>/*.md`** — per-app playbooks. To enable runtime discovery: set `IPH_DOMAIN_SKILLS=1` and call `domain_skills(bundle_id)` after launching an app.
