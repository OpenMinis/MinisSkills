---
name: android-dev
description: 在 Minis 的 ARM64 Alpine PRoot 中从零诊断、安装并验证 Android 构建环境，以及创建、构建、签名验证、安装和启动原生 Android App；覆盖 Java/Kotlin/Gradle/SDK/AAPT2、APK、ADB/无线调试/Shizuku，以及条件式 JNI/NDK。用户提到 Android 项目、APK/AAB、Gradle、AGP、SDK、AAPT2、Kotlin、Compose、JNI/NDK、ADB、开发者端口、无线调试、安装或启动应用时使用。
version: 2.0.0
---

# Android 开发（Minis ARM64 Alpine）

## 目标与不变量

按“探测 → 选路线 → 准备 → 构建 → 验证 → 安装/运行”执行。遵守：

- 不假设 Java、SDK、Gradle、ADB、NDK 或固定路径存在；先取证。
- 不直接运行 Google Linux SDK/NDK 中的 x86_64 native host 工具。
- 不下载或替换未固定版本、来源和校验值的 AAPT2；不重新分发无明确许可证的第三方二进制。
- 不把警告当成功，也不因非致命警告误报失败；以命令退出状态和验收证据为准。
- 不输出 keystore 密码、API key、代理凭据等秘密。
- 不自动卸载现有 App 来解决签名冲突，因为这可能删除用户数据。
- 未取得 `BUILD SUCCESSFUL`、APK 验证、安装成功与启动证据时，不声称对应阶段完成。

## 能力矩阵

| 能力 | 状态 | 默认处理 |
|---|---|---|
| Java/View Debug APK | 已实测 | 本地 ARM64 构建 |
| APK 签名与完整性验证 | 已实测 | `scripts/verify-apk.sh` |
| Kotlin App | 条件支持，未完整实测 | 先做最小 Kotlin smoke build |
| Compose/KSP/KAPT | 条件支持，未实测 | 先检查插件、仓库、SDK/AGP/JDK 矩阵 |
| Release APK/AAB | 条件支持 | 用户提供签名策略；先验证工具链 |
| ADB | 条件支持 | Alpine `android-tools`；必须检查设备状态 |
| Shizuku 安装/启动 | 条件支持 | 需要 Minis 集成权限与运行中的 Shizuku |
| JNI `arm64-v8a` | 实验性 | 先检查 NDK、Alpine Clang、sysroot；不得假设存在 |
| 多 ABI/AIDL/官方 native host 工具 | 未验证 | 先做能力探测；必要时改用远程 x86_64 构建机 |

## Phase 0：Doctor

先运行 Skill 自带诊断脚本：

```sh
/var/minis/skills/android-dev/scripts/doctor.sh
```

状态约定：

- `STATUS=READY` / exit 0：Java APK 环境可构建。
- `STATUS=NEED_BOOTSTRAP` / exit 10：运行 Bootstrap。
- `STATUS=UNSUPPORTED_ARCH` / exit 20：不要执行 ARM64 路线，改用匹配宿主的工具链。
- `ADB=optional_missing`、`NDK_R27D=optional_missing` 不阻断普通 APK 构建。

同时按任务检查磁盘、内存和写权限：

```sh
df -h /opt /var/minis /tmp
grep -E 'MemTotal|MemAvailable' /proc/meminfo
for D in /opt /var/minis/workspace /tmp; do test -w "$D" && echo "$D writable" || echo "$D NOT_WRITABLE"; done
```

磁盘不足时只清理本任务临时文件和可重建缓存，不擅自删除用户项目。Gradle 无堆栈直接显示 `Killed` 时，优先怀疑系统 OOM：降低 Xmx 与 workers，而不是反复重试。

## Phase 1：从零准备环境

### 标准 Bootstrap

对空白/缺损环境直接运行：

```sh
/var/minis/skills/android-dev/scripts/bootstrap-android.sh
```

脚本会幂等地：

1. 确认 `aarch64` Alpine 与至少 1.5 GiB `/opt` 可用空间；
2. 安装 OpenJDK 17、Gradle、ZIP/ELF 工具，并尽力安装 Alpine ARM64 ADB；
3. 从固定 Google URL 下载 Android Platform 34 与 Build Tools 35.0.0；
4. 同时校验固定 SHA-1/SHA-256，使用 `.part` 与 staging 目录，避免半成品覆盖；
5. 从固定 Git commit 下载 ARM64 AAPT2 并校验 SHA-256，先验证后原子替换并保留旧版；
6. 写入 `/etc/profile.d/android-sdk.sh`；
7. 验证 AAPT2 能解析 Android 34、D8/apksigner 存在，最后输出 `STATUS=READY`。

