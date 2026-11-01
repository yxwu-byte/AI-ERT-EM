"""Windows-first desktop prototype. Worker mode also supports frozen builds."""
import json
import sys
from pathlib import Path
from core import PRESETS, Settings, load_csv, run_inversion
from runtime import configure_runtime, redirect_worker_log, resource_path


def main():
    from PySide6.QtCore import QProcess, QTimer, Qt, QUrl, QSize
    from PySide6.QtGui import QPixmap, QDesktopServices
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
        QVBoxLayout, QLabel, QPushButton, QToolButton, QGridLayout, QGroupBox, QCheckBox, QStyle, QStackedWidget, QFileDialog,
        QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout, QTextEdit, QLineEdit,
        QMessageBox, QScrollArea, QSizePolicy)

    class Window(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle('ERT Studio • 2D surface surveys')
            self.resize(1440, 940)
            self.setMinimumSize(1060, 720)
            self.input_path = None
            self.rows = None
            self.output_path = None
            self.process = None
            root = QWidget()
            self.setCentralWidget(root)
            layout = QHBoxLayout(root)
            workspace = QVBoxLayout()
            layout.addLayout(workspace, 1)
            title = QLabel('ERT Studio  /  Survey workspace')
            title.setStyleSheet('font-size: 23px; font-weight: 700; color: #102c48;')
            workspace.addWidget(title)
            intro = QLabel('Follow the tiles from survey import to your resistivity model.')
            workspace.addWidget(intro)
            self.step_titles = ['Import survey', 'Check data', 'Configure inversion', 'Run inversion', 'Review results']
            details = ['Load CSV or try sample data', 'Review geometry and input checks',
                       'Choose model, mesh and weighting', 'Start, monitor or cancel the solver',
                       'View your model and export files']
            icons = [QStyle.SP_DialogOpenButton, QStyle.SP_DialogApplyButton,
                     QStyle.SP_FileDialogDetailedView, QStyle.SP_MediaPlay, QStyle.SP_FileDialogContentsView]
            self.tiles = []
            grid = QGridLayout()
            grid.setSpacing(12)
            for index, (title, detail, icon) in enumerate(zip(self.step_titles, details, icons)):
                tile = QToolButton()
                tile.setCheckable(True)
                tile.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
                tile.setIcon(self.style().standardIcon(icon))
                tile.setIconSize(QSize(26, 26))
                tile.setText(f'{index + 1:02d}   {title}\n{detail}')
                tile.setAccessibleName(f'Step {index + 1}: {title}')
                tile.setMinimumHeight(100)
                tile.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
                tile.clicked.connect(lambda checked=False, step=index: self.select_step(step))
                grid.addWidget(tile, index // 3, index % 3)
                self.tiles.append(tile)
            for column in range(3):
                grid.setColumnStretch(column, 1)
            workspace.addLayout(grid)
            self.pages = QStackedWidget()
            workspace.addWidget(self.pages, 1)
            self.setStyleSheet("""
                QMainWindow { background: #f3f6fb; }
                QToolButton { background: white; color: #193853; border: 1px solid #d1dce8;
                              border-radius: 12px; padding: 10px; font-size: 12px; }
                QToolButton:hover { border: 2px solid #448bd0; background: #edf6ff; }
                QToolButton:checked { border: 2px solid #2376bd; background: #dfedfc; }
                QToolButton:focus { border: 2px solid #2376bd; }
                QGroupBox { font-weight: bold; border: 1px solid #d1dce8; border-radius: 8px;
                            margin-top: 12px; padding: 14px; background: white; }
                QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 5px; }
                QPushButton { padding: 9px 14px; }
                QScrollArea { border: none; }
            """)
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
                scroll = QScrollArea()
                scroll.setWidgetResizable(True)
                scroll.setWidget(widget)
                self.pages.addWidget(scroll)
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
                       'Data errors and optional robust weighting are configured below.')
            self.parameter_controls = {}
            self.bound_controls = []

            def section(title, description):
                group = QGroupBox(title)
                content = QVBoxLayout(group)
                help_label = QLabel(description)
                help_label.setWordWrap(True)
                help_label.setStyleSheet('font-weight: normal; color: #52667b;')
                content.addWidget(help_label)
                form = QFormLayout()
                form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
                content.addLayout(form)
                box.addWidget(group)
                return form

            def number(form, key, label, low, high, default, help_text, decimals=2, special=None):
                control = QDoubleSpinBox()
                control.setDecimals(decimals)
                control.setRange(low, high)
                control.setValue(default)
                if special:
                    control.setSpecialValueText(special)
                control.setToolTip(help_text)
                control.setAccessibleDescription(help_text)
                form.addRow(label, control)
                self.inputs.append(control)
                self.parameter_controls[key] = control
                return control

            form = section('Model and regularization', 'Choose gradual or sharper changes. Higher λ favors a smoother model; '
                           'a smaller vertical weight permits more change with depth relative to horizontal changes.')
            self.preset = QComboBox()
            self.preset.addItems(PRESETS)
            form.addRow('Model preset', self.preset)
            self.inputs.append(self.preset)
            self.lam = number(form, 'regularization', 'Regularization strength λ', 0.01, 100000, 20,
                              'Higher values penalize model roughness more strongly.')
            self.start = number(form, 'start_resistivity', 'Starting resistivity (ohm m)', 0.01, 1000000, 100,
                                'Uniform resistivity used to start the inversion.')
            number(form, 'vertical_weight', 'Vertical smoothing weight', 0.01, 1, 1,
                   'Ratio of vertical to horizontal roughness weighting.')
            number(form, 'lambda_factor', 'λ multiplier per iteration', 0.01, 1, 1,
                   '1 keeps λ constant; below 1 gradually relaxes regularization.')

            form = section('Data weighting', 'Keep supplied CSV errors or set a minimum uncertainty. Robust data '
                           'weighting reduces the influence of large residuals; it does not remove bad measurements.')
            self.robust_data = QCheckBox('Use robust data weighting (IRLS)')
            form.addRow(self.robust_data)
            self.inputs.append(self.robust_data)
            number(form, 'error_floor', 'Minimum relative error (%)', 0, 99, 0,
                   'Effective error is the larger of the CSV error and this floor. No data are discarded.', special='Use CSV errors')

            form = section('Mesh', 'Automatic values use pyGIMLi defaults. Finer cells increase computation cost; '
                           'requested mesh depth is not a guarantee of reliable investigation depth.')
            number(form, 'mesh_depth', 'Model depth (m)', 0, 100000, 0,
                   'Depth of the parameter domain below the flat surface; zero selects automatic.', special='Automatic')
            number(form, 'max_cell_area', 'Maximum parameter cell area (m²)', 0, 1000000, 0,
                   'Upper bound for triangular parameter-cell area; zero selects automatic.', decimals=3, special='Automatic')

            form = section('Resistivity bounds', 'Optional physical bounds constrain the model. '
                           'The starting resistivity must lie strictly between the limits.')
            self.use_bounds = QCheckBox('Constrain resistivity to a range')
            form.addRow(self.use_bounds)
            self.inputs.append(self.use_bounds)
            for key, label, default in [('lower_resistivity', 'Minimum resistivity (ohm m)', 1),
                                        ('upper_resistivity', 'Maximum resistivity (ohm m)', 100000)]:
                control = number(form, key, label, 0.001, 10000000, default,
                                 'Both bounds are required; minimum < starting model < maximum.', decimals=3)
                self.bound_controls.append(control)
            self.use_bounds.toggled.connect(self.refresh_bounds)
            self.refresh_bounds()

            form = section('Stopping criteria', 'The iteration limit is a cap, not evidence of convergence. '
                           'Review the final misfit and solver log before interpretation.')
            self.iterations = QSpinBox()
            self.iterations.setRange(1, 100)
            self.iterations.setValue(10)
            form.addRow('Maximum iterations', self.iterations)
            self.inputs.append(self.iterations)
            number(form, 'min_phi_change', 'Minimum objective improvement (%)', 0, 100, 1,
                   'Stop when relative objective improvement falls below this percentage after the initial iterations.')
            self.stop_at_chi_one = QCheckBox('Stop when χ² reaches 1 or less')
            self.stop_at_chi_one.setChecked(True)
            form.addRow(self.stop_at_chi_one)
            self.inputs.append(self.stop_at_chi_one)
            reset = QPushButton('Restore recommended defaults')
            reset.clicked.connect(self.reset_parameters)
            box.addWidget(reset)
            self.inputs.append(reset)
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
            side.setFixedWidth(275)
            layout.addWidget(side)
            self.select_step(0)
            self.statusBar().showMessage('Ready • all survey processing stays on this computer')
            self.log_offset = 0
            self.log_timer = QTimer(self)
            self.log_timer.setInterval(300)
            self.log_timer.timeout.connect(self.read_log)

        def select_step(self, index):
            self.pages.setCurrentIndex(index)
            for step, tile in enumerate(self.tiles):
                tile.setChecked(step == index)

        def refresh_bounds(self):
            enabled = self.use_bounds.isChecked() and self.use_bounds.isEnabled()
            for control in self.bound_controls:
                control.setEnabled(enabled)

        def reset_parameters(self):
            defaults = Settings()
            self.preset.setCurrentText(defaults.preset)
            for key, control in self.parameter_controls.items():
                value = getattr(defaults, key)
                if key == 'error_floor':
                    value *= 100
                if value is None:
                    value = {'lower_resistivity': 1, 'upper_resistivity': 100000}.get(key, 0)
                control.setValue(value)
            self.iterations.setValue(defaults.max_iterations)
            self.robust_data.setChecked(defaults.robust_data)
            self.stop_at_chi_one.setChecked(defaults.stop_at_chi_one)
            self.use_bounds.setChecked(False)
            self.refresh_bounds()

        def current_settings(self):
            values = {key: control.value() for key, control in self.parameter_controls.items()}
            values['error_floor'] /= 100
            for key in ('mesh_depth', 'max_cell_area'):
                values[key] = values[key] or None
            if not self.use_bounds.isChecked():
                values['lower_resistivity'] = values['upper_resistivity'] = None
            settings = Settings(preset=self.preset.currentText(), max_iterations=self.iterations.value(),
                                robust_data=self.robust_data.isChecked(),
                                stop_at_chi_one=self.stop_at_chi_one.isChecked(), **values)
            settings.validate()
            return settings

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
            self.select_step(1)

        def start_run(self):
            if not self.rows:
                QMessageBox.information(self, 'Import required', 'Import and check a survey first.')
                return
            try:
                self.current_settings()
            except ValueError as exc:
                QMessageBox.warning(self, 'Check inversion parameters', str(exc))
                self.select_step(2)
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
            settings = self.current_settings()
            output = Path(mkdtemp(prefix='ert-run-', dir=folder))
            # Snapshot validated data so later edits to the source cannot change this run.
            with (output / 'survey.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(self.rows[0]))
                writer.writeheader()
                writer.writerows(self.rows)
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
            self.refresh_bounds()
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
                self.select_step(4)
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
                self.select_step(commands[text])
                reply = 'Opened ' + self.step_titles[commands[text]] + '. Use the buttons to continue.'
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
            for step, tile in enumerate(window.tiles):
                tile.click()
                assert window.pages.currentIndex() == step
                assert [button.isChecked() for button in window.tiles] == [i == step for i in range(5)]
            window.prompt.setText('configure inversion')
            window.navigate()
            assert window.pages.currentIndex() == 2
            window.parameter_controls['error_floor'].setValue(5)
            assert window.current_settings().error_floor == 0.05
            window.reset_parameters()
            assert window.current_settings() == Settings()
            window.load_survey(str(resource_path('examples/homogeneous.csv')))
            window.start.setValue(80)
            window.iterations.setValue(5)
            window.robust_data.setChecked(True)
            window.stop_at_chi_one.setChecked(False)
            window.use_bounds.setChecked(True)
            for key, value in dict(error_floor=5, lower_resistivity=50, upper_resistivity=200,
                                   mesh_depth=4, max_cell_area=0.5, vertical_weight=0.7,
                                   lambda_factor=0.9, min_phi_change=0.5).items():
                window.parameter_controls[key].setValue(value)
            window.select_step(3)
            window.prepare_run(str(target))
            def complete(code, status):
                window.grab().save(str(target / 'results-preview.png'))
                success = code == 0 and status == QProcess.NormalExit and (window.output_path / 'run.json').exists() and not window.image.pixmap().isNull()
                QTimer.singleShot(0, lambda: app.exit(0 if success else 1))
            window.process.finished.connect(complete)
            window.process.errorOccurred.connect(lambda _: app.exit(1))
        QTimer.singleShot(0, exercise_workflow)
        QTimer.singleShot(180000, lambda: app.exit(1))
    if '--screenshot' in sys.argv:
        target = Path(sys.argv[sys.argv.index('--screenshot') + 1]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        def capture():
            window.select_step(0)
            window.grab().save(str(target / 'workflow-tiles.png'))
            window.select_step(2)
            app.processEvents()
            window.grab().save(str(target / 'inversion-parameters.png'))
            app.quit()
        QTimer.singleShot(300, capture)
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
