# Decky Screen Saver

This fork adds Steam-style dropdowns for configuring separate battery and AC
screen-dimming and sleep timeouts. Available values are Disabled, 1 minute,
5 minutes, 15 minutes, 30 minutes, and 1 hour. Changes are saved and applied
directly to Steam's power settings.

It also adds media-aware screen inhibition for Firefox and Plex. Playing media
prevents dimming and sleep, while pausing, stopping, or closing the player
restores your selected Steam timeouts after a three-second grace period.
Resuming playback during that grace period keeps inhibition active.

Runtime monitoring can be enabled or disabled with the Background Monitor
setting. Optional Diagnostic Logging records portal, MPRIS, policy, inhibitor,
and power-setting activity without affecting whether the monitors run.

Credits to xfangfang, buy him a cup of coffee (https://www.paypal.me/xfangfang)

[中文说明](./README_ZH.md)

This is a plugin for Decky Loader (A plugin loader for the Steam Deck), it will automatically inhibit screensaver during video playback under SteamOS game mode.

### How to install

1. Install Decky Loader: https://decky.xyz
2. Download `ScreenSaver.zip` from: https://github.com/xfangfang/DeckyInhibitScreenSaver/releases
3. Unzip `ScreenSaver.zip` to the `/home/deck/homebrew/plugins` directory and restart Steam

[Welcome to buy me a cup of coffee](https://www.paypal.me/xfangfang)

### Build

From the plugin directory, run:

```bash
./cli/decky plugin build "$(pwd)"
```

### How does this plugin work

In SteamDeck game mode, when using the browser or video player, SteamDeck will automatically suspend in a few minutes. You need to manually modify the relevant system settings to prevent this behavior.

This plugin registers and monitors the missing D-Bus services in game mode, automatically preventing the system from suspending when receiving a request from a application. And restore the default settings when the application closes or cancels the request (dimming: 5 minutes, suspending: 10 minutes)


### Compatible application
- [x] VLC
- [x] Chrome
- [x] mpv (Works out-of-the-box with the Flathub build; all other packages require [mpv_inhibit_gnome](https://github.com/Guldoman/mpv_inhibit_gnome))
