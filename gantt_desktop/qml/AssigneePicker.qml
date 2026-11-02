import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Popup {
    id: picker
    objectName: "assigneePicker"
    property string taskId: ""
    property bool bulkEdit: false
    property var selectedIds: []
    property real anchorX: 8
    property real aboveY: 8
    property real belowY: 8
    readonly property var resources: controller.resourceCatalog.filter(r=>r.name.toLowerCase().indexOf(search.text.toLowerCase().trim())>=0)
    width: Math.min(370,parent.width-16)
    height: Math.min(parent.height-16,190+Math.min(7,Math.max(1,resources.length))*32)
    x: Math.max(8,Math.min(parent.width-width-8,anchorX))
    y: belowY+height<=parent.height-8 ? belowY : Math.max(8,aboveY-height)
    padding: 0
    modal: false
    focus: true
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    signal bulkChosen(var ids)
    signal createRequested(string name)
    signal advancedRequested(string taskId, var ids)
    background: Rectangle { color: appTheme.colors.surface; border.color: appTheme.colors.border; radius: 4 }

    function locate(anchor) {
        const point=anchor.mapToItem(parent,0,0)
        anchorX=point.x; aboveY=point.y; belowY=point.y+anchor.height
        search.text=""
    }
    function openTask(id, anchor) {
        taskId=id; bulkEdit=false
        selectedIds=(controller.selected.resourceIds || []).slice()
        locate(anchor); open()
    }
    function availableIds(ids) { return ids.filter(id=>controller.resourceCatalog.some(r=>r.id===id)) }
    function openBulk(ids, anchor) {
        taskId=""; bulkEdit=true; selectedIds=availableIds(ids)
        locate(anchor); open()
    }
    function toggle(id) {
        selectedIds=selectedIds.indexOf(id)>=0 ? selectedIds.filter(key=>key!==id) : selectedIds.concat([id])
    }
    function apply(advanced) {
        const id=taskId, ids=selectedIds.slice()
        if (bulkEdit) { bulkChosen(ids); close(); return }
        if (advanced) { close(); advancedRequested(id,ids); return }
        if (controller.chooseTaskResources(id,ids)) close()
    }
    onOpened: search.forceActiveFocus()
    onClosed: { taskId=""; selectedIds=[] }
    Connections {
        target: controller
        function onProjectLoaded() { picker.close() }
        function onViewChanged() { if (picker.visible) picker.selectedIds=picker.availableIds(picker.selectedIds) }
        function onSelectionChanged() { if (picker.visible && !picker.bulkEdit && controller.selectedId!==picker.taskId) picker.close() }
        function onBulkChanged() { if (picker.visible && picker.bulkEdit && !controller.bulkMode) picker.close() }
    }
    contentItem: Item {
        focus: true
        Keys.onEscapePressed: picker.close()
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            Label { text: i18n.tr.assignees; color: appTheme.colors.text; font.bold: true; font.pixelSize: 13 }
            CellEditor {
                id: search
                objectName: "assigneeSearch"
                Layout.fillWidth: true
                placeholderText: i18n.tr.find_resource
                background: Rectangle { color: appTheme.colors.input; border.color: search.activeFocus ? appTheme.colors.link : appTheme.colors.border; radius: 3 }
            }
            ListView {
                id: list
                objectName: "assigneeList"
                Layout.fillWidth: true; Layout.fillHeight: true
                clip: true; model: picker.resources
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ScrollBar { policy: ScrollBar.AsNeeded }
                delegate: Item {
                    required property var modelData
                    width: list.width; height: 32
                    CheckBox {
                        objectName: "assignee-option-" + modelData.id
                        x: 0; width: 30; height: parent.height
                        checked: picker.selectedIds.indexOf(modelData.id)>=0
                        nextCheckState: function() { return checkState }
                        onClicked: picker.toggle(modelData.id)
                        Accessible.name: modelData.name
                    }
                    Rectangle {
                        x: 36; y: 7; width: 18; height: 18; radius: 9; color: modelData.color
                        Text { anchors.centerIn: parent; text: modelData.name.slice(0,1).toUpperCase(); color: "white"; font.pixelSize: 10 }
                    }
                    Text { x: 63; width: Math.max(0,parent.width-x-8); height: parent.height; text: modelData.name; textFormat: Text.PlainText; color: appTheme.colors.text; font.pixelSize: 12; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter }
                    MouseArea { x: 31; width: parent.width-x; height: parent.height; cursorShape: Qt.PointingHandCursor; onClicked: picker.toggle(modelData.id) }
                }
                Label { anchors.centerIn: parent; visible: picker.resources.length===0; text: i18n.tr.no_resources_found; color: appTheme.colors.muted; font.pixelSize: 12 }
            }
            Label { text: i18n.tr.selected_count_prefix + picker.selectedIds.length + i18n.tr.apply_by_ok; color: appTheme.colors.muted; font.pixelSize: 11 }
            RowLayout {
                Layout.fillWidth: true; spacing: 4
                ActionButton { objectName: "resetAssignees"; text: i18n.tr.reset; enabled: picker.selectedIds.length>0; onClicked: picker.selectedIds=[] }
                ActionButton { objectName: "assigneeHoursButton"; text: i18n.tr.hours_btn; visible: !picker.bulkEdit; onClicked: picker.apply(true) }
                Item { Layout.fillWidth: true }
                ActionButton { objectName: "cancelAssignees"; text: i18n.tr.cancel; onClicked: picker.close() }
                ActionButton { objectName: "applyAssignees"; text: i18n.tr.ok; primary: true; onClicked: picker.apply(false) }
            }
            ActionButton { objectName: "addAssigneeResource"; text: i18n.tr.add_resource_btn; Layout.fillWidth: true; palette.buttonText: appTheme.colors.link; onClicked: picker.createRequested(search.text.trim()) }
        }
    }
}
