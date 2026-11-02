import QtQuick

CellEditor {
    id: field
    property bool calendarVisible: true
    signal calendarRequested()
    rightPadding: calendarVisible ? 28 : 8
    Loader {
        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 24; height: parent.height
        active: field.calendarVisible
        sourceComponent: Component {
            ActionButton {
                objectName: "calendar-" + field.objectName
                text: "▦"
                hint: i18n.tr.choose_date_in_calendar
                leftPadding: 0; rightPadding: 0
                enabled: field.enabled && !field.readOnly
                onClicked: field.calendarRequested()
            }
        }
    }
}
