import sys
import os
import time
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                               QHBoxLayout, QPushButton, QLabel, QFileDialog,
                               QComboBox, QMessageBox, QProgressBar, QGroupBox,
                               QTextEdit, QSplitter)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont

from ir_label import ImageInfo
from converters import (VOCImporter, YOLOImporter, COCOImporter, LabelMeImporter,
                        VOCExporter, YOLOExporter, COCOExporter, LabelMeExporter)

# QSS
STYLESHEET = """
QMainWindow {
    background-color: #f0f2f5;
}
QGroupBox {
    font-weight: bold;
    border: 1px solid #dcdcdc;
    border-radius: 8px;
    margin-top: 10px;
    background-color: #ffffff;
    padding: 15px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 5px;
    color: #333333;
}
QPushButton {
    background-color: #007AFF; 
    color: white; 
    border-radius: 6px; 
    padding: 8px 15px;
    font-size: 13px;
    font-weight: bold;
}
QPushButton:hover {
    background-color: #0062cc;
}
QPushButton:pressed {
    background-color: #004999;
}
QPushButton#btn_convert {
    background-color: #28a745; 
    font-size: 16px;
    padding: 12px;
}
QPushButton#btn_convert:hover {
    background-color: #218838;
}
QComboBox {
    padding: 5px;
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: white;
}
QProgressBar {
    border: 1px solid #bbb;
    border-radius: 5px;
    text-align: center;
    background-color: #e9ecef;
}
QProgressBar::chunk {
    background-color: #007AFF;
    border-radius: 4px;
}
QTextEdit {
    border: 1px solid #ccc;
    border-radius: 4px;
    background-color: #2b2b2b;
    color: #00ff00; 
    font-family: Consolas, monospace;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("UniLabel Converter - 目标检测标签格式转换工具")
        self.resize(900, 650)
        self.setStyleSheet(STYLESHEET)

        # IR数据模型
        self.current_data: list[ImageInfo] = []

        self.init_ui()

    def init_ui(self):
        # 0
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 1
        group_input = QGroupBox("1. 数据导入 (Input)")
        layout_input = QHBoxLayout()

        layout_input.addWidget(QLabel("原始格式(Original):"))
        self.combo_in = QComboBox()
        self.combo_in.addItems(["Pascal VOC (.xml)", "YOLO (.txt)", "MS COCO (.json)", "LabelMe (.json)"])
        self.combo_in.setMinimumWidth(150)
        layout_input.addWidget(self.combo_in)

        self.btn_load = QPushButton("📂 选择文件夹/文件")
        self.btn_load.clicked.connect(self.load_data)
        layout_input.addWidget(self.btn_load)

        self.lbl_count = QLabel("未加载数据")
        self.lbl_count.setStyleSheet("color: #666; font-style: italic;")
        layout_input.addWidget(self.lbl_count)

        layout_input.addStretch()
        group_input.setLayout(layout_input)
        main_layout.addWidget(group_input)

        # 2
        group_output = QGroupBox("2. 转换设置 (Output)")
        layout_output = QHBoxLayout()

        layout_output.addWidget(QLabel("目标格式(Target):"))
        self.combo_out = QComboBox()
        self.combo_out.addItems(["Pascal VOC", "YOLO", "MS COCO", "LabelMe"])
        self.combo_out.setMinimumWidth(150)
        layout_output.addWidget(self.combo_out)

        self.btn_out_dir = QPushButton("📂 选择保存路径")
        self.btn_out_dir.clicked.connect(self.select_output_dir)
        layout_output.addWidget(self.btn_out_dir)

        self.lbl_out_path = QLabel("未选择路径")
        self.lbl_out_path.setStyleSheet("color: #666;")
        layout_output.addWidget(self.lbl_out_path)

        layout_output.addStretch()
        group_output.setLayout(layout_output)
        main_layout.addWidget(group_output)

        # 3
        layout_action = QVBoxLayout()

        self.btn_convert = QPushButton("开始转换 (Start Conversion)")
        self.btn_convert.setObjectName("btn_convert")
        self.btn_convert.setCursor(Qt.PointingHandCursor)
        self.btn_convert.setEnabled(False)
        self.btn_convert.clicked.connect(self.run_conversion)
        layout_action.addWidget(self.btn_convert)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout_action.addWidget(self.progress_bar)

        main_layout.addLayout(layout_action)

        # 4
        group_log = QGroupBox("运行日志 (Log)")
        layout_log = QVBoxLayout()
        self.txt_log = QTextEdit()
        self.txt_log.setReadOnly(True)
        layout_log.addWidget(self.txt_log)
        group_log.setLayout(layout_log)

        main_layout.addWidget(group_log, 1)

        self.output_dir = ""

    def log(self, message):
        timestamp = time.strftime("[%H:%M:%S] ", time.localtime())
        self.txt_log.append(timestamp + message)
        sb = self.txt_log.verticalScrollBar()
        sb.setValue(sb.maximum())
        QApplication.processEvents() # 强制刷新UI，防止卡死

    def load_data(self):
        fmt = self.combo_in.currentText()
        self.current_data = []
        self.log(f"正在准备加载 {fmt} 数据...")

        try:
            if "COCO" in fmt:
                path, _ = QFileDialog.getOpenFileName(self, "选择 COCO JSON 文件", "", "JSON Files (*.json)")
                if not path: return
                img_dir = QFileDialog.getExistingDirectory(self, "选择 COCO 图片所在文件夹")
                if not img_dir: return

                importer = COCOImporter()
                self.current_data = importer.parse_all(path, img_dir)

            elif "YOLO" in fmt:
                folder = QFileDialog.getExistingDirectory(self, "选择 YOLO txt 和图片所在文件夹")
                if not folder: return
                classes_path, _ = QFileDialog.getOpenFileName(self, "选择 classes.txt", folder, "TXT Files (*.txt)")
                if not classes_path: return

                with open(classes_path, 'r') as f:
                    class_names = [line.strip() for line in f.readlines() if line.strip()]

                importer = YOLOImporter()
                files = [f for f in os.listdir(folder) if f.endswith('.txt') and f != 'classes.txt'] # NOTE: 防止把classes.txt和数据集放一起

                self.progress_bar.setMaximum(len(files))
                for i, f in enumerate(files):
                    txt_path = os.path.join(folder, f)
                    img_name_base = os.path.splitext(f)[0]
                    img_path = None
                    for ext in ['.jpg', '.png', '.jpeg', '.bmp']:
                        temp_path = os.path.join(folder, img_name_base + ext)
                        if os.path.exists(temp_path):
                            img_path = temp_path
                            break

                    if img_path:
                        self.current_data.append(importer.parse(txt_path, img_path, class_names))
                    else:
                        self.log(f"[Warning] 找不到对应的图片: {f}，跳过。")
                    self.progress_bar.setValue(i+1)

            else:
                folder = QFileDialog.getExistingDirectory(self, "选择数据集文件夹")
                if not folder: return

                if "VOC" in fmt:
                    importer = VOCImporter()
                    files = [f for f in os.listdir(folder) if f.endswith('.xml')]
                elif "LabelMe" in fmt:
                    importer = LabelMeImporter()
                    files = [f for f in os.listdir(folder) if f.endswith('.json')]

                self.progress_bar.setMaximum(len(files))
                for i, f in enumerate(files):
                    self.current_data.append(importer.parse(os.path.join(folder, f)))
                    self.progress_bar.setValue(i+1)

            count = len(self.current_data)
            self.lbl_count.setText(f"已加载 {count} 张图片")
            self.log(f"成功加载 {count} 个标注文件。")
            self.progress_bar.setValue(0)

            if count > 0:
                self.btn_convert.setEnabled(True)
                if not self.output_dir:
                    self.lbl_out_path.setText("请选择保存路径 ->")
                    self.lbl_out_path.setStyleSheet("color: red; font-weight: bold;")

        except Exception as e:
            self.log(f"[Error] 加载失败: {str(e)}")
            QMessageBox.critical(self, "Error", f"加载数据时发生错误:\n{str(e)}")

    def select_output_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "选择保存路径")
        if dir_path:
            self.output_dir = dir_path
            self.lbl_out_path.setText(dir_path)
            self.lbl_out_path.setStyleSheet("color: #333;")

    def run_conversion(self):
        if os.listdir(self.output_dir):
            reply = QMessageBox.question(
                self,
                "警告 / Warning",
                "输出目录不为空，可能会覆盖同名文件！\nOutput directory is not empty. Files may be overwritten!\n\n是否继续？(Continue?)",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        if not self.output_dir:
            QMessageBox.warning(self, "提示", "请先选择保存路径 (Output Directory)！")
            return

        fmt = self.combo_out.currentText()
        self.log(f"开始转换为 {fmt} ...")
        self.progress_bar.setValue(0)

        try:
            if "YOLO" in fmt:
                exporter = YOLOExporter()
                exporter.export(self.current_data, self.output_dir)     # NOTE: 这里没必要传class_list形参，会自动生成classes.txt
                self.progress_bar.setValue(100)

            elif "COCO" in fmt:
                exporter = COCOExporter()
                save_path = os.path.join(self.output_dir, "instances_converted.json")
                exporter.export(self.current_data, save_path)
                self.progress_bar.setValue(100)

            else:
                if "VOC" in fmt:
                    exporter = VOCExporter()
                elif "LabelMe" in fmt:
                    exporter = LabelMeExporter()

                total = len(self.current_data)
                self.progress_bar.setMaximum(total)

                for i, info in enumerate(self.current_data):
                    exporter.export(info, self.output_dir)
                    # 只有在非多线程环境下，才需要手动刷新事件循环来更新进度条
                    if i % 10 == 0:
                        self.progress_bar.setValue(i+1)
                        QApplication.processEvents()
                self.progress_bar.setValue(total)

            self.log(f"转换完成！文件已保存至: {self.output_dir}")
            QMessageBox.information(self, "成功", "格式转换任务已完成！")

        except Exception as e:
            self.log(f"[Error] 转换失败: {str(e)}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"转换过程中发生错误:\n{str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Segoe UI", 10)
    font.setStyleStrategy(QFont.PreferAntialias)
    app.setFont(font)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())