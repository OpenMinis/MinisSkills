# sdk27.md — Building for iOS 27 (and for devices with side-button intrusions)

iOS 27 raises the bar in two places: the SDK's `.tbd` stubs no longer describe an `arm64` device slice,
and UIKit **kills** apps that have not adopted the scene lifecycle. Both failures look like "the app
crashes on launch" and neither is obvious from the compiler output. This document is the checklist to
get a 27.x-SDK build running, plus the layout rules for hardware that reserves part of the screen edge
(the iPhone "Duo"-class devices do).

Verified on: iPhone19,4 / iOS 27.1 · SDK `iPhoneOS27.1.sdk` · clang+lld 19.1.4 · pymobiledevice3 11.x.

---

## 1. Install the SDK (the tbd patch is automatic)

```sh
python3 scripts/install_sdk.py 27.1      # → ~/.ios-sdk/iPhoneOS27.1.sdk (~380 MB, headers + .tbd only)
```
Point the project at it (`sdk:` and the `-F…/SubFrameworks` cflag in `project.yaml`). Old SDKs stay in
`~/.ios-sdk/`, so switching back is one `sed`.

**What breaks without the patch.** From iOS 27.0 on, the stubs declare:

```yaml
targets: [ arm64e-ios, arm64e.x1-ios ]      # 27.x — no arm64 slice, plus an arch LLD < 21 does not know
targets: [ armv7-ios, armv7s-ios, arm64-ios, arm64e-ios ]   # ≤ 26.x — fine
```

Compilation still succeeds (headers are compatible), but **every link fails**:

```
ld64.lld: error: could not load TAPI file at …/UIKit.tbd: malformed file
…/UIKit.tbd:3:32: error: unknown architecture
```

`install_sdk.py` rewrites each `targets:` list to `[ arm64-ios, arm64e-ios ]` as part of installation
(657 files / 1137 lists in 27.1, including the nested `- targets:` entries under `reexported-libraries:`).
A stub only declares symbols, so claiming `arm64-ios` is enough to link an arm64 app; the resulting
arm64 binary runs unchanged on arm64e hardware. If you installed 27.x before this patch existed, rerun
the installer or patch by hand — the rewrite is idempotent.

## 2. Adopt the scene lifecycle — or the app is killed at launch

An app that creates its own `UIWindow` in `application:didFinishLaunchingWithOptions:` and never
declares a scene manifest is terminated by UIKit as soon as the first scene is created. The crash is an
`EXC_BREAKPOINT` with this frame at the top — that string is the whole diagnosis, you do not need
symbols:

```
___UIApplicationEvaluateRuntimeIssueForNoSceneLifecycleAdoption_block_invoke
-[UIApplication workspace:didCreateScene:withTransitionContext:completion:]
UIApplicationMain → main
```

Linked against the 26.x SDK the same code only logs a warning, which is why an SDK bump can turn a
working app into a launcher that flashes and disappears.

**Minimum viable adoption (ObjC, no storyboard):**

```yaml
# project.yaml → info:
info:
  UIApplicationSceneManifest:
    UIApplicationSupportsMultipleScenes: false
    UISceneConfigurations:
      UIWindowSceneSessionRoleApplication:
        - UISceneConfigurationName: Default Configuration
          UISceneDelegateClassName: SceneD
```

```objc
@interface SceneD : UIResponder <UIWindowSceneDelegate>
@property (nonatomic, strong) UIWindow *window;
@end
@implementation SceneD
- (void)scene:(UIScene *)scene willConnectToSession:(UISceneSession *)s options:(UISceneConnectionOptions *)o {
  if (![scene isKindOfClass:UIWindowScene.class]) return;
  UIWindowScene *ws = (UIWindowScene *)scene;
  self.window = [[UIWindow alloc] initWithWindowScene:ws];
  self.window.frame = ws.coordinateSpace.bounds;
  self.window.rootViewController = /* your root VC */;
  [self.window makeKeyAndVisible];
}
@end

// AppDelegate: build nothing here, index the scene config instead
- (UISceneConfiguration *)application:(UIApplication *)app
    configurationForConnectingSceneSession:(UISceneSession *)session
                                   options:(UISceneConnectionOptions *)options {
  UISceneConfiguration *c = [[UISceneConfiguration alloc] initWithName:@"Default Configuration" sessionRole:session.role];
  c.delegateClass = [SceneD class];   // NOT NSClassFromString(@"SceneD") — see below
  return c;
}
```

