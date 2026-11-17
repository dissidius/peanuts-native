# DualSense APK signing and safe updates

The DualShock, DualSense and original Switch Pro skins are selectable inside each Android APK. The two distribution names and package IDs stay unchanged:

| Artifact | Android application ID |
| --- | --- |
| `PeanutsNative-DualSense-same-package.apk` | `dev.nxnative.android.peanuts` |
| `PeanutsNative-DualSense-side-by-side.apk` | `dev.nxnative.android.peanutsds` |

## One-time setup

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

Run the **Peanuts Native DualSense Android APK** workflow manually from branch `feature/android-dualsense-only-upstream` (or let the PR workflow run after secrets are configured). All three secrets are now required: the workflow will **fail instead of silently generating one-time signing keys**.

The workflow builds and uploads **both** APKs, verifies the expected package ID of each, uses the **same permanent signer** for both, verifies the signatures with Android `apksigner` and checks an incrementing version code (`10000 + GITHUB_RUN_NUMBER`).

You can inspect each build's public signing SHA-256 certificate fingerprint in the Actions logs. The fingerprint is safe to share; **the private keystore and password are not**.

## Installation compatibility

An APK can update an existing installation in-place **only if** its application ID is unchanged, the signing certificate is compatible, and Android accepts its version code. The two APKs above install as *separate apps* and keep separate app data.

**Important:** a newly generated persistent key cannot upgrade an already installed build that was signed with a different temporary key, even if both APKs have exactly the same package ID. `adb install -r`, Shizuku and InstallerX cannot bypass this Android security rule. Back up the existing app's game/settings data *before* any uninstall. After installing the first permanently signed version, preserve the same keystore for all subsequent releases.

To compare two APK signing identities on a machine with Android SDK Build Tools:

```bash
apksigner verify --print-certs PeanutsNative-DualSense-same-package.apk
```

Compare its `Signer #1 certificate SHA-256 digest` with that of the installed APK, if you have a copy. Both newly published variants should have the same digest.
