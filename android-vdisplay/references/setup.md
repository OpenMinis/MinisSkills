# Connecting Minis to the Local Device via Wireless Debugging

This skill requires `adb` inside Minis's Alpine environment to connect to **the same Android phone** with `shell` privileges. On Android 11+, use built-in **Wireless Debugging**.

## 1. Install Required Packages
```sh
apk add android-tools curl python3
```

## 2. Enable Wireless Debugging (On the Phone)
1. Go to **Settings -> About phone** and tap **Build number** 7 times to enable Developer options.
2. Go to **Settings -> System -> Developer options** and turn on **Wireless debugging** (requires an active Wi-Fi connection).
3. Tap into **Wireless debugging** and note the **IP address & Port** shown on the main page (used for `adb connect`).

## 3. One-Time Pairing (Run Inside Minis Interactive Terminal)
1. On the Wireless debugging screen, tap **Pair device with pairing code** to display the `IP:pairing_port` and 6-digit pairing code.
2. In the Minis **interactive terminal**, run (do not paste the pairing code into chat):
   ```sh
   adb pair <IP>:<pairing_port>        # Enter the 6-digit pairing code when prompted
   adb connect <IP>:<connect_port>     # Use the IP & port from the main Wireless debugging page
   adb devices                         # Should list the device as `device`
   ```
3. On subsequent uses, only `adb connect` is needed (note that the port changes after a reboot or Wi-Fi network switch).

## 4. Device Selection Environment Variables
- Single device attached: no configuration needed.
- Multiple devices attached: `export SERIAL=<IP:port>`.
- Automatic reconnection on drop: `export ADB_CONNECT=<IP:port>`.

## 5. Notes
- When connecting to the phone from itself, use the Wi-Fi IP address shown in Wireless debugging (not necessarily `127.0.0.1`).
- Wireless debugging turns off after a phone reboot; re-enable it in Developer options and run `adb connect` again.
- If an authorization dialog appears on screen, check **Always allow from this computer**.
