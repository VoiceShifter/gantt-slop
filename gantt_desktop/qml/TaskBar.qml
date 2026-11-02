import QtQuick
import QtQuick.Controls

Item {
    id: bar
    required property var task
    required property var workspace
    required property int rowIndex
    property string mode: "move"
    property bool dragging: false
    property bool moved: false
    property bool cancelled: false
    property bool linkHovered: false
    property int deltaDays: 0
    property real pressX: 0
    property real lastClick: 0
    property var preview: ({})
    property real progressPreview: -1
    readonly property var shown: dragging && preview.valid ? preview : task
    readonly property bool over: body.containsMouse || leftEdge.containsMouse || rightEdge.containsMouse || linkHovered || progressHandle.containsMouse
    readonly property real completion: progressPreview >= 0 ? progressPreview : task.progress
    readonly property bool critical: !!task.critical
    readonly property color displayColor: critical ? "#c93b3b" : task.color
    objectName: "taskbar-" + task.taskId
    x: (shown.startDay + (task.milestone ? 0.5 : 0)) * workspace.pixelsPerDay - (task.milestone ? 11 : 0)
    y: rowIndex * workspace.rowHeight + (workspace.rowHeight - height) / 2
    width: task.milestone ? 22 : Math.max(6, (shown.endDay - shown.startDay) * workspace.pixelsPerDay)
    height: 22
    z: dragging || over ? 5 : 2
    opacity: dragging ? 0.65 : task.status === "closed" ? 0.45 : 1
    Accessible.role: Accessible.Graphic
    Accessible.name: task.name + ", " + task.start + " — " + task.end + (bar.critical ? i18n.tr.critical_comma : "")
    Connections {
        target: workspace
        function onCancelDrags() { bar.cancelled = true; bar.dragging = false; bar.preview = ({}); bar.progressPreview = -1 }
    }

    function begin(which, area, mouse) {
        controller.select(task.taskId)
        mode = which
        pressX = area.mapToItem(workspace.sceneItem, mouse.x, mouse.y).x
        deltaDays = 0
        moved = false
        cancelled = false
        preview = ({})
    }
    function update(area, mouse) {
        const x = area.mapToItem(workspace.sceneItem, mouse.x, mouse.y).x
        if (Math.abs(x - pressX) >= 3) moved = true
        if (!moved) return
        const delta = Math.round((x - pressX) / workspace.pixelsPerDay)
        if (!dragging || delta !== deltaDays) {
            deltaDays = delta
            preview = controller.preview(task.taskId, mode, delta)
        }
        dragging = true
    }
    function finish() {
        if (cancelled) { moved = false; lastClick = 0; return }
        if (moved) {
            const id = task.taskId, delta = deltaDays, which = mode
            dragging = false
            preview = ({})
            lastClick = 0
            if (which === "move") controller.moveTask(id, delta)
            else controller.resizeTask(id, which, delta)
        } else {
            const now = Date.now()
            if (now - lastClick < 350) {
                lastClick = 0
                workspace.inspectTask(task.taskId)
            } else lastClick = now
        }
    }

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: task.summary ? 17 : 0
        color: bar.displayColor
        radius: task.summary ? 0 : 2
        visible: !task.milestone
        border.width: !task.summary && controller.selectedId === task.taskId ? 1 : 0
        border.color: "#1995a5"
        Rectangle {
            width: parent.width * bar.completion / 100
            height: parent.height
            color: bar.critical ? "#8e232b" : "#289da9"
            opacity: 0.7
            radius: parent.radius
        }
    }
    Rectangle {
        visible: task.milestone
        anchors.centerIn: parent
        width: 20; height: 20
        rotation: 45
        color: bar.displayColor
        border.width: controller.selectedId === task.taskId ? 1 : 0
        border.color: "#a94488"
    }
    Text {
        anchors.left: parent.left
        anchors.leftMargin: task.summary ? 5 : 2
        anchors.verticalCenter: task.summary ? undefined : parent.verticalCenter
        y: task.summary ? -1 : 0
        width: task.summary ? Math.max(parent.width, 420) : parent.width - 4
        height: task.summary ? 16 : 22
        text: task.summary ? task.name + " | " + task.start + " - " + task.end : task.name
        font.family: "Arial"
        font.pixelSize: 12
        font.bold: task.summary
        font.strikeout: task.status === "closed"
        color: task.summary ? (bar.critical ? appTheme.colors.danger : appTheme.colors.summary) : "white"
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
        visible: !task.milestone
    }
    Rectangle {
        visible: !task.summary && task.assignee.length > 0 && !bar.dragging
        x: parent.width + 21; y: 2
        width: 19; height: 19; radius: 10
        color: task.assigneeColor
        Text { anchors.centerIn: parent; text: task.assignee.slice(0, 1).toUpperCase(); color: "white"; font.pixelSize: 10 }
    }
    MouseArea {
        id: body
        anchors.fill: parent
        hoverEnabled: true
        preventStealing: true
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        cursorShape: controller.bulkMode ? Qt.PointingHandCursor : bar.dragging ? Qt.ClosedHandCursor : task.canMove ? Qt.OpenHandCursor : Qt.ArrowCursor
        onContainsMouseChanged: {
            if (containsMouse) workspace.hoverRow = rowIndex
            else if (workspace.hoverRow === rowIndex) workspace.hoverRow = -1
        }
        onPressed: function(mouse) {
            if (controller.bulkMode) {
                if (mouse.button === Qt.LeftButton) controller.toggleChecked(task.taskId)
                return
            }
            if (mouse.button === Qt.RightButton) { workspace.taskMenuRequested(task.taskId); return }
            bar.begin("move", body, mouse)
        }
        onPositionChanged: function(mouse) { if (!controller.bulkMode && pressed && pressedButtons & Qt.LeftButton) bar.update(body, mouse) }
        onReleased: function(mouse) { if (!controller.bulkMode && mouse.button === Qt.LeftButton) bar.finish() }
        onCanceled: { bar.dragging = false; bar.preview = ({}) }
    }
    MouseArea {
        id: leftEdge
        objectName: "resize-start-" + task.taskId
        width: 8; height: parent.height
        anchors.left: parent.left
        visible: !controller.bulkMode && !task.summary && !task.milestone
        hoverEnabled: true
        preventStealing: true
        cursorShape: task.canResizeStart ? Qt.SizeHorCursor : Qt.ForbiddenCursor
        onPressed: function(mouse) { bar.begin("start", leftEdge, mouse) }
        onPositionChanged: function(mouse) { if (pressed) bar.update(leftEdge, mouse) }
        onReleased: bar.finish()
        onCanceled: { bar.dragging = false; bar.preview = ({}) }
    }
    MouseArea {
        id: rightEdge
        objectName: "resize-end-" + task.taskId
        width: 8; height: parent.height
        anchors.right: parent.right
        visible: !controller.bulkMode && !task.summary && !task.milestone
        hoverEnabled: true
        preventStealing: true
        cursorShape: task.canResizeEnd ? Qt.SizeHorCursor : Qt.ForbiddenCursor
        onPressed: function(mouse) { bar.begin("end", rightEdge, mouse) }
        onPositionChanged: function(mouse) { if (pressed) bar.update(rightEdge, mouse) }
        onReleased: bar.finish()
        onCanceled: { bar.dragging = false; bar.preview = ({}) }
    }
    Repeater {
        model: ["S", "F"]
        delegate: Item {
            required property string modelData
            x: modelData === "S" ? -22 : bar.width
            width: 22; height: 22
            visible: !controller.bulkMode && (bar.over || workspace.linkSource !== "")
            Rectangle {
                anchors.centerIn: parent
                width: 12; height: 12; radius: 6
                readonly property bool origin: workspace.linkSource === task.taskId && workspace.sourceEnd === modelData
                color: origin ? appTheme.colors.selection : appTheme.colors.raised; border.color: origin ? appTheme.colors.link : appTheme.colors.strongBorder
            }
            MouseArea {
                id: linkArea
                objectName: "link-" + modelData + "-" + task.taskId
                anchors.fill: parent
                hoverEnabled: true
                preventStealing: true
                cursorShape: Qt.CrossCursor
                property real downX: 0
                property real downY: 0
                property bool linkMoved: false
                onContainsMouseChanged: bar.linkHovered = containsMouse
                onPressed: function(mouse) {
                    const point = mapToItem(workspace.sceneItem, mouse.x, mouse.y)
                    if (workspace.linkSource && workspace.linkSource !== task.taskId) {
                        workspace.connectTo(task.taskId, modelData)
                        return
                    } else {
                        workspace.beginLink(task.taskId, modelData, point.x, point.y)
                    }
                    downX = point.x; downY = point.y; linkMoved = false
                }
                onPositionChanged: function(mouse) {
                    if (!pressed || !workspace.linkSource) return
                    const point = mapToItem(workspace.sceneItem, mouse.x, mouse.y)
                    if (Math.abs(point.x - downX) + Math.abs(point.y - downY) > 3) linkMoved = true
                    workspace.updateLink(point.x, point.y)
                }
                onReleased: function(mouse) {
                    workspace.linkDragging = false
                    if (linkMoved && workspace.linkSource) {
                        const point = mapToItem(workspace.sceneItem, mouse.x, mouse.y)
                        workspace.finishLink(point.x, point.y)
                    }
                }
                onCanceled: workspace.cancelLink()
                ToolTip.visible: containsMouse
                ToolTip.text: modelData === "S" ? i18n.tr.link_from_start : i18n.tr.link_from_end
            }
        }
    }
    MouseArea {
        id: progressHandle
        objectName: "progress-" + task.taskId
        x: Math.max(0, bar.width * bar.completion / 100 - 5)
        y: 18; width: 12; height: 11
        visible: !controller.bulkMode && !task.summary && !task.milestone && (bar.over || pressed)
        hoverEnabled: true
        preventStealing: true
        cursorShape: Qt.SizeHorCursor
        Rectangle { anchors.centerIn: parent; width: 7; height: 7; rotation: 45; color: appTheme.colors.muted; border.color: appTheme.colors.strongBorder }
        onPressed: function(mouse) { bar.cancelled = false; bar.progressPreview = task.progress }
        onPositionChanged: function(mouse) {
            if (pressed) bar.progressPreview = Math.max(0, Math.min(100, mapToItem(bar, mouse.x, mouse.y).x / bar.width * 100))
        }
        onReleased: {
            if (bar.cancelled) { bar.progressPreview = -1; return }
            const value = String(Math.round(bar.completion)), id = task.taskId
            bar.progressPreview = -1
            controller.editField(id, "progress", value)
        }
    }
    ToolTip.visible: bar.dragging || (body.containsMouse && workspace.linkSource === "")
    ToolTip.delay: bar.dragging ? 0 : 600
    ToolTip.text: bar.dragging ? (bar.preview.hint || "") : task.name + "\n" + task.start + " — " + task.end + " · " + Math.round(task.progress) + "%" +
                  (controller.criticalPath && task.totalFloat !== null && task.totalFloat !== undefined ? "\n" + (bar.critical ? (i18n.tr.critical_label + " · ") : "") + i18n.tr.float_prefix + Number(task.totalFloat/60).toLocaleString(Qt.locale(),"g",6) + i18n.tr.work_h : "")
}
