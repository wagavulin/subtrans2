#!/usr/bin/env python

import io
import requests
import sys
import time
import pyautogui
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLineEdit, QDialog, QMenuBar, QToolBar, QStatusBar, QLabel, QTextEdit, QGridLayout
from PySide6.QtGui import QAction, QPixmap, QScreen, QMouseEvent, QPainter, QPen, QFont, QTextCursor
from PySide6.QtCore import Qt
from PySide6.QtCore import QThread, QObject, Signal, QTimer
from PIL.ImageQt import ImageQt
import chatstatement as cstat

class ShowRectDialog(QDialog):
    def __init__(self, rect:tuple[int,int,int,int]):
        self.rect = rect
        super().__init__()
        self.setModal = True
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.5)
        self.showFullScreen()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        x, y, w, h = self.rect
        painter = QPainter(self)
        pen = QPen(Qt.red, 2, Qt.SolidLine)
        pen.setWidth(1)
        painter.setPen(pen)
        painter.drawRect(x, y, w, h)

    def mouseReleaseEvent(self, event:QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.accept()

class CaptureRectDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setModal = True
        self.is_drawing = False
        self.captured_rect:list[int,int,int,int] = [0, 0, 0, 0] # x, y, w, h
        self.setWindowFlag(Qt.FramelessWindowHint)
        self.setWindowFlag(Qt.WindowStaysOnTopHint)
        self.setWindowOpacity(0.5)
        self.showFullScreen()

    def mousePressEvent(self, event:QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            globalPos = event.globalPosition()
            self.captured_rect[0] = int(globalPos.x())
            self.captured_rect[1] = int(globalPos.y())

    def updateCapturedRect(self, event:QMouseEvent):
        globalPos = event.globalPosition()
        x = int(globalPos.x())
        y = int(globalPos.y())
        self.captured_rect[2] = x - self.captured_rect[0]
        self.captured_rect[3] = y - self.captured_rect[1]

    def mouseMoveEvent(self, event:QMouseEvent) -> None:
        self.updateCapturedRect(event)
        self.is_drawing = True
        self.repaint()

    def mouseReleaseEvent(self, event:QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.updateCapturedRect(event)
            self.accept()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if self.is_drawing:
            x, y, w, h = self.captured_rect
            painter = QPainter(self)
            pen = QPen(Qt.red, 2, Qt.SolidLine)
            pen.setWidth(1)
            painter.setPen(pen)
            painter.drawRect(x, y, w, h)

    def keyPressEvent(self, event):
        print(event.key())
        if event.key() == Qt.Key_Escape:
            QApplication.quit()

class DebugWindow(QWidget):
    N_MSG_ROWS = 4

    def __init__(self):
        super().__init__()
        self._init_gui()

    def _init_gui(self):
        self.setWindowTitle("Debug Window")

        layout1 = QVBoxLayout(self)
        layout1.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setLayout(layout1)

        self.ted_text_in = QTextEdit()
        layout1.addWidget(self.ted_text_in)

        self.lbl_image = QLabel("Image")
        layout1.addWidget(self.lbl_image)

        layout1_2 = QGridLayout()
        self.ted_messages:list[list[QLabel]] = []
        for row_i in range(self.N_MSG_ROWS):
            self.ted_messages.append([])
            for col_i in range(2):
                tmp_tedit = QTextEdit(f"{row_i} {col_i}")
                self.ted_messages[row_i].append(tmp_tedit)
                layout1_2.addWidget(tmp_tedit, row_i, col_i)
        layout1.addLayout(layout1_2)

class OcrWorkerSignals(QObject):
    status = Signal(str)
    error = Signal(str)
    ocr_result = Signal(str)
    finished = Signal()

class OcrWorker(QObject):
    run_signal = Signal(object)
    process_image_signal = Signal(object)
    run_test_signal = Signal(object)

    def __init__(self):
        super().__init__()
        self.signals = OcrWorkerSignals()
        self.run_signal.connect(self.run)
        self.process_image_signal.connect(self.process_image)
        self.test_ocr_paths = None
        self.test_ocr_path_idx = -1
        self.run_test_signal.connect(self.run_test)

    def run(self):
        while True:
            if self.thread().isInterruptionRequested():
                break
            time.sleep(0.1)

    def process_image(self, img_buf:memoryview):
        try:
            self.signals.status.emit(f"OCR")
            res1 = requests.post("http://localhost:8000", img_buf)
            if res1.status_code == 200:
                ocr_text = res1.text
                self.signals.ocr_result.emit(ocr_text)
            else:
                self.signals.error.emit(f"status: {res1.status_code}")
        except Exception as e:
            self.signals.error.emit(f"exception: {str(e)}")
        self.signals.finished.emit()

    def run_test(self):
        self.signals.status.emit("Test Started")
        if self.test_ocr_paths is None:
            import glob
            self.test_ocr_paths = [path.replace("\\", "/") for path in sorted(list(glob.glob(f"./ocr/*.txt")))]
            self.test_ocr_path_idx = 0
        if self.test_ocr_path_idx >= len(self.test_ocr_paths):
            self.signals.status.emit("No more OCR file")
            return
        with open(self.test_ocr_paths[self.test_ocr_path_idx]) as f:
            ocr_text = f.read()
        self.signals.ocr_result.emit(ocr_text)
        self.test_ocr_path_idx += 1
        self.signals.finished.emit()

class TransWorkerSignals(QObject):
    status = Signal(str)
    error = Signal(str)
    result = Signal(int, cstat.Statement)
    finished = Signal(int)

class TransWorker(QObject):
    translate_signal = Signal(object)

    def __init__(self, id:int, server:str):
        super().__init__()
        self.id = id
        self.server = server
        self.signals = TransWorkerSignals()
        self.translate_signal.connect(self.translate)

    def translate(self, args):
        id:int = args[0]
        stat:cstat.Statement = args[1]
        try:
            #self.signals.status.emit(f"Translate")
            res = requests.post(self.server, stat.message)
            if res.status_code == 200:
                stat.translated_text = res.text
                self.signals.result.emit(id, stat)
            else:
                self.signals.error.emit(f"status: {res.status_code}")
        except Exception as e:
            self.signals.error.emit(f"exception: {str(e)}")
        self.signals.finished.emit(self.id)

class MainWindow(QMainWindow):
    N_MSG_ROWS = 4

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Test App")
        self.resize(800, 700)

        self.sbuf = cstat.StatementBuffer()
        self.n_updated = -1

        self.scaled_rect:list[int,int,int,int] = [0, 0, 200, 100]
        self._init_gui()
        self._init_thread()
        self.timer = QTimer()
        self.timer.timeout.connect(self.recv_timeout)
        self.test_timer = QTimer()
        self.test_timer.timeout.connect(self.recv_test_timeout)

    def __del__(self):
        self.ocr_thread.quit()
        self.ocr_thread.requestInterruption()
        self.ocr_thread.wait()
        for trans_thread in self.trans_threads:
            trans_thread.quit()
            trans_thread.requestInterruption()
            trans_thread.wait()

    def _init_gui(self):
        menu_bar = QMenuBar()
        file_menu = menu_bar.addMenu("File")
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.instance().quit)
        file_menu.addAction(quit_action)
        self.setMenuBar(menu_bar)

        tool_bar = QToolBar("ToolBar1", self)
        tool_bar.addAction("Action1")
        tool_bar.addAction("Action2")
        self.addToolBar(tool_bar)

        self.status_bar = QStatusBar()
        self.status_bar.showMessage("Ready")
        self.setStatusBar(self.status_bar)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout1 = QVBoxLayout(central_widget)
        layout1.setAlignment(Qt.AlignmentFlag.AlignTop)

        layout1_1 = QHBoxLayout()
        layout1.insertLayout(0, layout1_1)
        layout1_1_1 = QVBoxLayout()
        layout1_1.insertLayout(0, layout1_1_1)

        self.btn_show_area = QPushButton("Show Area")
        self.btn_show_area.clicked.connect(self._btn_show_area_clicked)
        layout1_1_1.addWidget(self.btn_show_area)
        self.btn_set_area = QPushButton("Set Area")
        self.btn_set_area.clicked.connect(self._btn_set_area_clicked)
        layout1_1_1.addWidget(self.btn_set_area)
        self.btn_oneshot = QPushButton("One Short")
        self.btn_oneshot.clicked.connect(self._btn_oneshot_clicked)
        layout1_1_1.addWidget(self.btn_oneshot)
        self.btn_capture = QPushButton("Capture")
        self.btn_capture.clicked.connect(self._btn_capture_clicked)
        layout1_1_1.addWidget(self.btn_capture)
        self.btn_run_oneshot_test = QPushButton("Start One Shot Test")
        self.btn_run_oneshot_test.clicked.connect(self._btn_run_oneshot_test_clicked)
        layout1_1_1.addWidget(self.btn_run_oneshot_test)
        self.btn_run_loop_test = QPushButton("Start Loop Test")
        self.btn_run_loop_test.clicked.connect(self._btn_run_loop_test_clicked)
        layout1_1_1.addWidget(self.btn_run_loop_test)

        self.lbl_image = QLabel("Image")
        layout1_1.addWidget(self.lbl_image)

        self.ted_output = QTextEdit()
        font = QFont("MS Gothic")
        font.setPointSize(14)
        self.ted_output.setFont(font)
        self.ted_output.setReadOnly(True)
        layout1.addWidget(self.ted_output)

    def _init_thread(self):
        self.ocr_thread = QThread()
        self.ocr_worker = OcrWorker()
        self.ocr_worker.moveToThread(self.ocr_thread)
        self.ocr_worker.signals.status.connect(self.recv_ocr_status)
        self.ocr_worker.signals.error.connect(self.recv_ocr_error)
        self.ocr_worker.signals.ocr_result.connect(self.recv_ocr_result)
        self.ocr_worker.signals.finished.connect(self.recv_ocr_finished)
        self.ocr_is_running:bool = False
        self.ocr_thread.start()

        self.trans_threads:list[QThread] = []
        self.trans_workers:list[TransWorker] = []
        self.trans_is_runnings:list[bool] = []
        for i in range(self.N_MSG_ROWS):
            port = 8001 + i
            server = f"http://localhost:{port}"
            trans_thread = QThread()
            trans_worker = TransWorker(i, server)
            trans_worker.moveToThread(trans_thread)
            trans_worker.signals.status.connect(self.recv_trans_status)
            trans_worker.signals.error.connect(self.recv_trans_error)
            trans_worker.signals.result.connect(self.recv_trans_result)
            trans_worker.signals.finished.connect(self.recv_trans_finished)
            trans_thread.start()
            self.trans_threads.append(trans_thread)
            self.trans_workers.append(trans_worker)
            self.trans_is_runnings.append(False)

    def _btn_show_area_clicked(self):
        dialog = ShowRectDialog(self.scaled_rect)
        dialog.exec()
        self.status_bar.showMessage(f"{self.scaled_rect}")

    def _btn_set_area_clicked(self):
        self._get_scaling()
        dialog = CaptureRectDialog()
        if dialog.exec():
            self.scaled_rect = dialog.captured_rect

    def _btn_oneshot_clicked(self):
        self.status_bar.showMessage("One Shot")
        rect = self._calc_rect()
        pil_img = pyautogui.screenshot(region=rect)
        qim = ImageQt(pil_img)
        orig_pixmap = QPixmap.fromImage(qim)
        pixmap = orig_pixmap.scaled(400, 100, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.debug_window.lbl_image.setPixmap(pixmap)

        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format="PNG")
        img_buf = img_byte_arr.getbuffer()
        self.ocr_worker.process_image_signal.emit(img_buf)

    def _btn_capture_clicked(self):
        self.debug_window = DebugWindow()
        self.debug_window.show()
        if self.timer.isActive():
            print("timer is active -> stop")
            self.timer.stop()
        else:
            print("timer is not active -> run")
            self.timer.start(1000)
        return
        self.status_bar.showMessage("clicked")
        rect = self._calc_rect()
        pil_img = pyautogui.screenshot(region=rect)
        qim = ImageQt(pil_img)
        orig_pixmap = QPixmap.fromImage(qim)
        pixmap = orig_pixmap.scaled(400, 100, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.debug_window.lbl_image.setPixmap(pixmap)

        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format="PNG")
        img_buf = img_byte_arr.getbuffer()
        self.ocr_worker.process_image_signal.emit(img_buf)

    def _btn_run_oneshot_test_clicked(self):
        self.ocr_worker.run_test_signal.emit(None)

    def _btn_run_loop_test_clicked(self):
        self.debug_window = DebugWindow()
        self.debug_window.show()
        if self.timer.isActive():
            self.test_timer.stop()
        else:
            self.test_timer.start(1000)

    def _get_scaling(self) -> float:
        window_handle = self.windowHandle()
        if not window_handle:
            self.status_bar.showMessage("Error: No window handle")
            return 1.0
        screen = window_handle.screen()
        if not screen:
            self.status_bar.showMessage("Error: no screen found")
            return 1.0
        scaling = screen.devicePixelRatio()
        self.status_bar.showMessage(f"Scaling: {scaling}")
        return scaling

    def _calc_rect(self) -> tuple[int,int,int,int]:
        scaling = self._get_scaling()
        rect = [int(v * scaling) for v in self.scaled_rect]
        return tuple(rect)

    def is_ocr_trans_ready(self):
        is_running = self.ocr_is_running
        for b in self.trans_is_runnings:
            is_running = is_running or b
        return not is_running

    def capture_image(self) -> memoryview:
        rect = self._calc_rect()
        pil_img = pyautogui.screenshot(region=rect)
        qim = ImageQt(pil_img)
        orig_pixmap = QPixmap.fromImage(qim)
        pixmap = orig_pixmap.scaled(400, 100, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.debug_window.lbl_image.setPixmap(pixmap)

        img_byte_arr = io.BytesIO()
        pil_img.save(img_byte_arr, format="PNG")
        img_buf = img_byte_arr.getbuffer()
        #self.ocr_worker.process_image_signal.emit(img_buf)
        return img_buf

    def recv_timeout(self):
        if self.is_ocr_trans_ready():
            print("start OCR")
            img_buf = self.capture_image()
            self.ocr_worker.process_image_signal.emit(img_buf)
        else:
            print("OCR still running -> skip")

    def recv_test_timeout(self):
        if self.is_ocr_trans_ready():
            print("Start OCR test")
            self.ocr_worker.run_test_signal.emit(None)
            self.ocr_is_running = True
        else:
            print("Thread is running -> skip")

    def recv_ocr_status(self, message:str):
        self.status_bar.showMessage(f"OCR: {message}")

    def recv_ocr_error(self, error_message:str):
        self.status_bar.showMessage(f"OCR Error: {error_message}")

    def recv_ocr_result(self, ocr_text:str):
        lines = ocr_text.split("\n")
        new_stats = cstat.parse_lines(lines)
        texts = []
        for stat in new_stats:
            texts.append(stat.name)
            texts.append(stat.message)
        parsed_text = "\n".join(texts)
        self.debug_window.ted_text_in.setText(parsed_text)

        self.n_updated = self.sbuf.update(new_stats)
        show_stats = self.sbuf.stats[-self.N_MSG_ROWS:]
        for i, stat in enumerate(show_stats):
            need_translate = False
            if i < len(show_stats) - self.n_updated:
                self.debug_window.ted_messages[i][0].setTextColor("black")
            else:
                self.debug_window.ted_messages[i][0].setTextColor("red")
                need_translate = True
            #self.ted_messages[i][0].setText(stat.name + "\n" + stat.message)
            self.debug_window.ted_messages[i][0].setText(stat.name + "\n" + stat.message)
            if need_translate:
                self.debug_window.ted_messages[i][1].setText("")
                self.trans_workers[i].translate_signal.emit((i, stat))
                self.trans_is_runnings[i] = True
            else:
                self.debug_window.ted_messages[i][1].setText(stat.translated_text)
        for i in range(len(show_stats), len(self.debug_window.ted_messages)):
            self.debug_window.ted_messages[i][0].setText("")

    def recv_ocr_finished(self):
        print("ocr_process_finished")
        self.ocr_is_running = False

    def recv_trans_status(self, message:str):
        self.status_bar.showMessage(f"Trans: {message}")

    def recv_trans_error(self, error_message:str):
        self.status_bar.showMessage(f"Trans Error: {error_message}")

    def recv_trans_result(self, id:int, stat:cstat.Statement):
        self.debug_window.ted_messages[id][1].setText(stat.translated_text)

    def recv_trans_finished(self, id):
        print(f"trans_process_finished: {id}")
        self.trans_is_runnings[id] = False
        if not any(self.trans_is_runnings):
            self.update_output()

    def update_output(self):
        html = ""
        for i, stat in enumerate(self.sbuf.stats):
            need_translate = i >= (len(self.sbuf.stats) - self.n_updated)
            if need_translate:
                font_color="red"
            else:
                font_color="black"
            html += f"<div style='color: {font_color};'>{stat.name}</div>\n"
            html += f"<div><small style='color: {font_color};'>{stat.message}</small></div>\n"
            html += f"<div style='color: {font_color};'>{stat.translated_text}</div>\n"
            html += f"<hr>"

        doc = self.ted_output.document()
        doc.setHtml(html)
        self.ted_output.moveCursor(QTextCursor.MoveOperation.End)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
