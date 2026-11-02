import QtQuick
import QtQuick.Controls

Button {
    id: control
    property var resourceIds: []
    property bool framed: false
    property string placeholderText: i18n.tr.unassigned
    readonly property var resources: controller.resourceCatalog.filter(r=>resourceIds.indexOf(r.id)>=0)
    readonly property string names: resources.map(r=>r.name).join(", ")
    implicitHeight: 30
    implicitWidth: 140
    hoverEnabled: true
    clip: true
    padding: 0
    Accessible.name: i18n.tr.assignee_prefix + (names || placeholderText)
    background: Rectangle {
        radius: 3
        color: control.framed ? appTheme.colors.input : control.hovered ? appTheme.colors.hover : "transparent"
        border.width: control.framed || control.activeFocus ? 1 : 0
        border.color: control.activeFocus ? appTheme.colors.link : appTheme.colors.border
    }
    contentItem: Item {
        Rectangle {
            x: 7; anchors.verticalCenter: parent.verticalCenter
            width: 18; height: 18; radius: 9
            visible: control.resources.length>0
            color: control.resources.length ? control.resources[0].color : "transparent"
            Text { anchors.centerIn: parent; text: control.resources.length ? control.resources[0].name.slice(0,1).toUpperCase() : ""; color: "white"; font.pixelSize: 10 }
        }
        Text {
            x: control.resources.length ? 30 : 8
            width: Math.max(0,parent.width-x-19); height: parent.height
            text: control.names || control.placeholderText; textFormat: Text.PlainText
            color: control.resources.length ? appTheme.colors.text : appTheme.colors.muted
            font.pixelSize: 12; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
        }
        Text { anchors.right: parent.right; anchors.rightMargin: 6; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: appTheme.colors.muted; font.pixelSize: 12 }
    }
    ToolTip.visible: hovered
    ToolTip.text: resources.length ? resources.map(r=>r.name).join("\n") : i18n.tr.choose_assignees_hint
    ToolTip.delay: 500
}
