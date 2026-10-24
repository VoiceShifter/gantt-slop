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
    palette.buttonText: appTheme.colors.text
    Accessible.name: hint || text
    background: Rectangle {
        radius: 3
        color: control.primary ? (control.down ? appTheme.colors.accentPressed : appTheme.colors.accent)
                               : control.checked ? appTheme.colors.selection : control.hovered ? appTheme.colors.hover : "transparent"
        border.width: control.activeFocus ? 1 : 0
        border.color: appTheme.colors.link
        opacity: control.enabled ? 1 : 0.4
    }
    contentItem: Text {
        id: label
        text: control.text
        font: control.font
        color: control.primary ? "white" : !control.enabled ? appTheme.colors.disabled : control.palette.buttonText
        horizontalAlignment: Text.AlignHCenter
        verticalAlignment: Text.AlignVCenter
    }
    ToolTip.visible: hovered && hint.length > 0
    ToolTip.text: hint
    ToolTip.delay: 450
}
