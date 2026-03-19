# Building FlareTrack Android App

This guide explains how to build the FlareTrack mobile application as an Android APK using Kivy and Buildozer.

## Prerequisites

### System Requirements
- **Linux** (Ubuntu 20.04+ recommended) or **WSL2** on Windows
- Python 3.7+
- At least 10 GB free disk space
- 4+ GB RAM

### Install Dependencies (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip autoconf libtool pkg-config zlib1g-dev libncurses5-dev libncursesw5-dev libtinyxml-dev wget
```

## Installation Steps

### 1. Clone the Repository

```bash
git clone https://github.com/TheFlood424K/FlareTrack.git
cd FlareTrack
```

### 2. Install Python Dependencies

```bash
pip3 install -r requirements.txt
```

### 3. Test the Mobile App Locally (Optional)

Before building for Android, you can test the Kivy UI on your computer:

```bash
python3 mobile_app.py
```

## Building the Android APK

### Method 1: Using Buildozer (Recommended)

```bash
# Initialize buildozer (first time only)
buildozer init

# Build APK in debug mode
buildozer -v android debug
```

The APK will be created in `bin/flaretrack-1.0-armeabi-v7a-debug.apk`

### Method 2: Build and Deploy to Connected Device

```bash
# Build and install on connected Android device
buildozer android debug deploy run
```

### Method 3: Release Build (for distribution)

```bash
# Create a release APK (requires signing)
buildozer android release
```

## Configuration

The `buildozer.spec` file contains all build settings:

- **App Name**: `FlareTrack`
- **Package**: `org.flaretrack`
- **Version**: `1.0`
- **Orientation**: Portrait
- **Permissions**: Storage (for saving health data)
- **Min Android API**: 21 (Android 5.0)
- **Target API**: 31 (Android 12)

## Troubleshooting

### Build Fails with "SDK not found"

Buildozer will automatically download the Android SDK and NDK. If it fails:

```bash
# Clean and rebuild
buildozer android clean
buildozer -v android debug
```

### Out of Memory Errors

Increase Java heap size:

```bash
export GRADLE_OPTS="-Xmx2048m"
buildozer -v android debug
```

### Permission Denied Errors

Don't run buildozer as root:

```bash
# Fix permissions if needed
sudo chown -R $USER:$USER ~/.buildozer
```

## Running on Android Device

### Via USB (ADB)

1. Enable Developer Options on your Android device
2. Enable USB Debugging
3. Connect device via USB
4. Run:

```bash
buildozer android deploy run
```

### Manual Installation

1. Copy `bin/flaretrack-1.0-armeabi-v7a-debug.apk` to your device
2. Enable "Install from Unknown Sources" in Settings
3. Open the APK file and install

## App Features

The mobile app includes:

✅ Log symptoms with severity ratings
✅ Track medications
✅ Record environmental factors
✅ View daily health summaries
✅ AI-powered flare-up predictions
✅ Offline data storage (JSON)

## File Structure

```
FlareTrack/
├── mobile_app.py          # Kivy mobile UI
├── buildozer.spec         # Android build configuration
├── tracker.py             # Core tracking logic
├── models.py              # Data models
├── storage.py             # JSON storage
├── ai_engine.py           # Prediction engine
└── requirements.txt       # Python dependencies
```

## Development Tips

### Testing UI Changes

Edit `mobile_app.py` and test locally before rebuilding:

```bash
python3 mobile_app.py
```

### Viewing Logs

```bash
buildozer android logcat
```

### Cleaning Build Cache

```bash
buildozer android clean
rm -rf .buildozer/
```

## Support

For issues or questions:
- Open an issue on GitHub
- Check Kivy documentation: https://kivy.org
- Buildozer docs: https://buildozer.readthedocs.io

## License

See main repository LICENSE file.
