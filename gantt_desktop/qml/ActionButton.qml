import QtQuick
import QtQuick.Controls

Button {
    id: control
    property string hint: ""
    property bool primary: false
    implicitHeight: 28
    implicitWidth: Math.max(28, label.implicitWidth + 18)
    leftPadding: 9
    rightPadding: 9
    hoverEnabled: true
    font.family: "Arial"
    font.pixelSize: 12
    palette.buttonText: "#30363b"
    Accessible.name: hint || text
    background: Rectangle {
        radius: 3
        color: control.primary ? (control.down ? "#1055b0" : "#1766cb")
                               : control.checked ? "#deecfa" : control.hovered ? "#edf2f7" : "transparent"
        border.width: control.activeFocus ? 1 : 0
        border.color: "#1876dd"
        opacity: control.enabled ? 1 : 0.4
    }
    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: !control.enabled ? "#bfc2c5" : control.primary ? "white" : control.palette.buttonText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    ToolTip.visible: hovered && hint.length > 0
    ToolTip.text: hint
    ToolTip.delay: 450
}
