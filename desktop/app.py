"""Windows-first desktop prototype. Worker mode also supports frozen builds."""
import json
import sys
from pathlib import Path
from core import PRESETS, Settings, load_csv, run_inversion
from runtime import configure_runtime, redirect_worker_log, resource_path


def main():
    from PySide6.QtCore import QProcess, QTimer, Qt, QUrl
    from PySide6.QtGui import QPixmap, QDesktopServices
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
        QVBoxLayout, QLabel, QPushButton, QListWidget, QStackedWidget, QFileDialog,
        QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout, QTextEdit, QLineEdit,
        QMessageBox, QScrollArea)

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('ERT Studio • 2D surface surveys')
            self.resize(1240, 780)
            self.input_path = None
            self.rows = None
            self.output_path = None
            self.process = None
            root = QWidget()
            self.setCentralWidget(root)
            layout = QHBoxLayout(root)
            self.steps = QListWidget()
            self.steps.addItems(['1  Import survey', '2  Check data', '3  Configure inversion',
                                 '4  Run inversion', '5  Review results'])
            self.steps.setFixedWidth(220)
            layout.addWidget(self.steps)
            self.pages = QStackedWidget()
            layout.addWidget(self.pages, 1)
            self.steps.currentRowChanged.connect(self.pages.setCurrentIndex)
            self.inputs = []

            def page(title, description):
                widget = QWidget()
                box = QVBoxLayout(widget)
                heading = QLabel(title)
                heading.setStyleSheet('font-size: 24px; font-weight: bold')
                box.addWidget(heading)
                label = QLabel(description)
                label.setWordWrap(True)
                box.addWidget(label)
                self.pages.addWidget(widget)
                return box

            box = page('Import your survey', 'Prototype: flat-surface 2D surveys with finite electrodes. '
                       'CSV columns: ax, bx, mx, nx (metres), rhoa (ohm m), error (relative fraction, e.g. 0.03). '
                       'Topography and instrument-specific importers are planned.')
            self.source = QLabel('No survey selected')
            box.addWidget(self.source)
            button = QPushButton('Choose survey CSV…')
            button.clicked.connect(self.import_data)
            box.addWidget(button)
            self.inputs.append(button)
            example = QPushButton('Try the included sample survey')
            example.clicked.connect(lambda: self.load_survey(str(resource_path('examples/homogeneous.csv'))))
            box.addWidget(example)
            self.inputs.append(example)
            box.addStretch()

            box = page('Check data quality', 'Input checks reject missing, non-finite, non-positive resistivity, '
                       'invalid errors and degenerate electrode geometries. No measurements are silently removed. '
                       'Reciprocal analysis and interactive filtering are planned.')
            self.quality = QLabel('Import a survey to see validation results.')
            self.quality.setWordWrap(True)
            box.addWidget(self.quality)
            box.addStretch()

            box = page('Choose an inversion approach', 'Both presets use pyGIMLi. Smooth regularization favors '
                       'gradual changes; blocky IRLS regularization favors sharper boundaries. '
                       'Data weighting uses the supplied errors in both presets.')
            form = QFormLayout()
            self.preset = QComboBox()
            self.preset.addItems(PRESETS)
            self.lam = QDoubleSpinBox()
            self.lam.setRange(0.01, 100000)
            self.lam.setValue(20)
            self.start = QDoubleSpinBox()
            self.start.setRange(0.01, 1000000)
            self.start.setValue(100)
            self.iterations = QSpinBox()
            self.iterations.setRange(1, 100)
            self.iterations.setValue(10)
            for title, control in [('Model preset', self.preset), ('Regularization strength λ', self.lam),
                                   ('Starting resistivity (ohm m)', self.start), ('Maximum iterations', self.iterations)]:
                form.addRow(title, control)
                self.inputs.append(control)
            box.addLayout(form)
            box.addStretch()

            box = page('Run inversion', 'Runs locally in a separate process. Choose a new results folder for '
                       'each run. Cancelling keeps partial files, which are not completed results.')
            self.run = QPushButton('Choose results folder and run…')
            self.run.clicked.connect(self.start_run)
            self.inputs.append(self.run)
            box.addWidget(self.run)
            self.cancel = QPushButton('Cancel run')
            self.cancel.setEnabled(False)
            self.cancel.clicked.connect(self.cancel_run)
            box.addWidget(self.cancel)
            self.log = QTextEdit()
            self.log.setReadOnly(True)
            box.addWidget(self.log, 1)

            box = page('Review results', 'Resistivity is non-unique. Review misfit, coverage and geological '
                       'context together. The results folder includes model meshes, coverage, responses and run settings.')
            self.summary = QLabel('Complete an inversion to view results.')
            self.summary.setWordWrap(True)
            box.addWidget(self.summary)
            open_results = QPushButton('Open results folder')
            open_results.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.output_path))) if self.output_path else None)
            box.addWidget(open_results)
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            self.image = QLabel()
            self.image.setAlignment(Qt.AlignCenter)
            scroll.setWidget(self.image)
            box.addWidget(scroll, 1)

            sidebar = QVBoxLayout()
            sidebar.addWidget(QLabel('Navigation assistant • offline commands'))
            self.chat = QTextEdit()
            self.chat.setReadOnly(True)
            self.chat.setPlainText('Try “go to import”, “check data”, “configure inversion”, '
                                   '“show results”, or “help”.\nThis prototype uses fixed commands, not a language model.')
            sidebar.addWidget(self.chat, 1)
            self.prompt = QLineEdit()
            self.prompt.setPlaceholderText('Where would you like to go?')
            self.prompt.returnPressed.connect(self.navigate)
            sidebar.addWidget(self.prompt)
            send = QPushButton('Send')
            send.clicked.connect(self.navigate)
            sidebar.addWidget(send)
            side = QWidget()
            side.setLayout(sidebar)
            side.setFixedWidth(290)
            layout.addWidget(side)
            self.steps.setCurrentRow(0)
            self.statusBar().showMessage('Ready • all survey processing stays on this computer')
            self.log_offset = 0
            self.log_timer = QTimer(self)
            self.log_timer.setInterval(300)
            self.log_timer.timeout.connect(self.read_log)

        def import_data(self):
            path, _ = QFileDialog.getOpenFileName(self, 'Open survey', '', 'Survey CSV (*.csv)')
            if path:
                self.load_survey(path)

        def load_survey(self, path):
            try:
                rows = load_csv(path)
            except Exception as exc:
                QMessageBox.warning(self, 'Survey could not be imported', str(exc))
                return
            self.input_path, self.rows = path, rows
            self.output_path = None
            self.image.clear()
            self.summary.setText('Complete an inversion for the newly imported survey.')
            self.source.setText(path)
            electrodes = {row[key] for row in rows for key in ('ax', 'bx', 'mx', 'nx')}
            self.quality.setText(f'{len(rows)} measurements • {len(electrodes)} electrodes\n'
                                 f'Profile: {min(electrodes):g} to {max(electrodes):g} m\n'
                                 'Input checks passed. Check units, survey geometry and error estimates before inversion.')
            self.steps.setCurrentRow(1)

        def start_run(self):
            if not self.rows:
                QMessageBox.information(self, 'Import required', 'Import and check a survey first.')
                return
            folder = QFileDialog.getExistingDirectory(self, 'Choose parent folder for new run')
            if not folder:
                return
            try:
                self.prepare_run(folder)
            except OSError as exc:
                QMessageBox.warning(self, 'Cannot create results', str(exc))

        def prepare_run(self, folder):
            from tempfile import mkdtemp
            from dataclasses import asdict
            import csv
            output = Path(mkdtemp(prefix='ert-run-', dir=folder))
            # Snapshot validated data so later edits to the source cannot change this run.
            with (output / 'survey.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(self.rows[0]))
                writer.writeheader()
                writer.writerows(self.rows)
            settings = Settings(self.preset.currentText(), self.lam.value(),
                                self.iterations.value(), self.start.value())
            (output / 'settings.json').write_text(json.dumps(asdict(settings)), encoding='utf-8')
            self.output_path = output
            self.image.clear()
            self.summary.setText('Inversion running…')
            self.log.clear()
            self.log_offset = 0
            self.log_timer.start()
            self.cancelled = False
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_log)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.process_error)
            for widget in self.inputs:
                widget.setEnabled(False)
            self.cancel.setEnabled(True)
            args = ['--worker', str(output)]
            if not getattr(sys, 'frozen', False):
                args.insert(0, str(Path(__file__).resolve()))
            self.process.start(sys.executable, args)
            self.statusBar().showMessage('Inverting • see live solver output')

        def read_log(self):
            if self.process:
                self.log.insertPlainText(bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace'))
            if self.output_path and (self.output_path / 'solver.log').exists():
                with (self.output_path / 'solver.log').open('rb') as stream:
                    stream.seek(self.log_offset)
                    chunk = stream.read()
                    self.log_offset = stream.tell()
                self.log.insertPlainText(chunk.decode('utf-8', errors='replace'))
            self.log.ensureCursorVisible()

        def process_error(self, error):
            if error == QProcess.FailedToStart:
                self.log.append(self.process.errorString())
                self.finished(-1, QProcess.CrashExit)

        def cancel_run(self):
            self.cancelled = True
            self.process.kill()

        def finished(self, code, status):
            self.log_timer.stop()
            self.read_log()
            for widget in self.inputs:
                widget.setEnabled(True)
            self.cancel.setEnabled(False)
            if code != 0 or status != QProcess.NormalExit or self.cancelled:
                message = 'Cancelled; partial files retained.' if self.cancelled else 'Inversion failed; see solver log.'
                self.summary.setText(message)
                self.statusBar().showMessage(message)
                return
            try:
                result = json.loads((self.output_path / 'run.json').read_text(encoding='utf-8'))
                self.summary.setText(f"χ²: {result['chi_squared']:.3g} • relative RMS: "
                                     f"{result['relative_rms_percent']:.2f}%\nSaved to {self.output_path}")
                self.image.setPixmap(QPixmap(str(self.output_path / 'model.png')).scaledToWidth(800, Qt.SmoothTransformation))
                self.steps.setCurrentRow(4)
                self.statusBar().showMessage('Inversion complete')
            except Exception as exc:
                self.summary.setText(f'Could not load completed results: {exc}')

        def navigate(self):
            prompt = self.prompt.text().strip()
            if not prompt:
                return
            self.chat.setPlainText(self.chat.toPlainText() + '\nYou: ' + prompt)
            # Plain text avoids rendering user-supplied HTML.
            text = prompt.lower().strip(' .!?')
            commands = {'go to import': 0, 'import': 0, 'check data': 1, 'configure inversion': 2,
                        'run inversion': 3, 'show results': 4, 'results': 4}
            if text in commands:
                self.steps.setCurrentRow(commands[text])
                reply = 'Opened ' + self.steps.currentItem().text() + '. Use the buttons to continue.'
            else:
                reply = 'Available commands: go to import, check data, configure inversion, run inversion, show results.'
            self.chat.setPlainText(self.chat.toPlainText() + '\nAssistant: ' + reply)
            self.prompt.clear()

        def closeEvent(self, event):
            if self.process and self.process.state() != QProcess.NotRunning:
                QMessageBox.information(self, 'Run active', 'Cancel the inversion before closing.')
                event.ignore()
            else:
                event.accept()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window()
    window.show()
    if '--workflow-test' in sys.argv:
        target = Path(sys.argv[sys.argv.index('--workflow-test') + 1]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        def exercise_workflow():
            window.load_survey(str(resource_path('examples/homogeneous.csv')))
            window.start.setValue(80)
            window.iterations.setValue(5)
            window.steps.setCurrentRow(3)
            window.prepare_run(str(target))
            def complete(code, status):
                success = code == 0 and status == QProcess.NormalExit and (window.output_path / 'run.json').exists() and not window.image.pixmap().isNull()
                QTimer.singleShot(0, lambda: app.exit(0 if success else 1))
            window.process.finished.connect(complete)
            window.process.errorOccurred.connect(lambda _: app.exit(1))
        QTimer.singleShot(0, exercise_workflow)
        QTimer.singleShot(180000, lambda: app.exit(1))
    if '--smoke-test' in sys.argv:
        QTimer.singleShot(1000, app.quit)
    sys.exit(app.exec())


if __name__ == '__main__':
    import traceback
    import multiprocessing
    multiprocessing.freeze_support()
    runtime_folder = configure_runtime()
    if len(sys.argv) == 3 and sys.argv[1] == '--worker':
        folder = Path(sys.argv[2]).resolve()
        log_stream = redirect_worker_log(folder)
        try:
            settings = Settings(**json.loads((folder / 'settings.json').read_text(encoding='utf-8')))
            run_inversion(folder / 'survey.csv', folder, settings)
        except Exception:
            traceback.print_exc()
            sys.exit(1)
        finally:
            log_stream.flush()
    elif len(sys.argv) == 3 and sys.argv[1] == '--diagnostics':
        Path(sys.argv[2]).write_text(json.dumps({
            'frozen': bool(getattr(sys, 'frozen', False)),
            'executable': sys.executable, 'runtime': str(runtime_folder),
            'bundled_python': sys.version,
        }, indent=2), encoding='utf-8')
    else:
        try:
            main()
        except Exception:
            (runtime_folder / 'startup-error.log').write_text(traceback.format_exc(), encoding='utf-8')
            if sys.platform == 'win32':
                import ctypes
                ctypes.windll.user32.MessageBoxW(0, 'ERT Studio could not start. Details: ' + str(runtime_folder / 'startup-error.log'), 'ERT Studio', 0x10)
            raise
