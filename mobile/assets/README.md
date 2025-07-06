# Assets Directory

This directory contains all the static assets for the mobile app.

## Directory Structure

```
assets/
├── favicon.png          # Web favicon (placeholder)
├── images/              # Image assets
│   └── .gitkeep        # Keeps directory in git
└── README.md           # This file
```

## Adding Your Own Assets

### App Icons
- **icon.png** (1024x1024) - Main app icon
- **splash.png** (1242x2436) - Splash screen
- **adaptive-icon.png** (1024x1024) - Android adaptive icon

### Images
Place any images used in your app in the `images/` directory.

### Usage
Once you add assets, update the `app.json` file to reference them:

```json
{
  "expo": {
    "icon": "./assets/icon.png",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain"
    }
  }
}
```

## Current Status
- ✅ Basic directory structure created
- ✅ Placeholder favicon for web
- ✅ Ready for custom assets 