import sys
import os
import json
import math
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QGraphicsView, QGraphicsScene,
    QGraphicsEllipseItem, QGraphicsLineItem, QGraphicsPixmapItem, QGraphicsTextItem,
    QGraphicsItem, QAction, QToolBar, QDockWidget, QWidget, QFormLayout, QLineEdit,
    QComboBox, QPushButton, QInputDialog
)
from PyQt5.QtGui import QBrush, QColor, QPen, QPixmap
from PyQt5.QtCore import Qt, QPointF, QRectF

# Default node types and colors, including door/exit type
default_types = {
    'Room': '#FF9999',
    'Corridor': '#99FF99',
    'Restroom': '#9999FF',
    'Stair': '#FFFF99',
    'Elevator': '#FF99FF',
    'Door': '#FFCC00'  # 출입문 요소
}

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
        # Toggle selected state and color
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
        self.node_types = dict(default_types)
        self.nodes = {}
        self.edges = []
        self.next_id = 1
        self.mode = None
        self.temp_edge = []

        self._init_ui()

    def _init_ui(self):
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.setCentralWidget(self.view)

        self.bg_item = None

        tb = QToolBar('Tools', self)
        self.addToolBar(tb)
        # File actions
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
        # Mode actions
        self.mode_actions = {}
        for name in ['Node Add', 'Node Edit', 'Node Delete', 'Edge Add', 'Edge Delete', 'Calibrate Scale']:
            act = QAction(name, self)
            act.setCheckable(True)
            act.triggered.connect(lambda checked, n=name: self.set_mode(n))
            tb.addAction(act)
            self.mode_actions[name] = act
        # Apply scale button
        self.apply_scale_btn = QAction('Apply Scale', self)
        self.apply_scale_btn.triggered.connect(self.apply_scale)
        tb.addAction(self.apply_scale_btn)

        # Properties dock
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

        # Mouse event override
        self.scene.mousePressEvent = self.on_mouse_press

    def set_mode(self, mode_name):
        # Toggle mode buttons
        for name, act in self.mode_actions.items():
            act.setChecked(name == mode_name)
        self.mode = mode_name
        # Show/hide properties
        self.prop_dock.setVisible(mode_name in ['Node Add', 'Node Edit'])
        # Preload properties when editing
        if mode_name == 'Node Edit':
            items = self.scene.selectedItems()
            if items and isinstance(items[0], NodeItem):
                node = items[0]
                self.prop_name.setText(node.name)
                self.prop_type.setCurrentText(node.ntype)
        # Make nodes movable only in edit mode
        for node in self.nodes.values():
            node.setFlag(QGraphicsEllipseItem.ItemIsMovable, mode_name == 'Node Edit')

    def new_background(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select Background Image', '', 'Images (*.png *.jpg *.bmp)')
        if not path:
            return
        # Clear scene
        self.scene.clear()
        self.nodes.clear()
        self.edges.clear()
        self.next_id = 1
        # Add background
        pix = QPixmap(path)
        self.bg_item = QGraphicsPixmapItem(pix)
        self.bg_item.filePath = path
        self.scene.addItem(self.bg_item)

    def load_json(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Open Graph JSON', '', 'JSON Files (*.json)')
        if not path:
            return
        with open(path, 'r') as f:
            data = json.load(f)
        # Load scale
        self.scale_factor = data.get('scale', 1.0)
        # Load background
        bg = data.get('background', '')
        if os.path.exists(bg):
            pix = QPixmap(bg)
            self.scene.clear()
            self.bg_item = QGraphicsPixmapItem(pix)
            self.bg_item.filePath = bg
            self.scene.addItem(self.bg_item)
        # Clear existing nodes/edges
        self.nodes.clear()
        self.edges.clear()
        self.next_id = 1
        # Create nodes
        for nd in data.get('nodes', []):
            node = NodeItem(nd['id'], nd['name'], nd['type'], self.node_types.get(nd['type'], '#CCCCCC'))
            node.setPos(nd['x'], nd['y'])
            self.scene.addItem(node)
            self.nodes[nd['id']] = node
            self.next_id = max(self.next_id, nd['id'] + 1)
        # Create edges
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
            # Default QGraphics handling (move/select)
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
                    # remove connected edges
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
            # Toggle selection on edges, no prompt
            for it in self.scene.items(QRectF(pos.x()-5, pos.y()-5, 10, 10)):
                if isinstance(it, EdgeItem):
                    it.toggle_selection()
                    break
            return
        # Default fallback
        QGraphicsScene.mousePressEvent(self.scene, event)

    def apply_scale(self):
        # Only apply when in calibrate mode
        if self.mode != 'Calibrate Scale':
            return
        # Gather selected edges
        selected_edges = [e for e in self.edges if e.selected]
        if not selected_edges:
            return
        # Compute total pixel length
        pixel_sum = sum(math.hypot(e.dst.pos().x()-e.src.pos().x(), e.dst.pos().y()-e.src.pos().y()) for e in selected_edges)
        meters, ok = QInputDialog.getDouble(self, 'Scale Calibration', f'Selected total pixel length: {pixel_sum:.2f}. Enter real-world meters:')
        if ok and pixel_sum > 0:
            self.scale_factor = meters / pixel_sum
            # Update all edges
            for e in self.edges:
                e.set_scale(self.scale_factor)
        # Clear selection highlights
        for e in selected_edges:
            e.toggle_selection()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = GraphEditor()
    editor.show()
    sys.exit(app.exec_())
