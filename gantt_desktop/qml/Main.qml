import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window

ApplicationWindow {
    id: window
    objectName: "mainWindow"
    width: Math.min(1600, Screen.width - 60)
    height: Math.min(960, Screen.height - 70)
    minimumWidth: 1000
    minimumHeight: 650
    visible: true
    title: controller.projectName + (controller.dirty ? " *" : "") + " — Gantt Desktop"
    color: appTheme.colors.surface
    palette.window: appTheme.colors.surface
    palette.windowText: appTheme.colors.text
    palette.base: appTheme.colors.input
    palette.alternateBase: appTheme.colors.panel
    palette.text: appTheme.colors.text
    palette.button: appTheme.colors.panel
    palette.buttonText: appTheme.colors.text
    palette.highlight: appTheme.colors.accent
    palette.highlightedText: "white"
    palette.placeholderText: appTheme.colors.muted
    palette.toolTipBase: appTheme.colors.raised
    palette.toolTipText: appTheme.colors.text
    font.family: "Arial"
    font.pixelSize: 13
    property bool allowClose: false
    property bool sidebarVisible: true
    property string filterCode: "all"
    property bool workloadVisible: false
    property real workloadHeight: 230
    readonly property bool editingText: activeFocusItem && activeFocusItem.cursorPosition !== undefined
    readonly property bool modalBlocked: nativeDialogs.modalOpen || settings.visible || assigneePicker.visible
    onClosing: function(event) { if (!allowClose) event.accepted = controller.confirmClose() }

    function inspectTask(id) { if (!controller.bulkMode) { controller.select(id); inspector.open() } }
    function selectedParent() { return controller.selected.summary ? controller.selectedId : (controller.selected.parentId || "") }
    function showTaskMenu(id) { if (!controller.bulkMode) { controller.select(id); taskMenu.popup() } }
    function askDelete(id) { if (id) nativeDialogs.confirmDelete(id,false) }
    function askBulkDelete() { if (controller.bulkDeleteCount>0) nativeDialogs.confirmDelete("",true) }
    function showDependency(source,target,kind,id) { gantt.cancelInteractions(); nativeDialogs.showDependency(source,target,kind,id) }
    function showResources(id) { gantt.cancelInteractions(); nativeDialogs.showResources(id) }
    function showFields() { gantt.cancelInteractions(); nativeDialogs.showFields(gantt.columnVisibility()) }
    function showAssignments(id) { gantt.cancelInteractions(); controller.select(id); nativeDialogs.showAssignments(id) }
    function showAssigneePicker(id, anchor) { gantt.cancelInteractions(); controller.select(id); assigneePicker.openTask(id,anchor) }
    function saveProject() { contentItem.forceActiveFocus(); controller.save() }
    function showExport() {
        contentItem.forceActiveFocus(); gantt.cancelInteractions()
        nativeDialogs.showExport({columns:gantt.columns,pixelsPerDay:gantt.pixelsPerDay,workload:window.workloadVisible})
    }

    Connections {
        target: controller
        function onToast(message) { notification.text=message; notice.visible=true; toastTimer.restart() }
        function onInspectRequested() { inspector.open(); controller.focusTask(controller.selectedId) }
        function onProjectLoaded() { inspector.close(); search.text=""; window.filterCode="all"; gantt.scrollX=0; gantt.hiddenCustomFields=[] }
        function onBulkChanged() {
            if (controller.bulkMode) {
                inspector.close()
                if (!bulkEditor.visible) bulkEditor.open()
            } else if (bulkEditor.visible) bulkEditor.close()
        }
    }
    Connections {
        target: nativeDialogs
        function onColumnVisibilityChanged(key, shown) { gantt.setColumnVisible(key,shown) }
    }
    Shortcut { sequences: [StandardKey.Save]; enabled:!window.modalBlocked; onActivated: window.saveProject() }
    Shortcut { sequence: "Ctrl+Shift+S"; enabled:!window.modalBlocked; onActivated: controller.saveAs() }
    Shortcut { sequences: [StandardKey.Open]; enabled:!window.modalBlocked; onActivated: controller.openProject() }
    Shortcut { sequences: [StandardKey.New]; enabled:!window.modalBlocked; onActivated: controller.newProject() }
    Shortcut { sequences: [StandardKey.Undo]; enabled:!window.modalBlocked && !window.editingText; onActivated: controller.undo() }
    Shortcut { sequences: [StandardKey.Redo]; enabled:!window.modalBlocked && !window.editingText; onActivated: controller.redo() }
    Shortcut { sequence: "Delete"; enabled:!window.modalBlocked && !window.editingText && !controller.bulkMode && !!controller.selectedId; onActivated: window.askDelete(controller.selectedId) }
    Shortcut { sequence: "Delete"; enabled:!window.modalBlocked && !window.editingText && controller.bulkMode && controller.bulkDeleteCount>0; onActivated: window.askBulkDelete() }
    Shortcut { sequences: [StandardKey.SelectAll]; enabled:!window.modalBlocked && controller.bulkMode && !window.editingText; onActivated: controller.setAllChecked(true) }
    Shortcut { sequence: "Escape"; enabled:!window.modalBlocked; onActivated: { gantt.cancelInteractions(); if (controller.bulkMode) controller.setBulkMode(false); if (inspector.opened) inspector.close(); contentItem.forceActiveFocus() } }
    Shortcut { sequence: "Return"; enabled:!window.modalBlocked && !controller.bulkMode && !window.editingText && !!controller.selectedId && !inspector.opened; onActivated: window.inspectTask(controller.selectedId) }
    Shortcut { sequence: "Ctrl+F"; enabled:!window.modalBlocked; onActivated: { search.forceActiveFocus(); search.selectAll() } }

    Menu {
        id: fileMenu
        MenuItem { text: "Новый проект"; onTriggered: controller.newProject() }
        MenuItem { text: "Открыть…"; onTriggered: controller.openProject() }
        MenuSeparator {}
        MenuItem { text: "Сохранить"; onTriggered: window.saveProject() }
        MenuItem { text: "Сохранить как…"; onTriggered: controller.saveAs() }
        MenuSeparator {}
        MenuItem { text: "Открыть демонстрационный проект"; onTriggered: controller.loadExample() }
    }
    Menu {
        id: taskMenu
        MenuItem { text: "Открыть задачу"; onTriggered: window.inspectTask(controller.selectedId) }
        MenuItem { text: "Показать на диаграмме"; onTriggered: controller.focusTask(controller.selectedId) }
        MenuSeparator {}
        MenuItem { text: "Добавить задачу"; onTriggered: controller.addTask(window.selectedParent(),"task") }
        MenuItem { text: "Добавить веху"; onTriggered: controller.addTask(window.selectedParent(),"milestone") }
        MenuItem { text: "Добавить подзадачу"; enabled: controller.selected.summary || false; onTriggered: controller.addTask(controller.selectedId,"task") }
        MenuSeparator {}
        MenuItem { text: "Переместить выше"; onTriggered: controller.reorder(controller.selectedId,-1) }
        MenuItem { text: "Переместить ниже"; onTriggered: controller.reorder(controller.selectedId,1) }
        MenuItem { text: "Добавить зависимость"; enabled: !!controller.selectedId; onTriggered: window.showDependency("",controller.selectedId,"FS","") }
        MenuSeparator {}
        MenuItem { text: "Удалить"; onTriggered: window.askDelete(controller.selectedId) }
    }
    Menu {
        id: filterMenu
        MenuItem { text:"Все задачи"; checkable:true; checked:window.filterCode==="all"; onTriggered:{window.filterCode="all";controller.setFilter("all")} }
        MenuItem { text:"Незавершённые"; checkable:true; checked:window.filterCode==="incomplete"; onTriggered:{window.filterCode="incomplete";controller.setFilter("incomplete")} }
        MenuItem { text:"Завершённые"; checkable:true; checked:window.filterCode==="complete"; onTriggered:{window.filterCode="complete";controller.setFilter("complete")} }
        MenuItem { text:"Просроченные"; checkable:true; checked:window.filterCode==="overdue"; onTriggered:{window.filterCode="overdue";controller.setFilter("overdue")} }
    }
    Menu {
        id: viewMenu
        MenuItem { text:"К началу проекта"; onTriggered:gantt.centerDay(7) }
        MenuItem { text:"К выбранной задаче"; enabled:!!controller.selectedId; onTriggered:controller.focusTask(controller.selectedId) }
        MenuSeparator {}
        MenuItem { text:window.sidebarVisible?"Скрыть боковую панель":"Показать боковую панель"; onTriggered:window.sidebarVisible=!window.sidebarVisible }
        MenuItem { text:"Сбросить ширину таблицы"; onTriggered:gantt.resetColumnWidths() }
    }
    Settings { id: settings; parent: Overlay.overlay }
    AssigneePicker {
        id: assigneePicker
        parent: Overlay.overlay
        onBulkChosen: function(ids) { bulkEditor.draftResourceIds=ids }
        onCreateRequested: function(name) { nativeDialogs.showNewResource(name) }
        onAdvancedRequested: function(id,ids) { nativeDialogs.showAssignments(id,ids) }
    }
    BulkEditor {
        id: bulkEditor
        parent: Overlay.overlay
        onDeleteRequested: window.askBulkDelete()
        onAssigneePickerRequested: function(ids,anchor) { gantt.cancelInteractions(); assigneePicker.openBulk(ids,anchor) }
    }
    TaskInspector {
        id: inspector
        parent: Overlay.overlay
        onDependencyRequested: function(source,target,kind,id) { window.showDependency(source,target,kind,id) }
        onDeleteRequested: function(id) { window.askDelete(id) }
        onAssignmentRequested: function(id) { window.showAssignments(id) }
        onAssigneePickerRequested: function(id,anchor) { window.showAssigneePicker(id,anchor) }
    }

    RowLayout {
        anchors.fill: parent
        spacing: 0
        Rectangle {
            id: sidebar
            Layout.preferredWidth: window.sidebarVisible?260:0
            Layout.fillHeight: true
            visible: window.sidebarVisible
            clip: true
            color: appTheme.colors.surface
            Rectangle { anchors.right:parent.right; width:1; height:parent.height; color:appTheme.colors.border }
            ColumnLayout {
                anchors.fill:parent
                anchors.margins:12
                spacing:14
                RowLayout {
                    Layout.fillWidth:true
                    Label { text:"GANTT DESKTOP"; color:appTheme.colors.brand; font.bold:true; font.pixelSize:21 }
                    Item { Layout.fillWidth:true }
                    ActionButton { text:"⇤"; hint:"Скрыть панель проектов"; onClicked:window.sidebarVisible=false }
                }
                Label { text:"Локальные проекты"; font.bold:true; font.pixelSize:15; color:appTheme.colors.text }
                ActionButton { text:"＋  Создать новый проект"; primary:true; Layout.fillWidth:true; implicitHeight:33; onClicked:controller.newProject() }
                Rectangle {
                    Layout.fillWidth:true; height:32; color:appTheme.colors.selection; radius:3
                    Label { x:14; anchors.verticalCenter:parent.verticalCenter; text:"□   Текущий проект"; color:appTheme.colors.text; font.bold:true }
                    MouseArea { anchors.fill:parent; onClicked:{inspector.close();gantt.centerDay(7)} }
                }
                ActionButton { text:"Открыть проект…"; Layout.fillWidth:true; onClicked:controller.openProject() }
                ActionButton { text:"Сохранить проект"; Layout.fillWidth:true; onClicked:window.saveProject() }
                ActionButton { text:"Демонстрационный проект"; Layout.fillWidth:true; onClicked:controller.loadExample() }
                Item { Layout.fillHeight:true }
                Rectangle {
                    Layout.fillWidth:true; height:88; color:appTheme.colors.panel; radius:4
                    Column {
                        x:14; y:15; width:parent.width-28; spacing:9
                        Text { text:controller.fileName; width:parent.width; elide:Text.ElideMiddle; color:appTheme.colors.secondary; font.pixelSize:12 }
                        Text { text:controller.dirty?"Есть несохранённые изменения":"Изменения сохранены"; color:controller.dirty?appTheme.colors.warning:appTheme.colors.muted; font.pixelSize:11 }
                        Text { text:"Локальный файл · Без аккаунта"; color:appTheme.colors.muted; font.pixelSize:11 }
                    }
                }
                ActionButton { objectName:"helpButton"; text:"?  Помощь"; onClicked:nativeDialogs.showHelp() }
            }
        }
        ColumnLayout {
            Layout.fillWidth:true; Layout.fillHeight:true
            spacing:0
            Item {
                Layout.fillWidth:true; Layout.preferredHeight:44
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:12; anchors.rightMargin:14; spacing:10
                    ActionButton { text:"⇥"; visible:!window.sidebarVisible; hint:"Показать панель проектов"; onClicked:window.sidebarVisible=true }
                    ActionButton { text:"Файл ⌄"; onClicked:fileMenu.popup() }
                    CellEditor { text:controller.projectName; font.bold:true; font.pixelSize:15; Layout.preferredWidth:280; onEditingFinished:if(text!==controller.projectName)controller.renameProject(text) }
                    Item { Layout.fillWidth:true }
                    Text { visible:window.width>=1200; text:"Локальный проект"; color:appTheme.colors.muted; font.pixelSize:12 }
                    ActionButton { objectName:"settingsButton"; text:"⚙ Настройки"; hint:"Настройки приложения"; onClicked:{gantt.cancelInteractions();settings.open()} }
                    ActionButton { text:"Сохранить"; hint:"Сохранить · Ctrl+S"; onClicked:window.saveProject() }
                }
            }
            Item {
                Layout.fillWidth:true; Layout.preferredHeight:30
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:appTheme.colors.border }
                Text { x:14; y:4; text:"Диаграмма"; color:appTheme.colors.link; font.bold:true; font.pixelSize:14 }
                Rectangle { x:14; anchors.bottom:parent.bottom; width:78; height:2; color:appTheme.colors.accent }
                ActionButton { anchors.right:parent.right; anchors.rightMargin:12; text:"▷  Как использовать"; onClicked:nativeDialogs.showHelp() }
            }
            Rectangle {
                id: toolbar
                Layout.fillWidth:true; Layout.preferredHeight:40
                color:appTheme.colors.surface
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:appTheme.colors.border }
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:9; anchors.rightMargin:10; spacing:2
                    ActionButton { objectName:"undoButton"; text:"↶"; font.pixelSize:21; hint:"Отменить · Ctrl+Z"; enabled:controller.canUndo; onClicked:{window.contentItem.forceActiveFocus();controller.undo()} }
                    ActionButton { objectName:"redoButton"; text:"↷"; font.pixelSize:21; hint:"Повторить · Ctrl+Shift+Z"; enabled:controller.canRedo; onClicked:controller.redo() }
                    ActionButton { objectName:"bulkModeButton"; text:"☑"; font.pixelSize:18; hint:"Массовое изменение задач"; checked:controller.bulkMode; onClicked:{window.contentItem.forceActiveFocus();gantt.cancelInteractions();controller.setBulkMode(!controller.bulkMode)} }
                    Rectangle { width:1; height:20; color:appTheme.colors.border; Layout.leftMargin:7; Layout.rightMargin:7 }
                    ActionButton { objectName:"addTaskButton"; text:"＋"; font.pixelSize:21; hint:"Добавить задачу"; enabled:!controller.bulkMode; onClicked:controller.addTask(window.selectedParent(),"task") }
                    ActionButton { text:"◇"; font.pixelSize:20; hint:"Добавить веху"; enabled:!controller.bulkMode; onClicked:controller.addTask(window.selectedParent(),"milestone") }
                    ActionButton { text:"⊞"; font.pixelSize:18; hint:"Добавить группу"; enabled:!controller.bulkMode; onClicked:controller.addTask("","group") }
                    ActionButton { text:"⌃ Развернуть все"; visible:toolbar.width>1100; onClicked:controller.expandAll(true) }
                    ActionButton { text:"⌄ Свернуть все"; visible:toolbar.width>1100; onClicked:controller.expandAll(false) }
                    Item { Layout.fillWidth:true }
                    CellEditor {
                        id: search
                        objectName:"taskSearch"
                        Layout.preferredWidth:toolbar.width>1100?190:130
                        placeholderText:"Поиск по имени задачи"
                        onTextChanged:controller.search(text)
                        background:Rectangle { color:search.activeFocus?appTheme.colors.input:appTheme.colors.raised; radius:3; border.color:search.activeFocus?appTheme.colors.link:appTheme.colors.border }
                    }
                    ActionButton { text:"Поля"; objectName:"fieldsButton"; onClicked:window.showFields() }
                    ActionButton { text:"Фильтр"; objectName:"filterButton"; checked:window.filterCode!=="all"; onClicked:filterMenu.popup() }
                    Slider {
                        id: zoom
                        objectName:"zoomSlider"
                        Layout.preferredWidth:100
                        from:0; to:5; value:2; stepSize:1; snapMode:Slider.SnapAlways
                        Accessible.name:"Масштаб времени"
                    }
                    Text { text:["Дни","Дни","Недели","Месяцы","Кварталы","Годы"][Math.round(zoom.value)]; font.pixelSize:12; color:appTheme.colors.secondary; Layout.preferredWidth:58 }
                    ActionButton { objectName:"exportButton"; text:"Экспорт"; onClicked:window.showExport() }
                    ActionButton { text:"Вид ⌄"; onClicked:viewMenu.popup() }
                }
            }
            GanttView {
                id:gantt
                Layout.fillWidth:true; Layout.fillHeight:true
                pixelsPerDay:[52,26,10,4,2,1][Math.round(zoom.value)]
                activeLinkId:nativeDialogs.activeLinkId
                onInspectTask:function(id){window.inspectTask(id)}
                onTaskMenuRequested:function(id){window.showTaskMenu(id)}
                onFieldsRequested:window.showFields()
                onAssigneePickerRequested:function(id,anchor){window.showAssigneePicker(id,anchor)}
                onLinkEditRequested:function(id){const d=controller.linkDetails(id);window.showDependency(d.source,d.target,d.kind,id)}
                onZoomRequested:function(change){zoom.value=Math.max(0,Math.min(5,zoom.value+change))}
            }
            Rectangle {
                visible:window.workloadVisible
                Layout.fillWidth:true; Layout.preferredHeight:5
                color:appTheme.colors.border
                MouseArea {
                    objectName:"workloadSplitter"
                    anchors.fill:parent; cursorShape:Qt.SplitVCursor; preventStealing:true
                    property real downY:0
                    property real oldHeight:0
                    onPressed:function(mouse){downY=mapToItem(window.contentItem,mouse.x,mouse.y).y;oldHeight=window.workloadHeight}
                    onPositionChanged:function(mouse){if(pressed)window.workloadHeight=Math.max(130,Math.min(window.height*0.55,oldHeight-(mapToItem(window.contentItem,mouse.x,mouse.y).y-downY)))}
                }
            }
            ResourceWorkload {
                id:workloadView
                visible:window.workloadVisible
                Layout.fillWidth:true; Layout.preferredHeight:window.workloadHeight
                gridWidth:gantt.gridWidth; pixelsPerDay:gantt.pixelsPerDay; scrollX:gantt.scrollX; sceneWidth:gantt.sceneWidth
                onManageResource:function(id){window.showResources(id)}
                onInspectTask:function(id){window.inspectTask(id)}
                onCloseRequested:window.workloadVisible=false
                onHorizontalScroll:function(delta){gantt.scrollX+=delta;gantt.clampScroll()}
                onZoomRequested:function(change){zoom.value=Math.max(0,Math.min(5,zoom.value+change))}
            }
            Rectangle {
                Layout.fillWidth:true; Layout.preferredHeight:26
                color:appTheme.colors.raised
                Rectangle { width:parent.width; height:1; color:appTheme.colors.border }
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:14; anchors.rightMargin:14
                    ActionButton { objectName:"workloadToggle"; text:"Загрузка ресурсов"; implicitHeight:24; font.pixelSize:11; checked:window.workloadVisible; onClicked:window.workloadVisible=!window.workloadVisible }
                    ActionButton { objectName:"resourcesButton"; text:"Люди…"; implicitHeight:24; font.pixelSize:11; onClicked:window.showResources("") }
                    Text { text:controller.taskCount+" задач · "+controller.calendarLabel; font.pixelSize:11; color:appTheme.colors.muted }
                    Item { Layout.fillWidth:true }
                    Text { text:controller.selectedId?(controller.selected.start+" — "+controller.selected.end):"Двойной щелчок — свойства задачи"; font.pixelSize:11; color:appTheme.colors.muted }
                }
            }
        }
    }
    Rectangle {
        id:notice
        visible:false
        anchors.right:parent.right; anchors.top:parent.top
        anchors.margins:14
        width:Math.min(560,window.width-40); height:notification.implicitHeight+28
        color:appTheme.colors.raised; radius:5; border.color:appTheme.colors.border; z:100
        Rectangle { width:4; height:parent.height; color:appTheme.colors.accent; radius:2 }
        Text { id:notification; x:18; y:14; width:parent.width-34; wrapMode:Text.WordWrap; color:appTheme.colors.text; font.pixelSize:12 }
        Timer { id:toastTimer; interval:4500; onTriggered:notice.visible=false }
        MouseArea { anchors.fill:parent; onClicked:notice.visible=false }
    }
}
