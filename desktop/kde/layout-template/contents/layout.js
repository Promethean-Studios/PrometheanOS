// KDE Plasma layout-template API. The existing Plasma shell remains in place.
var topPanel = new Panel;
topPanel.location = "top";
topPanel.height = 38;
topPanel.alignment = "left";
topPanel.addWidget("org.kde.plasma.kickoff");
topPanel.addWidget("org.kde.plasma.appmenu");
topPanel.addWidget("org.kde.plasma.systemtray");
topPanel.addWidget("org.kde.plasma.digitalclock");

var taskDock = new Panel;
taskDock.location = "bottom";
taskDock.alignment = "center";
taskDock.height = 58;
taskDock.hiding = "dodgewindows";
taskDock.alwaysVisible = false;
taskDock.addWidget("org.kde.plasma.icontasks");