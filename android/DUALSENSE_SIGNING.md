# Fork APK signing: safe updates across successive releases

The DualShock, DualSense and original Switch Pro skins are selectable inside each Android APK. This fork's v0.1.4 release follows the same signing policy for every future v0.1.x build. The two distribution names and package IDs stay unchanged:

| Artifact | Android application ID |
| --- | --- |
| `PeanutsNative-DualSense-same-package.apk` | `dev.nxnative.android.peanuts` |
| `PeanutsNative-DualSense-side-by-side.apk` | `dev.nxnative.android.peanutsds` |

## One-time setup (required before the first APK build)

**Recommended Windows setup:** open PowerShell at the repository root, install JDK 21 and the GitHub CLI, authenticate with `gh auth login`, then run `powershell -ExecutionPolicy Bypass -File android/setup-fork-signing.ps1`. The script creates a **permanent private key on your own PC** (or reuses the existing one), asks GitHub CLI to store the three required encrypted repository secrets and never commits the key to the public fork. Safely back up the `.p12` file and save its printed password in your password manager before continuing. If you already have the private keystore used for a previous fork APK, reuse that exact file and alias to preserve update compatibility.

**Manual alternative:**

**Keep a permanent PKCS#12 keystore and password in private offline backups.** Never commit either to Git or attach it to a public issue/PR/artifact. Using a new key on every build causes `INSTALL_FAILED_UPDATE_INCOMPATIBLE` when updating the installed app. Losing the key prevents signing future compatible updates.

In repository **Settings → Secrets and variables → Actions → New repository secret**, create all three **repository secrets**:

1. `PEANUTS_SIGN_STORE_B64`: the entire base64 representation of the private `.p12` keystore.
2. `PEANUTS_SIGN_ALIAS`: the alias of the private key entry in the keystore.
3. `PEANUTS_SIGN_PASS`: its PKCS#12 store/key password (the build expects both passwords to match).

For example, generate a personal keystore on a trusted machine (never inside the repository):

```bash
keytool -genkeypair -noprompt -storetype PKCS12 -keystore peanuts-native-release.p12 \
  -alias peanuts-native -keyalg RSA -keysize 3072 -sigalg SHA256withRSA \
  -validity 10000 -dname "CN=Peanuts Native Personal Signing,O=Private Build,C=AL"
```

Choose and securely save a strong password when prompted. To convert the binary file to a single base64 string for the GitHub secret:

```bash
base64 -w0 peanuts-native-release.p12
```

On Windows PowerShell:

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes((Resolve-Path ".\\peanuts-native-release.p12")))
```

## Build

Run the **Peanuts Native Fork Android APK (upgrade-safe)** workflow manually from branch `feature/android-dualsense-v0.1.4`, or push a commit to that branch after secrets have been configured. All three secrets are now required: the workflow will **fail instead of silently generating one-time signing keys**.

The workflow builds and uploads **both** APKs, verifies the expected package ID of each, uses the **same permanent signer** for both, verifies the signatures with Android `apksigner` and checks an incrementing version code (`200000 + GITHUB_RUN_NUMBER`).

You can inspect each build's public signing SHA-256 certificate fingerprint in the Actions logs. The fingerprint is safe to share; **the private keystore and password are not**.

## Installation compatibility

**Fork-to-fork upgrades:** install the first build signed using this keystore. Every subsequent build must use that same private key and application ID, with a higher version code (this workflow uses the GitHub Actions run number). An APK built from the original developer's certificate cannot be replaced by our differently signed same-package APK, and vice versa. The side-by-side fork package lets the official app remain untouched. **The successful older fork test build was signed before this permanent-secret policy was introduced; unless its exact original private key is available, a new certificate cannot update that one in place.** Backup before uninstalling either.

An APK can update an existing installation in-place **only if** its application ID is unchanged, the signing certificate is compatible, and Android accepts its version code. The two APKs above install as *separate apps* and keep separate app data.

**Important:** a newly generated persistent key cannot upgrade an already installed build that was signed with a different temporary key, even if both APKs have exactly the same package ID. `adb install -r`, Shizuku and InstallerX cannot bypass this Android security rule. Back up the existing app's game/settings data *before* any uninstall. After installing the first permanently signed version, preserve the same keystore for all subsequent releases.

To compare two APK signing identities on a machine with Android SDK Build Tools:

```bash
apksigner verify --print-certs PeanutsNative-DualSense-same-package.apk
```

Compare its `Signer #1 certificate SHA-256 digest` with that of the installed APK, if you have a copy. Both newly published variants should have the same digest.
