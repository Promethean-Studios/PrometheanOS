# Promethean Desktop

The desktop layer extends KDE Plasma and keeps the stock Plasma shell,
application launcher, panel, and system tray. The assets under `kde/` are
user-scoped and use supported KDE configuration files and commands.

Apply the visual defaults as the desktop user:

```bash
./desktop/kde/apply-promethean.sh
```

The template provides a KDE Kickoff launcher, top panel, task buttons, system
tray, clock, and a centered bottom task dock. Applying the layout is opt-in
because Plasma layout templates can replace a user's existing panel placement:

```bash
PROMETHEAN_APPLY_LAYOUT=1 ./desktop/kde/apply-promethean.sh
```

Enable the conservative profile on lower-end hardware:

```bash
./desktop/kde/apply-low-end.sh
```

The Control Center is served by the local Promethean API at
`http://127.0.0.1:8765/control-center`. It only reads telemetry; permissions
and privileged operations remain in the backend service.