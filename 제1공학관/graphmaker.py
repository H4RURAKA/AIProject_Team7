import sys
import os
import json
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPixmapItem, QGraphicsTextItem,
    QGraphicsItem, QAction, QToolBar, QDockWidget, QWidget, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QInputDialog, QStatusBar
)
from PyQt5.QtGui import QBrush, QColor, QPen, QPixmap, QPainter
from PyQt5.QtCore import Qt, QPointF, QRectF

# Custom view class to support Ctrl + wheel zoom
class ZoomableGraphicsView(QGraphicsView):
    def __init__(self, *args):
        super().__init__(*args)
        self.setRenderHint(QPainter.Antialiasing)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.scale_factor = 1.0
        self.status_bar = None

    def wheelEvent(self, event):
        if event.modifiers() == Qt.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
            self.scale_factor *= factor
            # 안전하게 statusBar 접근
            if hasattr(self.parent(), 'statusBar'):
                bar = self.parent().statusBar()
                if bar:
                    bar.showMessage(f"Zoom: {self.scale_factor * 100:.1f}%")
        else:
            super().wheelEvent(event)


class EdgeItem(QGraphicsLineItem):
    def __init__(self, src, dst, scale_factor, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.src = src
        self.dst = dst
        self.scale_factor = scale_factor
        self.setPen(QPen(QColor('#555555'), 2))
        self.selected = False
        self.update_position()

    def update_position(self):
        p1 = self.src.pos()
        p2 = self.dst.pos()
        self.setLine(p1.x(), p1.y(), p2.x(), p2.y())
        self.weight = math.hypot(p2.x() - p1.x(), p2.y() - p1.y()) * self.scale_factor

    def set_scale(self, scale):
        self.scale_factor = scale
        self.update_position()

    def toggle_selection(self):
        self.selected = not self.selected
        pen = self.pen()
        pen.setColor(QColor('#FF0000') if self.selected else QColor('#555555'))
        self.setPen(pen)

class NodeItem(QGraphicsEllipseItem):
    RADIUS = 15
    def __init__(self, node_id, name, ntype, color, *args, **kwargs):
        super().__init__(-self.RADIUS, -self.RADIUS, 2*self.RADIUS, 2*self.RADIUS, *args, **kwargs)
        self.node_id = node_id
        self.name = name
        self.ntype = ntype
        self.color = color
        self.setBrush(QBrush(QColor(color)))
        self.setFlags(
            QGraphicsEllipseItem.ItemIsSelectable |
            QGraphicsEllipseItem.ItemSendsGeometryChanges |
            QGraphicsEllipseItem.ItemIsMovable
        )
        self.text = QGraphicsTextItem(name, self)
        self.text.setDefaultTextColor(Qt.black)
        self.text.setPos(-self.RADIUS, -self.RADIUS - 20)
        self.edges = []

    def set_name(self, new_name):
        self.name = new_name
        self.text.setPlainText(new_name)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            for edge in list(self.edges):
                edge.update_position()
        return super().itemChange(change, value)

class GraphEditor(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Graph Editor')
        self.scale_factor = 1.0
        self.node_types = {
            'Room': '#FF9999',
            'Corridor': '#99FF99',
            'Restroom': '#9999FF',
            'Stair': '#FFFF99',
            'Elevator': '#FF99FF',
            'Door': '#FFCC00'
        }
        self.nodes = {}
        self.edges = []
        self.next_id = 1
        self.mode = None
        self.temp_edge = []

        self._init_ui()

    def _init_ui(self):
        self.scene = QGraphicsScene(self)
        self.view = ZoomableGraphicsView(self.scene)
        self.view.status_bar = self.statusBar()  # 연결
        self.setCentralWidget(self.view)

        self.bg_item = None

        tb = QToolBar('Tools', self)
        self.addToolBar(tb)
        for action_name in ['New', 'Load', 'Save']:
            act = QAction(action_name, self)
            if action_name == 'New':
                act.triggered.connect(self.new_background)
            elif action_name == 'Load':
                act.triggered.connect(self.load_json)
            else:
                act.triggered.connect(self.save_json)
            tb.addAction(act)
        tb.addSeparator()
        self.mode_actions = {}
        for name in ['Node Add', 'Node Edit', 'Node Delete', 'Edge Add', 'Edge Delete', 'Calibrate Scale']:
            act = QAction(name, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, n=name: self.set_mode(n))
            tb.addAction(act)
            self.mode_actions[name] = act

        self.apply_scale_btn = QAction('Apply Scale', self)
        self.apply_scale_btn.triggered.connect(self.apply_scale)
        tb.addAction(self.apply_scale_btn)

        self.prop_dock = QDockWidget('Properties', self)
        props = QWidget()
        layout = QFormLayout(props)
        self.prop_name = QLineEdit()
        self.prop_name.textChanged.connect(self.on_name_change)
        self.prop_type = QComboBox()
        self.prop_type.currentTextChanged.connect(self.on_type_change)
        for t in self.node_types:
            self.prop_type.addItem(t)
        btn_add_type = QPushButton('Add Type')
        btn_add_type.clicked.connect(self.add_node_type)
        layout.addRow('Name', self.prop_name)
        layout.addRow('Type', self.prop_type)
        layout.addRow('', btn_add_type)
        self.prop_dock.setWidget(props)
        self.addDockWidget(Qt.RightDockWidgetArea, self.prop_dock)
        self.prop_dock.hide()

        self.scene.mousePressEvent = self.on_mouse_press
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Zoom: 100.0%")

    def set_mode(self, mode_name):
        for name, act in self.mode_actions.items():
            act.setChecked(name == mode_name)
        self.mode = mode_name
        self.prop_dock.setVisible(mode_name in ['Node Add', 'Node Edit'])
        if mode_name == 'Node Edit':
            items = self.scene.selectedItems()
            if items and isinstance(items[0], NodeItem):
                node = items[0]
                self.prop_name.setText(node.name)
                self.prop_type.setCurrentText(node.ntype)
        for node in self.nodes.values():
            node.setFlag(QGraphicsEllipseItem.ItemIsMovable, mode_name == 'Node Edit')

    def new_background(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select Background Image', '', 'Images (*.png *.jpg *.bmp)')
        if not path:
            return
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.next_id = 1
        pix = QPixmap(path)
        self.bg_item = QGraphicsPixmapItem(pix)
        self.bg_item.filePath = path
        self.bg_item.setZValue(-1)
        self.scene.addItem(self.bg_item)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Graph JSON', '', 'JSON Files (*.json)')
        if not path:
            return
        with open(path, 'r') as f:
            data = json.load(f)
        self.scale_factor = data.get('scale', 1.0)
        bg = data.get('background', '')
        self.scene.clear()
        if os.path.exists(bg):
            pix = QPixmap(bg)
            self.bg_item = QGraphicsPixmapItem(pix)
            self.bg_item.filePath = bg
            self.bg_item.setZValue(-1)
            self.scene.addItem(self.bg_item)
        self.nodes.clear()
        self.edges.clear()
        self.next_id = 1
        for nd in data.get('nodes', []):
            node = NodeItem(nd['id'], nd['name'], nd['type'], self.node_types.get(nd['type'], '#CCCCCC'))
            node.setPos(nd['x'], nd['y'])
            self.scene.addItem(node)
            self.nodes[nd['id']] = node
            self.next_id = max(self.next_id, nd['id'] + 1)
        for ed in data.get('edges', []):
            src = self.nodes.get(ed['source'])
            dst = self.nodes.get(ed['target'])
            if src and dst:
                edge = EdgeItem(src, dst, self.scale_factor)
                self.scene.addItem(edge)
                src.edges.append(edge)
                dst.edges.append(edge)
                self.edges.append(edge)

    def save_json(self):
        path, _ = QFileDialog.getSaveFileName(self, 'Save Graph JSON', '', 'JSON Files (*.json)')
        if not path:
            return
        data = {
            'background': getattr(self.bg_item, 'filePath', ''),
            'scale': self.scale_factor,
            'nodes': [],
            'edges': []
        }
        for nid, node in self.nodes.items():
            p = node.pos()
            data['nodes'].append({
                'id': nid,
                'name': node.name,
                'type': node.ntype,
                'x': p.x(),
                'y': p.y()
            })
        for e in self.edges:
            data['edges'].append({
                'source': e.src.node_id,
                'target': e.dst.node_id,
                'weight': e.weight
            })
        with open(path, 'w') as f:
            json.dump(data, f, indent=4)

    def add_node_type(self):
        text, ok = QInputDialog.getText(self, 'New Node Type', 'Type name and hex color (e.g. Office,#FFAACC):')
        if ok and ',' in text:
            name, color = text.split(',', 1)
            self.node_types[name] = color.strip()
            self.prop_type.addItem(name)

    def on_name_change(self, text):
        if self.mode == 'Node Edit':
            items = self.scene.selectedItems()
            if items and isinstance(items[0], NodeItem):
                items[0].set_name(text)

    def on_type_change(self, typ):
        if self.mode == 'Node Edit':
            items = self.scene.selectedItems()
            if items and isinstance(items[0], NodeItem):
                node = items[0]
                node.ntype = typ
                node.setBrush(QBrush(QColor(self.node_types.get(typ, '#CCCCCC'))))

    def on_mouse_press(self, event):
        pos = event.scenePos()
        if self.mode == 'Node Edit':
            QGraphicsScene.mousePressEvent(self.scene, event)
            return
        if self.mode == 'Node Add':
            name = self.prop_name.text() or f"Node{self.next_id}"
            ntype = self.prop_type.currentText()
            color = self.node_types.get(ntype, '#CCCCCC')
            node = NodeItem(self.next_id, name, ntype, color)
            node.setPos(pos)
            self.scene.addItem(node)
            self.nodes[self.next_id] = node
            self.next_id += 1
            return
        if self.mode == 'Node Delete':
            for it in self.scene.items(QRectF(pos.x()-5, pos.y()-5, 10, 10)):
                if isinstance(it, NodeItem):
                    for e in list(it.edges):
                        self.scene.removeItem(e)
                        self.edges.remove(e)
                        e.src.edges.remove(e)
                        e.dst.edges.remove(e)
                    self.scene.removeItem(it)
                    del self.nodes[it.node_id]
                    break
            return
        if self.mode == 'Edge Add':
            hits = [i for i in self.scene.items(QRectF(pos.x()-5, pos.y()-5, 10, 10)) if isinstance(i, NodeItem)]
            if hits:
                self.temp_edge.append(hits[0])
                if len(self.temp_edge) == 2:
                    src, dst = self.temp_edge
                    edge = EdgeItem(src, dst, self.scale_factor)
                    self.scene.addItem(edge)
                    src.edges.append(edge)
                    dst.edges.append(edge)
                    self.edges.append(edge)
                    self.temp_edge = []
            return
        if self.mode == 'Edge Delete':
            for it in self.scene.items(QRectF(pos.x()-5, pos.y()-5, 10, 10)):
                if isinstance(it, EdgeItem):
                    self.scene.removeItem(it)
                    self.edges.remove(it)
                    it.src.edges.remove(it)
                    it.dst.edges.remove(it)
                    break
            return
        if self.mode == 'Calibrate Scale':
            for it in self.scene.items(QRectF(pos.x()-5, pos.y()-5, 10, 10)):
                if isinstance(it, EdgeItem):
                    it.toggle_selection()
                    break
            return
        QGraphicsScene.mousePressEvent(self.scene, event)

    def apply_scale(self):
        if self.mode != 'Calibrate Scale':
            return
        selected_edges = [e for e in self.edges if e.selected]
        if not selected_edges:
            return
        pixel_sum = sum(math.hypot(e.dst.pos().x()-e.src.pos().x(), e.dst.pos().y()-e.src.pos().y()) for e in selected_edges)
        meters, ok = QInputDialog.getDouble(self, 'Scale Calibration', f'Selected total pixel length: {pixel_sum:.2f}. Enter real-world meters:')
        if ok and pixel_sum > 0:
            self.scale_factor = meters / pixel_sum
            for e in self.edges:
                e.set_scale(self.scale_factor)
        for e in selected_edges:
            e.toggle_selection()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = GraphEditor()
    editor.show()
    sys.exit(app.exec_())