### The trap: `-dead_strip` deletes a delegate referenced only by name

If the class name lives **only** in `UISceneDelegateClassName` (a string in Info.plist) and in
`NSClassFromString`, nothing in the object file references the class, so the linker drops it. The scene
then connects with a **nil delegate**: the process launches, has no window, and the system suspends it.
Symptoms:

- the icon tap looks like a crash ("flashes and disappears")
- **no crash report is produced at all**
- the system log shows the app going `running-active-Visible → NotVisible` and then staying invisible
- any local server the app starts in the scene delegate never comes up

Fix: reference the class at compile time (`c.delegateClass = [SceneD class]`). Keeping the Info.plist
entry too is harmless and documents intent.

## 3. Diagnose launch failures without a Mac

All of these run from the phone over the same loopback RSD channel the rest of the skill uses
(`IOSDEV_PAIRING_FILE` must be set).

```sh
# crash reports (works even when the app died before writing anything visible)
python3 scripts/crashlogs.py --app MyApp            # list newest
python3 scripts/crashlogs.py --app MyApp --print    # full text of the newest one
python3 scripts/crashlogs.py --app MyApp --pull ./crashes
```

If a fresh crash is missing, flush first — records can sit in the device's staging area:

```python
async with CrashReportsManager(rsd) as m:
    await m.flush(); await asyncio.sleep(2); print(await m.ls('/'))
```

Launch an app on demand and watch the launch state, without touching the device:

```python
async with DvtProvider(rsd) as prov, ProcessControl(prov) as pc:
    pid = await pc.launch(BUNDLE_ID)         # DTXNsError "Process failed to launch" = launchd refused it

async with OsTraceService(rsd) as log:       # os_trace relay over RSD
    async for e in log.syslog():
        ...                                   # "Received state update for <pid> (app<…>, running-active-Visible)"
```

**No crash report + `Process failed to launch` + state flicking `Visible → NotVisible`** is the
signature of the nil-delegate trap in section 2, not of a code bug.

## 4. Layout: hardware that reserves a screen edge

Some 27-era devices reserve part of the display for the side button / grip area. The window does **not**
shrink; the system reports the reserved strip through the safe area instead. Measured on iPhone19,4:

```json
{"size":"951x669","safeTop":0,"safeLeft":0,"safeRight":84,"safeBottom":34,"cornerRadius":59}
```

`safeRight = 84` means the rightmost 84 pt are unusable. Anchoring a floating control to
`view.trailingAnchor` puts it straight under the hardware and it shows up "cut off" or invisible.
Rules:

- Anchor overlay chrome to `view.safeAreaLayoutGuide.leadingAnchor/trailingAnchor/topAnchor`, **never**
  to `view.leadingAnchor/trailingAnchor`. This applies to the whole bottom bar as well — in landscape
  the reserved strip moves to one of the sides.
- Add corner-radius clearance on top of the safe area. A 44 pt circle sitting in a 59 pt corner arc
  still gets clipped even inside the safe area:

```objc
CGFloat cr = 0;
@try { cr = [[[UIScreen mainScreen] valueForKey:@"_displayCornerRadius"] doubleValue]; } @catch (NSException *e) {}
CGFloat padX   = MAX(10.0, cr * 0.25);
CGFloat padTop = MAX(8.0,  cr * 0.20);
```

- Recompute in `viewDidLayoutSubviews` and only touch the constants when the value actually changed
  (avoiding a layout loop), because the safe area changes with rotation, folding and split view.

Handy verification endpoints if the app embeds a small debug HTTP server:

```
GET /layout   → window size, safe-area insets, corner radius, 44×44 control frames
GET /views    → hierarchical view dump with frames (find "44x44" to check your overlay)
```
`/layout` is the fastest way to answer "why is my button under the bezel" — compare the control's frame
against `size - safeRight`.

## 5. Version notes

| Item | Value at verification time |
|---|---|
| Device / OS | iPhone19,4 · iOS 27.1 |
| SDK | `iPhoneOS27.1.sdk` (mirror `xybp888/iOS-SDKs`) |
| Linker | ld64.lld 19.1.4 (needs the tbd patch above) |
| Scene lifecycle | required from iOS 27 SDK; warning only on 26.x |
| Deployment target | `min_ios: 14.0` still launches fine on 27.1 |

A 27.x build is ~20–30 % slower to link than a 26.x build on iSH, and the binary grows by a few KB;
neither is a problem in practice.
