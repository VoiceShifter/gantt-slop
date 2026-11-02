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
    readonly property string filterCode: controller.quickFilter
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
        nativeDialogs.showExport({columns:gantt.columns,pixelsPerDay:gantt.pixelsPerDay,workload:window.workloadVisible,critical:controller.criticalPath})
    }

    Connections {
        target: controller
        function onToast(message) { notification.text=message; notice.visible=true; toastTimer.restart() }
        function onInspectRequested() { inspector.open(); controller.focusTask(controller.selectedId) }
        function onProjectLoaded() { inspector.close(); search.text=""; gantt.scrollX=0; gantt.hiddenCustomFields=[] }
        function onFilterChanged() { search.text=controller.filterQuery }
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
        MenuItem { text: i18n.tr.menu_new_project; onTriggered: controller.newProject() }
        MenuItem { text: i18n.tr.menu_open; onTriggered: controller.openProject() }
        MenuItem { objectName:"importXmlMenuItem"; text: i18n.tr.menu_import_xml; onTriggered: controller.importXml() }
        MenuItem { objectName:"importCsvMenuItem"; text: i18n.tr.menu_import_csv; onTriggered: controller.importCsv() }
        MenuItem { objectName:"importXlsxMenuItem"; text: i18n.tr.menu_import_xlsx; onTriggered: controller.importXlsx() }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_save; onTriggered: window.saveProject() }
        MenuItem { text: i18n.tr.menu_save_as; onTriggered: controller.saveAs() }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_open_sample; onTriggered: controller.loadExample() }
        MenuSeparator {}
        MenuItem { objectName:"mcpMenuItem"; text: i18n.tr.menu_mcp; onTriggered:{gantt.cancelInteractions();nativeDialogs.showMcp()} }
    }
    Menu {
        id: taskMenu
        MenuItem { text: i18n.tr.menu_open_task; onTriggered: window.inspectTask(controller.selectedId) }
        MenuItem { text: i18n.tr.menu_show_on_chart; onTriggered: controller.focusTask(controller.selectedId) }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_add_task; onTriggered: controller.addTask(window.selectedParent(),"task") }
        MenuItem { text: i18n.tr.menu_add_milestone; onTriggered: controller.addTask(window.selectedParent(),"milestone") }
        MenuItem { text: i18n.tr.menu_add_subtask; enabled: controller.selected.summary || false; onTriggered: controller.addTask(controller.selectedId,"task") }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_move_up; onTriggered: controller.reorder(controller.selectedId,-1) }
        MenuItem { text: i18n.tr.menu_move_down; onTriggered: controller.reorder(controller.selectedId,1) }
        MenuItem { text: i18n.tr.menu_add_dependency; enabled: !!controller.selectedId; onTriggered: window.showDependency("",controller.selectedId,"FS","") }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_delete; onTriggered: window.askDelete(controller.selectedId) }
    }
    Menu {
        id: filterMenu
        MenuItem { objectName:"advancedFiltersMenuItem"; text: i18n.tr.menu_advanced_filters; onTriggered:{gantt.cancelInteractions();nativeDialogs.showFilters()} }
        MenuSeparator {}
        MenuItem { text: i18n.tr.menu_no_quick_filter; checkable:true; checked:window.filterCode==="all"; onTriggered:controller.setFilter("all") }
        MenuItem { text: i18n.tr.menu_incomplete; checkable:true; checked:window.filterCode==="incomplete"; onTriggered:controller.setFilter("incomplete") }
        MenuItem { text: i18n.tr.menu_complete; checkable:true; checked:window.filterCode==="complete"; onTriggered:controller.setFilter("complete") }
        MenuItem { text: i18n.tr.menu_overdue; checkable:true; checked:window.filterCode==="overdue"; onTriggered:controller.setFilter("overdue") }
        MenuSeparator {}
        MenuItem { objectName:"clearFiltersMenuItem"; text: i18n.tr.menu_clear_filters; enabled:controller.filterActive; onTriggered:controller.clearFilters() }
    }
    Menu {
        id: viewMenu
        MenuItem { text: i18n.tr.menu_to_start; onTriggered:gantt.centerDay(7) }
        MenuItem { text: i18n.tr.menu_to_task; enabled:!!controller.selectedId; onTriggered:controller.focusTask(controller.selectedId) }
        MenuSeparator {}
        MenuItem { text: window.sidebarVisible ? i18n.tr.menu_hide_sidebar : i18n.tr.menu_show_sidebar; onTriggered:window.sidebarVisible=!window.sidebarVisible }
        MenuItem { text: i18n.tr.menu_reset_columns; onTriggered:gantt.resetColumnWidths() }
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
                    ActionButton { text:"⇤"; hint:i18n.tr.hide_project_panel; onClicked:window.sidebarVisible=false }
                }
                Label { text:i18n.tr.local_projects; font.bold:true; font.pixelSize:15; color:appTheme.colors.text }
                ActionButton { text:i18n.tr.new_project_btn; primary:true; Layout.fillWidth:true; implicitHeight:33; onClicked:controller.newProject() }
                Rectangle {
                    Layout.fillWidth:true; height:32; color:appTheme.colors.selection; radius:3
                    Label { x:14; anchors.verticalCenter:parent.verticalCenter; text:i18n.tr.current_project; color:appTheme.colors.text; font.bold:true }
                    MouseArea { anchors.fill:parent; onClicked:{inspector.close();gantt.centerDay(7)} }
                }
                ActionButton { text:i18n.tr.open_project_btn; Layout.fillWidth:true; onClicked:controller.openProject() }
                ActionButton { text:i18n.tr.save_project_btn; Layout.fillWidth:true; onClicked:window.saveProject() }
                ActionButton { text:i18n.tr.sample_project_btn; Layout.fillWidth:true; onClicked:controller.loadExample() }
                Item { Layout.fillHeight:true }
                Rectangle {
                    Layout.fillWidth:true; height:88; color:appTheme.colors.panel; radius:4
                    Column {
                        x:14; y:15; width:parent.width-28; spacing:9
                        Text { text:controller.fileName; width:parent.width; elide:Text.ElideMiddle; color:appTheme.colors.secondary; font.pixelSize:12 }
                        Text { text:controller.dirty?i18n.tr.unsaved_changes:i18n.tr.changes_saved; color:controller.dirty?appTheme.colors.warning:appTheme.colors.muted; font.pixelSize:11 }
                        Text { text:i18n.tr.local_file_no_account; color:appTheme.colors.muted; font.pixelSize:11 }
                    }
                }
                ActionButton { objectName:"helpButton"; text:i18n.tr.help_btn; onClicked:nativeDialogs.showHelp() }
            }
        }
        ColumnLayout {
            Layout.fillWidth:true; Layout.fillHeight:true
            spacing:0
            Item {
                Layout.fillWidth:true; Layout.preferredHeight:44
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:12; anchors.rightMargin:14; spacing:10
                    ActionButton { text:"⇥"; visible:!window.sidebarVisible; hint:i18n.tr.show_project_panel; onClicked:window.sidebarVisible=true }
                    ActionButton { text:i18n.tr.file_menu_btn; onClicked:fileMenu.popup() }
                    CellEditor { text:controller.projectName; font.bold:true; font.pixelSize:15; Layout.preferredWidth:280; onEditingFinished:if(text!==controller.projectName)controller.renameProject(text) }
                    ActionButton { objectName:"baselinesButton"; text:window.width>=1200?i18n.tr.baselines_btn:"▱"; hint:i18n.tr.baselines_hint; checked:!!controller.baselineName; onClicked:{window.contentItem.forceActiveFocus();gantt.cancelInteractions();nativeDialogs.showBaselines()} }
                    Item { Layout.fillWidth:true }
                    Text { visible:window.width>=1200; text:i18n.tr.local_project; color:appTheme.colors.muted; font.pixelSize:12 }
                    ActionButton { objectName:"settingsButton"; text:i18n.tr.settings_btn; hint:i18n.tr.settings_hint; onClicked:{gantt.cancelInteractions();settings.open()} }
                    ActionButton { text:i18n.tr.save_btn; hint:i18n.tr.save_hint; onClicked:window.saveProject() }
                }
            }
            Item {
                Layout.fillWidth:true; Layout.preferredHeight:30
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:appTheme.colors.border }
                Text { x:14; y:4; text:i18n.tr.chart_tab; color:appTheme.colors.link; font.bold:true; font.pixelSize:14 }
                Rectangle { x:14; anchors.bottom:parent.bottom; width:78; height:2; color:appTheme.colors.accent }
                ActionButton { anchors.right:parent.right; anchors.rightMargin:12; text:i18n.tr.how_to_use; onClicked:nativeDialogs.showHelp() }
            }
            Rectangle {
                id: toolbar
                Layout.fillWidth:true; Layout.preferredHeight:40
                color:appTheme.colors.surface
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:appTheme.colors.border }
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:9; anchors.rightMargin:10; spacing:2
                    ActionButton { objectName:"undoButton"; text:"↶"; font.pixelSize:21; hint:i18n.tr.undo_hint; enabled:controller.canUndo; onClicked:{window.contentItem.forceActiveFocus();controller.undo()} }
                    ActionButton { objectName:"redoButton"; text:"↷"; font.pixelSize:21; hint:i18n.tr.redo_hint; enabled:controller.canRedo; onClicked:controller.redo() }
                    ActionButton { objectName:"bulkModeButton"; text:"☑"; font.pixelSize:18; hint:i18n.tr.bulk_hint; checked:controller.bulkMode; onClicked:{window.contentItem.forceActiveFocus();gantt.cancelInteractions();controller.setBulkMode(!controller.bulkMode)} }
                    Rectangle { width:1; height:20; color:appTheme.colors.border; Layout.leftMargin:7; Layout.rightMargin:7 }
                    ActionButton { objectName:"addTaskButton"; text:"＋"; font.pixelSize:21; hint:i18n.tr.add_task_hint; enabled:!controller.bulkMode; onClicked:controller.addTask(window.selectedParent(),"task") }
                    ActionButton { text:"◇"; font.pixelSize:20; hint:i18n.tr.add_milestone_hint; enabled:!controller.bulkMode; onClicked:controller.addTask(window.selectedParent(),"milestone") }
                    ActionButton { text:"⊞"; font.pixelSize:18; hint:i18n.tr.add_group_hint; enabled:!controller.bulkMode; onClicked:controller.addTask("","group") }
                    ActionButton { objectName:"criticalPathButton"; text:"⌁"; font.pixelSize:21; hint:i18n.tr.critical_path_hint; checked:controller.criticalPath; onClicked:{window.contentItem.forceActiveFocus();gantt.cancelInteractions();controller.setCriticalPath(!controller.criticalPath)} }
                    ActionButton { text:i18n.tr.expand_all; visible:toolbar.width>1100; onClicked:controller.expandAll(true) }
                    ActionButton { text:i18n.tr.collapse_all; visible:toolbar.width>1100; onClicked:controller.expandAll(false) }
                    Item { Layout.fillWidth:true }
                    CellEditor {
                        id: search
                        objectName:"taskSearch"
                        Layout.preferredWidth:toolbar.width>1100?190:toolbar.width>900?130:100
                        placeholderText:i18n.tr.search_placeholder
                        onTextChanged:controller.search(text)
                        background:Rectangle { color:search.activeFocus?appTheme.colors.input:appTheme.colors.raised; radius:3; border.color:search.activeFocus?appTheme.colors.link:appTheme.colors.border }
                    }
                    ActionButton { text:i18n.tr.fields_btn; objectName:"fieldsButton"; onClicked:window.showFields() }
                    ActionButton { text:i18n.tr.filter_btn; objectName:"filterButton"; checked:controller.filterActive; onClicked:filterMenu.popup() }
                    Slider {
                        id: zoom
                        objectName:"zoomSlider"
                        Layout.preferredWidth:100
                        from:0; to:5; value:2; stepSize:1; snapMode:Slider.SnapAlways
                        Accessible.name:i18n.tr.time_scale
                    }
                    Text { text:[i18n.tr.scale_days, i18n.tr.scale_days, i18n.tr.scale_weeks, i18n.tr.scale_months, i18n.tr.scale_quarters, i18n.tr.scale_years][Math.round(zoom.value)]; font.pixelSize:12; color:appTheme.colors.secondary; Layout.preferredWidth:58 }
                    ActionButton { objectName:"exportButton"; text:i18n.tr.export_btn; onClicked:window.showExport() }
                    ActionButton { text:i18n.tr.view_menu_btn; onClicked:viewMenu.popup() }
                }
            }
            Rectangle {
                visible: controller.criticalPath
                Layout.fillWidth: true; Layout.preferredHeight: criticalInfo.implicitHeight + 14
                color: appTheme.colors.panel
                Rectangle { width: 3; height: parent.height; color: controller.criticalPathError ? appTheme.colors.warning : "#c93b3b" }
                Label {
                    id: criticalInfo
                    objectName: "criticalPathInfo"
                    x: 14; y: 7; width: parent.width-28
                    text: controller.criticalPathInfo; textFormat: Text.PlainText
                    wrapMode: Text.WordWrap; font.pixelSize: 11
                    color: controller.criticalPathError ? appTheme.colors.danger : appTheme.colors.text
                }
            }
            Rectangle {
                visible: !!controller.baselineName
                Layout.fillWidth: true; Layout.preferredHeight: baselineInfo.implicitHeight + 14
                color: appTheme.colors.panel
                Rectangle { width: 3; height: parent.height; color: appTheme.colors.secondary }
                Label {
                    id: baselineInfo
                    objectName: "baselineInfo"
                    x: 14; y: 7; width: parent.width-28
                    text: controller.baselineInfo; textFormat: Text.PlainText
                    wrapMode: Text.WrapAnywhere; font.pixelSize: 11; color: appTheme.colors.secondary
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
                    ActionButton { objectName:"workloadToggle"; text:i18n.tr.workload_toggle; implicitHeight:24; font.pixelSize:11; checked:window.workloadVisible; onClicked:window.workloadVisible=!window.workloadVisible }
                    ActionButton { objectName:"resourcesButton"; text:i18n.tr.people_btn; implicitHeight:24; font.pixelSize:11; onClicked:window.showResources("") }
                    Text { text:controller.taskCount + " " + i18n.tr.tasks_count_suffix + " · " + controller.calendarLabel; font.pixelSize:11; color:appTheme.colors.muted }
                    Item { Layout.fillWidth:true }
                    ActionButton { objectName:"mcpIndicator"; visible:!!nativeDialogs.mcpStatus; text:nativeDialogs.mcpStatus; implicitHeight:24; font.pixelSize:11; checked:true; onClicked:{gantt.cancelInteractions();nativeDialogs.showMcp()} }
                    Text { text:controller.selectedId?(controller.selected.start+" — "+controller.selected.end):i18n.tr.double_click_hint; font.pixelSize:11; color:appTheme.colors.muted }
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
