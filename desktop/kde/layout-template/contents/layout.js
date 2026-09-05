// KDE Plasma layout-template API. The existing Plasma shell remains in place.
var topPanel = new Panel;
topPanel.location = "top";
topPanel.height = 34;
topPanel.addWidget("org.kde.plasma.kickoff");
topPanel.addWidget("org.kde.plasma.appmenu");
topPanel.addWidget("org.kde.plasma.icontasks");
topPanel.addWidget("org.kde.plasma.systemtray");
topPanel.addWidget("org.kde.plasma.digitalclock");

var taskDock = new Panel;
taskDock.location = "bottom";
taskDock.alignment = "center";
taskDock.height = 52;
taskDock.addWidget("org.kde.plasma.icontasks");