再次运行 Doctor，只有 READY 才继续：

```sh
/var/minis/skills/android-dev/scripts/doctor.sh
```

### 为什么固定 Android 34

当前固定 ARM64 AAPT2：

- AArch64 静态 ELF；
- AAPT2 2.19；
- 已验证 Android Platform 34；
- 不能解析 Android 35 新资源表，会报 `illegal map type 'string' (22)`。

所以默认 `compileSdk 34` / `targetSdk 34`。不要因 Build Tools 目录名是 35.0.0 就误用 Platform 35。AAPT2 来源与哈希见 `references/aapt2-provenance.md`。

只有新版 ARM64 AAPT2 同时通过以下测试后，才升级平台：

```sh
file "$AAPT2"
readelf -h "$AAPT2" | grep AArch64
"$AAPT2" version
"$AAPT2" dump resources /opt/android-sdk/platforms/android-35/android.jar >/dev/null
```

官方 Linux AAPT2/zipalign/aidl 等 native 程序通常为 x86_64；Termux AAPT2 依赖 Android Bionic；QEMU+gcompat 已出现 `Bus error`。它们都不是默认回退路线。Java wrapper（如 D8、apksigner）可在 Java 17 下单独验证后使用。

## Phase 2：项目配置与构建路线

项目 `local.properties`：

```properties
sdk.dir=/opt/android-sdk
```

项目 `gradle.properties`：

```properties
android.aapt2FromMavenOverride=/opt/android-sdk/build-tools/35.0.0/aapt2
org.gradle.jvmargs=-Xmx1536m -Dfile.encoding=UTF-8
org.gradle.workers.max=2
org.gradle.parallel=false
org.gradle.daemon=false
```

内存充足时可用 `-Xmx2048m`；内存紧张时降到 `768m–1024m`。不要在命令中输出代理变量值。若 `sdkmanager` 报 `MalformedURLException: no protocol`，仅对该命令临时移除空/畸形的 `HTTP_PROXY`、`HTTPS_PROXY` 及小写变体。

当前稳定最小模块：

```gradle
plugins { id 'com.android.application' }

android {
    namespace 'com.example.app'
    compileSdk 34
    buildToolsVersion '35.0.0'
    defaultConfig {
        applicationId 'com.example.app'
        minSdk 23
        targetSdk 34
        versionCode 1
        versionName '1.0'
    }
}
```

已实测组合：Java 17 + Gradle 8.11.1 + AGP 8.9.0 + Platform 34 + Build Tools 35.0.0 + 固定 ARM64 AAPT2。

### Gradle Runner 选择

已有项目优先 Wrapper，系统 Gradle 只用于无 Wrapper 的新项目或明确兼容的回退：

```sh
if test -f ./gradlew; then
  chmod +x ./gradlew
  GRADLE=./gradlew
elif command -v gradle >/dev/null 2>&1; then
  GRADLE=gradle
else
  echo 'No Gradle runner' >&2; exit 2
fi
```

正常构建不要默认 `clean`：

```sh
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk
export ANDROID_HOME=/opt/android-sdk ANDROID_SDK_ROOT=/opt/android-sdk
export PATH="$JAVA_HOME/bin:$PATH"
"$GRADLE" --no-daemon assembleDebug --stacktrace
```

仅在中间产物明确损坏时运行 `clean assembleDebug`；需要重跑任务优先 `--rerun-tasks`。资源链接失败时加 `--info` 取得完整 AAPT2 命令。

`Platform-Tools not installed/license not accepted` 与 Bionic `couldn't find any tzdata` 在任务继续且最终 `BUILD SUCCESSFUL` 时可记为非致命警告。若构建退出非零，必须读取完整错误，不因看到部分 task 成功而报告完成。

## Phase 3：APK 验收

构建后执行：

```sh
/var/minis/skills/android-dev/scripts/verify-apk.sh \
  app/build/outputs/apk/debug/app-debug.apk com.example.app
```

脚本要求：

- APK 非空；
- 包名符合预期；
- 存在 launchable Activity；
- ZIP 完整；
- `apksigner verify` 成功；
- 输出 SHA-256、字节数和 `STATUS=VERIFIED`。

Release 构建必须另行确认签名证书与策略。不要把密码写进项目、脚本、命令输出或聊天。

## Phase 4：安装与启动

### Shizuku（本机优先）

