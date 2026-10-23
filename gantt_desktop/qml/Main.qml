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
    color: "white"
    font.family: "Arial"
    font.pixelSize: 13
    property bool allowClose: false
    property bool sidebarVisible: true
    property string filterCode: "all"
    property string deleteId: ""
    readonly property bool editingText: activeFocusItem && activeFocusItem.cursorPosition !== undefined
    onClosing: function(event) { if (!allowClose) event.accepted = controller.confirmClose() }

    function inspectTask(id) { controller.select(id); inspector.open() }
    function selectedParent() { return controller.selected.summary ? controller.selectedId : (controller.selected.parentId || "") }
    function showTaskMenu(id) { controller.select(id); taskMenu.popup() }
    function askDelete(id) { if (!id) return; deleteId=id; deleteDialog.open() }
    function showDependency(source,target,kind,id) {
        const detail = id ? controller.linkDetails(id) : ({})
        dependency.linkId=id; dependency.sourceId=source; dependency.targetId=target
        dependency.relation=kind; dependency.lagHours=String(detail.lag || 0)
        dependency.open()
    }
    function saveProject() { contentItem.forceActiveFocus(); controller.save() }

    Connections {
        target: controller
        function onToast(message) { notification.text=message; notice.visible=true; toastTimer.restart() }
        function onInspectRequested() { inspector.open(); controller.focusTask(controller.selectedId) }
        function onProjectLoaded() { inspector.close(); search.text=""; window.filterCode="all"; gantt.scrollX=0 }
    }
    Shortcut { sequences: [StandardKey.Save]; onActivated: window.saveProject() }
    Shortcut { sequence: "Ctrl+Shift+S"; onActivated: controller.saveAs() }
    Shortcut { sequences: [StandardKey.Open]; onActivated: controller.openProject() }
    Shortcut { sequences: [StandardKey.New]; onActivated: controller.newProject() }
    Shortcut { sequences: [StandardKey.Undo]; enabled: !window.editingText; onActivated: controller.undo() }
    Shortcut { sequences: [StandardKey.Redo]; enabled: !window.editingText; onActivated: controller.redo() }
    Shortcut { sequence: "Delete"; enabled: !window.editingText && !!controller.selectedId; onActivated: window.askDelete(controller.selectedId) }
    Shortcut { sequence: "Escape"; onActivated: { gantt.cancelInteractions(); if (inspector.opened) inspector.close(); contentItem.forceActiveFocus() } }
    Shortcut { sequence: "Return"; enabled: !window.editingText && !!controller.selectedId && !inspector.opened; onActivated: window.inspectTask(controller.selectedId) }
    Shortcut { sequence: "Ctrl+F"; onActivated: { search.forceActiveFocus(); search.selectAll() } }

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
        MenuItem { text: "Добавить зависимость"; enabled: !controller.selected.summary; onTriggered: window.showDependency("",controller.selectedId,"FS","") }
        MenuSeparator {}
        MenuItem { text: "Удалить"; onTriggered: window.askDelete(controller.selectedId) }
    }
    Menu {
        id: fieldsMenu
        title: "Показать/скрыть поля"
        MenuItem { text: "Исполнитель"; checkable:true; checked:gantt.showAssignee; onTriggered:gantt.showAssignee=checked }
        MenuItem { text: "Трудозатраты"; checkable:true; checked:gantt.showEffort; onTriggered:gantt.showEffort=checked }
        MenuItem { text: "Стоимость"; checkable:true; checked:gantt.showCost; onTriggered:gantt.showCost=checked }
        MenuSeparator {}
        MenuItem { text: "Начало"; checkable:true; checked:gantt.showStart; onTriggered:gantt.showStart=checked }
        MenuItem { text: "Завершение"; checkable:true; checked:gantt.showEnd; onTriggered:gantt.showEnd=checked }
        MenuItem { text: "Длительность"; checkable:true; checked:gantt.showDuration; onTriggered:gantt.showDuration=checked }
        MenuItem { text: "Прогресс"; checkable:true; checked:gantt.showProgress; onTriggered:gantt.showProgress=checked }
    }
    Menu {
        id: filterMenu
        MenuItem { text:"Все задачи"; checkable:true; checked:window.filterCode==="all"; onTriggered:{window.filterCode="all";controller.setFilter("all")} }
        MenuItem { text:"Незавершённые"; checkable:true; checked:window.filterCode==="incomplete"; onTriggered:{window.filterCode="incomplete";controller.setFilter("incomplete")} }
        MenuItem { text:"Завершённые"; checkable:true; checked:window.filterCode==="complete"; onTriggered:{window.filterCode="complete";controller.setFilter("complete")} }
        MenuItem { text:"Просроченные"; checkable:true; checked:window.filterCode==="overdue"; onTriggered:{window.filterCode="overdue";controller.setFilter("overdue")} }
    }
    Menu {
        id: exportMenu
        MenuItem { text:"Текущий вид в PNG…"; onTriggered:controller.exportPng() }
        MenuItem { text:"Таблица задач в CSV…"; onTriggered:controller.exportCsv() }
    }
    Menu {
        id: viewMenu
        MenuItem { text:"К началу проекта"; onTriggered:gantt.centerDay(7) }
        MenuItem { text:"К выбранной задаче"; enabled:!!controller.selectedId; onTriggered:controller.focusTask(controller.selectedId) }
        MenuSeparator {}
        MenuItem { text:window.sidebarVisible?"Скрыть боковую панель":"Показать боковую панель"; onTriggered:window.sidebarVisible=!window.sidebarVisible }
        MenuItem { text:"Сбросить ширину таблицы"; onTriggered:gantt.gridWidth=Math.min(716,Math.max(450,gantt.width*0.48)) }
    }
    Dialog {
        id: deleteDialog
        anchors.centerIn: parent
        title: "Удалить задачу?"
        modal: true
        standardButtons: Dialog.Ok | Dialog.Cancel
        Label { text:"Задача, её подзадачи и связанные зависимости будут удалены.\nДействие можно отменить через Undo."; wrapMode:Text.WordWrap }
        onAccepted:controller.deleteTask(window.deleteId)
    }
    Dialog {
        id: help
        anchors.centerIn: parent
        title: "Работа с диаграммой"
        modal: true
        standardButtons: Dialog.Close
        width: Math.min(660,window.width-80)
        Label {
            width:parent.width
            wrapMode:Text.WordWrap
            lineHeight:1.5
            text:"• Перетаскивайте свободную задачу или группу за тело блока.\n• Задача с предшественником закреплена: измените связь или лаг.\n• Тяните края задачи для изменения начала или завершения.\n• Круги по бокам создают связи: перетащите круг на другую задачу.\n• Маленький ромб под блоком меняет прогресс.\n• Двойной щелчок открывает свойства; название редактируется в таблице.\n• Пустую область диаграммы можно перетаскивать.\n• Ctrl+колесо — масштаб; Shift+колесо — горизонтальная прокрутка.\n• Ctrl+Z / Ctrl+Shift+Z — отмена и повтор; Ctrl+S — сохранить.\n\nКалендарь: Пн–Пт, 09:00–13:00 и 14:00–18:00.\nДлительность и трудозатраты — разные величины."
        }
    }
    DependencyDialog { id: dependency; parent: Overlay.overlay }
    TaskInspector {
        id: inspector
        parent: Overlay.overlay
        onDependencyRequested: function(source,target,kind,id) { window.showDependency(source,target,kind,id) }
        onDeleteRequested: function(id) { window.askDelete(id) }
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
            color: "white"
            Rectangle { anchors.right:parent.right; width:1; height:parent.height; color:"#eeeeee" }
            ColumnLayout {
                anchors.fill:parent
                anchors.margins:12
                spacing:14
                RowLayout {
                    Layout.fillWidth:true
                    Label { text:"GANTT DESKTOP"; color:"#00564f"; font.bold:true; font.pixelSize:21 }
                    Item { Layout.fillWidth:true }
                    ActionButton { text:"⇤"; hint:"Скрыть панель проектов"; onClicked:window.sidebarVisible=false }
                }
                Label { text:"Локальные проекты"; font.bold:true; font.pixelSize:15; color:"#292929" }
                ActionButton { text:"＋  Создать новый проект"; primary:true; Layout.fillWidth:true; implicitHeight:33; onClicked:controller.newProject() }
                Rectangle {
                    Layout.fillWidth:true; height:32; color:"#e8eff6"; radius:3
                    Label { x:14; anchors.verticalCenter:parent.verticalCenter; text:"□   Текущий проект"; color:"#252f37"; font.bold:true }
                    MouseArea { anchors.fill:parent; onClicked:{inspector.close();gantt.centerDay(7)} }
                }
                ActionButton { text:"Открыть проект…"; Layout.fillWidth:true; onClicked:controller.openProject() }
                ActionButton { text:"Сохранить проект"; Layout.fillWidth:true; onClicked:window.saveProject() }
                ActionButton { text:"Демонстрационный проект"; Layout.fillWidth:true; onClicked:controller.loadExample() }
                Item { Layout.fillHeight:true }
                Rectangle {
                    Layout.fillWidth:true; height:88; color:"#f8f9fa"; radius:4
                    Column {
                        x:14; y:15; width:parent.width-28; spacing:9
                        Text { text:controller.fileName; width:parent.width; elide:Text.ElideMiddle; color:"#44505b"; font.pixelSize:12 }
                        Text { text:controller.dirty?"Есть несохранённые изменения":"Изменения сохранены"; color:controller.dirty?"#a57a20":"#7d8b95"; font.pixelSize:11 }
                        Text { text:"Локальный файл · Без аккаунта"; color:"#9aa1a7"; font.pixelSize:11 }
                    }
                }
                ActionButton { text:"?  Помощь"; onClicked:help.open() }
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
                    Text { text:"Локальный проект"; color:"#7b858e"; font.pixelSize:12 }
                    ActionButton { text:"Сохранить"; hint:"Сохранить · Ctrl+S"; onClicked:window.saveProject() }
                }
            }
            Item {
                Layout.fillWidth:true; Layout.preferredHeight:30
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:"#eeeeee" }
                Text { x:14; y:4; text:"Диаграмма"; color:"#176dce"; font.bold:true; font.pixelSize:14 }
                Rectangle { x:14; anchors.bottom:parent.bottom; width:78; height:2; color:"#246dc2" }
                ActionButton { anchors.right:parent.right; anchors.rightMargin:12; text:"▷  Как использовать"; onClicked:help.open() }
            }
            Rectangle {
                id: toolbar
                Layout.fillWidth:true; Layout.preferredHeight:40
                color:"white"
                Rectangle { anchors.bottom:parent.bottom; width:parent.width; height:1; color:"#e5e5e5" }
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:9; anchors.rightMargin:10; spacing:2
                    ActionButton { objectName:"undoButton"; text:"↶"; font.pixelSize:21; hint:"Отменить · Ctrl+Z"; enabled:controller.canUndo; onClicked:{window.contentItem.forceActiveFocus();controller.undo()} }
                    ActionButton { objectName:"redoButton"; text:"↷"; font.pixelSize:21; hint:"Повторить · Ctrl+Shift+Z"; enabled:controller.canRedo; onClicked:controller.redo() }
                    Rectangle { width:1; height:20; color:"#e3e3e3"; Layout.leftMargin:7; Layout.rightMargin:7 }
                    ActionButton { objectName:"addTaskButton"; text:"＋"; font.pixelSize:21; hint:"Добавить задачу"; onClicked:controller.addTask(window.selectedParent(),"task") }
                    ActionButton { text:"◇"; font.pixelSize:20; hint:"Добавить веху"; onClicked:controller.addTask(window.selectedParent(),"milestone") }
                    ActionButton { text:"⊞"; font.pixelSize:18; hint:"Добавить группу"; onClicked:controller.addTask("","group") }
                    ActionButton { text:"⌃ Развернуть все"; visible:toolbar.width>1100; onClicked:controller.expandAll(true) }
                    ActionButton { text:"⌄ Свернуть все"; visible:toolbar.width>1100; onClicked:controller.expandAll(false) }
                    Item { Layout.fillWidth:true }
                    CellEditor {
                        id: search
                        objectName:"taskSearch"
                        Layout.preferredWidth:toolbar.width>1100?190:130
                        placeholderText:"Поиск по имени задачи"
                        onTextChanged:controller.search(text)
                        background:Rectangle { color:search.activeFocus?"white":"#fafbfc"; radius:3; border.color:search.activeFocus?"#2482e8":"#ebedf0" }
                    }
                    ActionButton { text:"Поля"; objectName:"fieldsButton"; onClicked:fieldsMenu.popup() }
                    ActionButton { text:"Фильтр"; objectName:"filterButton"; checked:window.filterCode!=="all"; onClicked:filterMenu.popup() }
                    Slider {
                        id: zoom
                        objectName:"zoomSlider"
                        Layout.preferredWidth:100
                        from:0; to:5; value:2; stepSize:1; snapMode:Slider.SnapAlways
                        Accessible.name:"Масштаб времени"
                    }
                    Text { text:["Дни","Дни","Недели","Месяцы","Кварталы","Годы"][Math.round(zoom.value)]; font.pixelSize:12; color:"#777777"; Layout.preferredWidth:58 }
                    ActionButton { text:"Экспорт"; onClicked:exportMenu.popup() }
                    ActionButton { text:"Вид ⌄"; onClicked:viewMenu.popup() }
                }
            }
            GanttView {
                id:gantt
                Layout.fillWidth:true; Layout.fillHeight:true
                pixelsPerDay:[52,26,10,4,2,1][Math.round(zoom.value)]
                onInspectTask:function(id){window.inspectTask(id)}
                onTaskMenuRequested:function(id){window.showTaskMenu(id)}
                onLinkEditRequested:function(id){const d=controller.linkDetails(id);window.showDependency(d.source,d.target,d.kind,id)}
                onZoomRequested:function(change){zoom.value=Math.max(0,Math.min(5,zoom.value+change))}
            }
            Rectangle {
                Layout.fillWidth:true; Layout.preferredHeight:26
                color:"#fafbfc"
                Rectangle { width:parent.width; height:1; color:"#e9ebee" }
                RowLayout {
                    anchors.fill:parent; anchors.leftMargin:14; anchors.rightMargin:14
                    Text { text:controller.taskCount+" задач · Пн–Пт · 8ч/день"; font.pixelSize:11; color:"#83909b" }
                    Item { Layout.fillWidth:true }
                    Text { text:controller.selectedId?(controller.selected.start+" — "+controller.selected.end):"Двойной щелчок — свойства задачи"; font.pixelSize:11; color:"#83909b" }
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
        color:"white"; radius:5; border.color:"#dfe5ed"; z:100
        Rectangle { width:4; height:parent.height; color:"#2479d7"; radius:2 }
        Text { id:notification; x:18; y:14; width:parent.width-34; wrapMode:Text.WordWrap; color:"#35414b"; font.pixelSize:12 }
        Timer { id:toastTimer; interval:4500; onTriggered:notice.visible=false }
        MouseArea { anchors.fill:parent; onClicked:notice.visible=false }
    }
}
