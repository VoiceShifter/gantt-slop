import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Drawer {
    id: drawer
    objectName: "settingsDrawer"
    edge: Qt.RightEdge
    width: Math.min(420, parent.width - 20)
    height: parent.height
    padding: 0
    modal: true
    focus: true
    interactive: false
    background: Rectangle { color: appTheme.colors.surface; border.color: appTheme.colors.border }
    contentItem: Item {
        focus: true
        Keys.onEscapePressed: drawer.close()
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 24
            spacing: 18
            RowLayout {
                Layout.fillWidth: true
                Label { text: "Настройки"; font.bold: true; font.pixelSize: 20; color: appTheme.colors.text }
                Item { Layout.fillWidth: true }
                ActionButton { objectName: "closeSettingsButton"; text: "×"; hint: "Закрыть настройки"; onClicked: drawer.close() }
            }
            Rectangle { Layout.fillWidth: true; height: 1; color: appTheme.colors.border }
            Label { text: "Внешний вид"; font.bold: true; color: appTheme.colors.text }
            Switch {
                id: themeSwitch
                objectName: "themeSwitch"
                text: "Тёмная тема"
                checked: appTheme.dark
                onClicked: appTheme.setDark(checked)
                Accessible.name: text
                indicator: Rectangle {
                    objectName: "themeSwitchTrack"
                    implicitWidth: 46; implicitHeight: 24; radius: 12
                    x: themeSwitch.leftPadding; y: (themeSwitch.height-height)/2
                    color: themeSwitch.checked ? appTheme.colors.accent : appTheme.colors.strongBorder
                    Rectangle {
                        objectName: "themeSwitchThumb"
                        width: 20; height: 20; radius: 10; y: 2
                        x: 2 + (parent.width-width-4)*themeSwitch.visualPosition
                        color: "white"
                    }
                }
            }
            Label {
                Layout.fillWidth: true
                text: "Одна тема для диаграммы, таблицы, панелей и всех диалогов."
                wrapMode: Text.WordWrap
                color: appTheme.colors.secondary
            }
            Item { Layout.fillHeight: true }
            Label {
                Layout.fillWidth: true
                text: "Изменения применяются сразу и сохраняются между запусками на этом компьютере. Файл проекта не меняется."
                wrapMode: Text.WordWrap
                font.pixelSize: 12
                color: appTheme.colors.muted
            }
            ActionButton { text: "Готово"; primary: true; Layout.fillWidth: true; implicitHeight: 34; onClicked: drawer.close() }
        }
    }
}