先查看准确语法，再执行：

```sh
android-shizuku-cli package install --help
android-shizuku-cli package install /absolute/path/app-debug.apk
android-shizuku-cli activity start --component com.example.app/.MainActivity
```

返回 `PERMISSION_DENIED` 时不要重试，引导用户打开 [设置 → 权限](minis://settings/permissions)，并确认 Shizuku 服务运行和授权完成。安装后用 `pm path`、启动命令返回值或日志验证。

### ADB

只使用 Alpine `/usr/bin/adb`。先检查设备：

```sh
adb start-server
adb devices -l
```

多个设备时必须指定 `-s SERIAL`。`offline`、`unauthorized` 时停止并让用户处理设备授权。Android 11+ 无线调试配对码必须在交互终端输入，不在聊天索取或回显：

```sh
adb pair HOST:PAIR_PORT
adb connect HOST:CONNECT_PORT
```

安装、启动与验证：

```sh
adb -s "$SERIAL" install -r "$APK"
adb -s "$SERIAL" shell pm path com.example.app
adb -s "$SERIAL" shell am force-stop com.example.app
adb -s "$SERIAL" shell am start -W -n com.example.app/.MainActivity
adb -s "$SERIAL" logcat -d -s AndroidRuntime:E '*:S'
```

签名冲突 `INSTALL_FAILED_UPDATE_INCOMPATIBLE` 时说明原因并询问用户；不要自动卸载。版本降级需用户同意后决定是否用 `-d`。空间不足、用户限制、ABI 不匹配按错误码处理，不盲目重试。

## JNI / NDK：实验路线

不要假设 NDK 或 Clang 已配置。先检查：

```sh
NDK=/opt/android-sdk/ndk/27.3.13750724
CLANG=$(command -v clang-18 || command -v clang || true)
test -d "$NDK" || { echo 'NDK missing'; exit 2; }
test -n "$CLANG" || { echo 'Alpine clang missing'; exit 2; }
SYS="$NDK/toolchains/llvm/prebuilt/linux-x86_64/sysroot"
test -d "$SYS" || { echo 'NDK sysroot missing'; exit 2; }
```

官方 NDK host Clang/CMake 是 x86_64，不直接执行。可实验性使用 Alpine Clang + NDK sysroot 预编译 `arm64-v8a` `.so`，但必须验证：

```sh
readelf -h libnative-lib.so | grep AArch64
readelf -d libnative-lib.so
unzip -l app-debug.apk | grep 'lib/arm64-v8a/'
```

还要在真实设备启动并检查 `UnsatisfiedLinkError`/logcat，才声称 JNI 可用。缺少 builtins、unwind、SSP 或出现 musl/Bionic 链接疑问时停止，不随意复制系统库；优先改用可信 x86_64 Linux/macOS 远程构建机。

## 错误决策表

| 现象 | 正确动作 | 重试策略 |
|---|---|---|
| Java `Failed to mark memory page as executable` | 显式切 OpenJDK 17 | 一次；仍失败则停止 |
| 文件存在但 `No such file or directory` | `file`、`readelf -l` 检查架构/解释器 | 不盲重试 |
| Android 35 `illegal map type` | 使用 Platform/compileSdk 34 | 一次 |
| 下载 ZIP 校验失败 | 删除 `.part`，重新下载固定 URL | 最多一次，仍失败则停止 |
| `sdkmanager` proxy URL 错误 | 只对该命令移除畸形代理变量 | 一次 |
| Gradle 直接 `Killed` | 检查内存/存储，降低 Xmx/workers | 调整后一次 |
| AAPT2 resource link 失败 | `--info` 取得命令，验证平台兼容性 | 按根因处理 |
| Shizuku `PERMISSION_DENIED` | 请求用户开放权限 | 不重试 |
| ADB `unauthorized/offline` | 等用户授权/重连 | 不循环 |
| 安装签名冲突 | 询问是否保留数据/卸载 | 不自动卸载 |
| 文件系统只读/空间不足 | 换可写目录或请用户清理 | 不删用户文件 |

## 交付契约

最终报告分阶段列出证据：

1. 环境：Doctor `STATUS=READY`；
2. 构建：`BUILD SUCCESSFUL` 与 APK 路径；
3. 验收：`STATUS=VERIFIED`、包名、版本、SHA-256；
4. 安装：明确成功或因权限/设备状态未执行；
5. 运行：Activity 启动返回值或日志证据；
6. 条件支持/未验证能力必须明确标注，不扩大结论。
