"""Windows-first desktop prototype. Worker mode also supports frozen builds."""
import json
import sys
from pathlib import Path
from core import PRESETS, Settings, load_csv, run_inversion
from runtime import configure_runtime, redirect_worker_log, resource_path


def main():
    from PySide6.QtCore import QProcess, QTimer, Qt, QUrl, QSize, QThread, Signal
    from PySide6.QtGui import QPixmap, QDesktopServices
    from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout,
        QVBoxLayout, QLabel, QPushButton, QToolButton, QGridLayout, QGroupBox, QCheckBox, QStyle, QStackedWidget, QFileDialog,
        QComboBox, QDoubleSpinBox, QSpinBox, QFormLayout, QTextEdit, QLineEdit,
        QMessageBox, QScrollArea, QSizePolicy, QTableWidget, QTableWidgetItem, QDialog, QInputDialog)

    from engine_packs import ENGINES, engine_path, install_pack, PACK_PAGE
    from survey_io import write_csv, read_bert, read_res2dinv_wenner

    class PackInstaller(QThread):
        done = Signal(str)
        failed = Signal(str)
        def __init__(self, path, parent):
            super().__init__(parent)
            self.path = path
        def run(self):
            try: self.done.emit(install_pack(self.path))
            except Exception as exc: self.failed.emit(str(exc))

    class ChatWorker(QThread):
        done = Signal(object)
        failed = Signal(str)
        def __init__(self, key, prompt, state, history, parent):
            super().__init__(parent)
            self.key,self.prompt,self.state,self.history = key,prompt,state,history
        def run(self):
            from ai_client import request_reply,AssistantError
            try: self.done.emit(request_reply(self.key,self.prompt,self.state,self.history))
            except AssistantError as exc: self.failed.emit(str(exc))
            except Exception: self.failed.emit('The AI request could not be completed. No changes were applied.')
            finally: self.key = None

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
            self.import_report = {}
            self.active_output = None
            self.batch_results = {}
            self.result_paths = {}
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
                       'Import standard CSV, map delimited tables, or convert BERT and RES2DINV Wenner files. '
                       'Every engine receives the same validated positions, apparent resistivity and errors.')
            self.source = QLabel('No survey selected')
            box.addWidget(self.source)
            button = QPushButton('Import or convert a survey…')
            button.clicked.connect(self.import_data)
            box.addWidget(button)
            self.inputs.append(button)
            mapped = QPushButton('Map columns and units for any table…')
            mapped.clicked.connect(self.map_table)
            box.addWidget(mapped)
            self.inputs.append(mapped)
            self.sample_catalog = json.loads(resource_path('examples/catalog.json').read_text(encoding='utf-8'))
            self.sample_choice = QComboBox()
            for sample in self.sample_catalog:
                self.sample_choice.addItem(sample['label'], sample)
            box.addWidget(self.sample_choice)
            self.sample_description = QLabel(self.sample_catalog[0]['description'] + ' All samples are synthetic.')
            self.sample_description.setWordWrap(True)
            box.addWidget(self.sample_description)
            self.sample_choice.currentIndexChanged.connect(lambda _: self.sample_description.setText(self.sample_choice.currentData()['description'] + ' All samples are synthetic.'))
            example = QPushButton('Load selected sample')
            example.clicked.connect(lambda: self.load_survey(str(resource_path('examples/' + self.sample_choice.currentData()['file']))))
            box.addWidget(example)
            self.inputs.extend([example, self.sample_choice])
            formats = QPushButton('Open sample files and conversion examples')
            formats.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(resource_path('examples')))))
            box.addWidget(formats)
            export = QPushButton('Save converted standard CSV…')
            export.clicked.connect(self.export_survey)
            box.addWidget(export)
            self.inputs.append(export)
            box.addStretch()

            box = page('Check data quality', 'Input checks reject missing, non-finite, non-positive resistivity, '
                       'invalid errors and degenerate electrode geometries. No measurements are silently removed. '
                       'Reciprocal analysis and interactive filtering are planned.')
            self.quality = QLabel('Import a survey to see validation results.')
            self.quality.setWordWrap(True)
            box.addWidget(self.quality)
            self.data_preview = QTableWidget(0, 6)
            self.data_preview.setHorizontalHeaderLabels(['A x (m)','B x (m)','M x (m)','N x (m)','ρa (ohm m)','Relative error'])
            self.data_preview.setEditTriggers(QTableWidget.NoEditTriggers)
            box.addWidget(self.data_preview, 1)

            box = page('Choose engines and inversion parameters', 'Select one or several engines. Runs use the same converted survey, '
                       'but mesh discretizations and objective functions differ. Compare the common fit metrics alongside the models. '
                       'Optional engines are downloaded from GitHub once and then run locally; survey data are never uploaded.')
            engines = QGroupBox('Inversion engines • select one or more')
            engine_box = QVBoxLayout(engines)
            self.engine_checks = {}
            for key, name in ENGINES.items():
                check = QCheckBox(name)
                check.setChecked(key == 'pygimli')
                self.engine_checks[key] = check
                engine_box.addWidget(check)
                self.inputs.append(check)
            note = QLabel('pyGIMLi: smooth or blocky, with optional robust weighting. SimPEG: smooth L2 log-resistivity. '
                          'PyHydroGeophysX: smooth ERT using pyGIMLi forward modelling and its own solver/stopping rules. '
                          'λ values do not have identical numerical meaning across engines.')
            note.setWordWrap(True);engine_box.addWidget(note)
            get_packs = QPushButton('Get optional engine packs from GitHub')
            get_packs.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(PACK_PAGE)))
            engine_box.addWidget(get_packs)
            self.install_pack_button = QPushButton('Install downloaded engine-pack ZIP…')
            self.install_pack_button.clicked.connect(self.choose_engine_pack)
            engine_box.addWidget(self.install_pack_button)
            self.inputs.append(self.install_pack_button)
            box.addWidget(engines)
            self.refresh_engines()
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
            form.addRow('pyGIMLi model preset', self.preset)
            self.inputs.append(self.preset)
            self.lam = number(form, 'regularization', 'Regularization strength λ', 0.01, 100000, 20,
                              'Higher values penalize model roughness more strongly.')
            self.start = number(form, 'start_resistivity', 'Starting resistivity (ohm m)', 0.01, 1000000, 100,
                                'Uniform resistivity used to start the inversion.')
            number(form, 'vertical_weight', 'Vertical smoothing (pyGIMLi)', 0.01, 1, 1,
                   'Ratio of vertical to horizontal roughness weighting.')
            number(form, 'lambda_factor', 'λ multiplier per iteration', 0.01, 1, 1,
                   '1 keeps λ constant; below 1 gradually relaxes regularization.')

            form = section('Data weighting', 'Keep supplied CSV errors or set a minimum uncertainty. Robust data '
                           'weighting reduces the influence of large residuals; it does not remove bad measurements.')
            self.robust_data = QCheckBox('pyGIMLi: robust data weighting (IRLS)')
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
            number(form, 'min_phi_change', 'pyGIMLi minimum improvement (%)', 0, 100, 1,
                   'Stop when relative objective improvement falls below this percentage after the initial iterations.')
            self.stop_at_chi_one = QCheckBox('pyGIMLi: stop when χ² reaches 1 or less')
            self.stop_at_chi_one.setChecked(True)
            form.addRow(self.stop_at_chi_one)
            self.inputs.append(self.stop_at_chi_one)
            self.hydro_solver = QComboBox()
            self.hydro_solver.addItems(['cgls', 'lsqr'])
            self.hydro_solver.setToolTip('Linear update solver for PyHydroGeophysX only. Its upstream stopping rule is χ² < 1.5 or < 1% change.')
            form.addRow('PyHydroGeophysX linear solver', self.hydro_solver)
            self.inputs.append(self.hydro_solver)
            scope = QLabel('The preset, robust data weighting, vertical smoothing and stopping checkboxes above apply only to pyGIMLi. '
                           'SimPEG uses its native voltage-data target χ² = 1; PyHydroGeophysX uses its upstream fixed stopping rules.')
            scope.setWordWrap(True);box.addWidget(scope)
            reset = QPushButton('Restore recommended defaults')
            reset.clicked.connect(self.reset_parameters)
            box.addWidget(reset)
            self.inputs.append(reset)
            box.addStretch()

            box = page('Run inversion', 'Runs locally in a separate process. Choose a new results folder for '
                       'each run. Selected engines run sequentially to limit memory usage. Cancelling stops the current and pending engines; completed results remain available.')
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
                       'context together. Each engine saves its model, predicted data, settings and available diagnostics.')
            self.summary = QLabel('Complete an inversion to view results.')
            self.summary.setWordWrap(True)
            box.addWidget(self.summary)
            self.result_choice = QComboBox()
            self.result_choice.currentIndexChanged.connect(self.show_selected_result)
            box.addWidget(self.result_choice)
            self.comparison = QTableWidget(0, 4)
            self.comparison.setHorizontalHeaderLabels(['Engine','Status','Common log χ²','Relative RMS (%)'])
            self.comparison.setEditTriggers(QTableWidget.NoEditTriggers)
            self.comparison.setMaximumHeight(145)
            box.addWidget(self.comparison)
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
            sidebar.addWidget(QLabel('AI assistant • GPT-5.6 Luna'))
            from ai_settings import read_preferences
            from ai_credentials import read_key
            self.ai_preferences = read_preferences()
            try: self.ai_key = read_key()
            except OSError: self.ai_key = None
            self.ai_history = [];self.ai_pending = None;self.ai_requests = 0;self.ai_tokens = 0
            self.ai_worker = None
            self.ai_settings_button = QPushButton('AI Settings…')
            self.ai_settings_button.clicked.connect(self.open_ai_settings)
            sidebar.addWidget(self.ai_settings_button)
            self.chat = QTextEdit()
            self.chat.setReadOnly(True)
            self.chat.setPlainText('Open AI Settings to enter your existing key and enable natural-language help. '
                                   'Try “Explain the error floor” or “Set λ to 30 and open configuration”. '
                                   'Changes are proposed for your approval. Fixed navigation commands work without API access.')
            sidebar.addWidget(self.chat, 1)
            self.prompt = QLineEdit()
            self.prompt.setPlaceholderText('Where would you like to go?')
            self.prompt.returnPressed.connect(self.navigate)
            sidebar.addWidget(self.prompt)
            send = QPushButton('Send');self.ai_send = send
            send.clicked.connect(self.navigate)
            sidebar.addWidget(send)
            self.ai_apply = QPushButton('Review and apply proposed changes')
            self.ai_apply.setEnabled(False);self.ai_apply.clicked.connect(lambda: self.apply_ai_actions())
            sidebar.addWidget(self.ai_apply)
            clear = QPushButton('Clear conversation');self.ai_clear = clear
            clear.clicked.connect(self.clear_ai_chat);sidebar.addWidget(clear)
            self.ai_usage = QLabel('Offline commands ready • AI disabled')
            self.ai_usage.setWordWrap(True);sidebar.addWidget(self.ai_usage)
            side = QWidget()
            side.setLayout(sidebar)
            side.setFixedWidth(310)
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
            self.hydro_solver.setCurrentText(defaults.hydro_solver)
            self.refresh_bounds()

        def current_settings(self, validate=True):
            values = {key: control.value() for key, control in self.parameter_controls.items()}
            values['error_floor'] /= 100
            for key in ('mesh_depth', 'max_cell_area'):
                values[key] = values[key] or None
            if not self.use_bounds.isChecked():
                values['lower_resistivity'] = values['upper_resistivity'] = None
            settings = Settings(preset=self.preset.currentText(), max_iterations=self.iterations.value(),
                                robust_data=self.robust_data.isChecked(),
                                stop_at_chi_one=self.stop_at_chi_one.isChecked(), hydro_solver=self.hydro_solver.currentText(), **values)
            if validate: settings.validate()
            return settings

        def refresh_engines(self):
            import os
            developer = not getattr(sys, 'frozen', False) and bool(os.environ.get('ERT_ENGINE_TEST_PYTHON'))
            for engine, check in self.engine_checks.items():
                available = engine == 'pygimli' or engine_path(engine) is not None or developer
                check.setEnabled(available)
                check.setText(ENGINES[engine] + (' • included' if engine == 'pygimli' else ' • installed' if available else ' • download optional pack'))
                if not available: check.setChecked(False)

        def choose_engine_pack(self):
            path, _ = QFileDialog.getOpenFileName(self, 'Choose an official engine-pack ZIP', '', 'Engine pack (*.zip)')
            if not path: return
            self.install_pack_button.setEnabled(False)
            self.run.setEnabled(False)
            self.statusBar().showMessage('Checking and installing engine pack…')
            self.pack_installer = PackInstaller(path, self)
            self.pack_installer.done.connect(self.pack_installed)
            self.pack_installer.failed.connect(self.pack_failed)
            self.pack_installer.start()

        def pack_installed(self, engine):
            self.refresh_engines()
            self.engine_checks[engine].setChecked(True)
            self.install_pack_button.setEnabled(True);self.run.setEnabled(True)
            self.statusBar().showMessage(ENGINES[engine] + ' engine pack installed; ready for local inversion')

        def pack_failed(self, error):
            self.install_pack_button.setEnabled(True);self.run.setEnabled(True)
            QMessageBox.warning(self, 'Engine pack could not be installed', error)
            self.statusBar().showMessage('Engine installation failed')

        def selected_engines(self):
            selected = [engine for engine, check in self.engine_checks.items() if check.isChecked()]
            if not selected: raise ValueError('Select at least one inversion engine.')
            import os
            developer = not getattr(sys, 'frozen', False) and bool(os.environ.get('ERT_ENGINE_TEST_PYTHON'))
            for engine in selected:
                if engine != 'pygimli' and engine_path(engine) is None and not developer:
                    raise ValueError('Install the ' + ENGINES[engine] + ' optional engine pack first.')
            return selected

        def import_data(self):
            path, _ = QFileDialog.getOpenFileName(self, 'Import or convert survey', '', 'Survey files (*.csv *.tsv *.txt *.ohm *.dat);;All files (*)')
            if not path: return
            try:
                try:
                    rows = load_csv(path)
                    report = {'source': Path(path).name, 'format': 'Standard CSV', 'estimated_errors': False}
                except (ValueError, UnicodeError):
                    if Path(path).suffix.lower() in ('.ohm', '.dat'):
                        formats = ['BERT electrode/measurement file', 'RES2DINV Wenner alpha', 'Delimited table with column mapping']
                        default = 0 if Path(path).read_text(encoding='utf-8-sig').splitlines()[0].strip().isdigit() else 1
                        choice, ok = QInputDialog.getItem(self, 'Choose survey format', 'Input format', formats, default, False)
                        if not ok: return
                        if choice in formats[:2]:
                            error, ok = QInputDialog.getDouble(self, 'Error estimate', 'Fallback relative error (%) if not supplied', 3, .01, 99, 2)
                            if not ok: return
                            rows, report = (read_bert if choice == formats[0] else read_res2dinv_wenner)(path, default_error=error/100)
                        else:
                            rows, report = self.convert_dialog(path)
                    else:
                        rows, report = self.convert_dialog(path)
                if rows is not None: self.accept_survey(path, rows, report)
            except Exception as exc:
                QMessageBox.warning(self, 'Survey could not be imported', str(exc))

        def map_table(self):
            path, _ = QFileDialog.getOpenFileName(self, 'Map table columns and units', '', 'Tables (*.csv *.tsv *.txt)')
            if not path: return
            try:
                rows, report = self.convert_dialog(path)
                if rows is not None: self.accept_survey(path, rows, report)
            except Exception as exc: QMessageBox.warning(self, 'Conversion failed', str(exc))

        def convert_dialog(self, path):
            from import_dialog import ImportDialog
            dialog = ImportDialog(path, self)
            if dialog.exec() == QDialog.Accepted: return dialog.rows, dialog.report
            return None, None

        def load_survey(self, path):
            try:
                self.accept_survey(path, load_csv(path), {'source': Path(path).name, 'format': 'Standard CSV', 'estimated_errors': False})
            except Exception as exc:
                QMessageBox.warning(self, 'Survey could not be imported', str(exc))

        def accept_survey(self, path, rows, report):
            self.input_path, self.rows, self.import_report = path, rows, report
            self.output_path = None;self.active_output = None
            self.image.clear();self.result_choice.clear();self.result_paths = {};self.batch_results = {}
            self.comparison.setRowCount(0)
            self.summary.setText('Complete an inversion for the newly imported survey.')
            self.source.setText(path)
            electrodes = {row[key] for row in rows for key in ('ax', 'bx', 'mx', 'nx')}
            self.quality.setText(f'{len(rows)} measurements • {len(electrodes)} electrodes\n'
                                 f'Profile: {min(electrodes):g} to {max(electrodes):g} m\n'
                                 + ('Errors were estimated during conversion. ' if report.get('estimated_errors') else '')
                                 + 'Input checks passed. Preview shows the first 100 measurements; units are metres, ohm m, fractional errors.')
            from core import COLUMNS
            shown = rows[:100];self.data_preview.setRowCount(len(shown))
            for i, row in enumerate(shown):
                for j, key in enumerate(COLUMNS): self.data_preview.setItem(i, j, QTableWidgetItem(f'{row[key]:.7g}'))
            self.select_step(1)

        def export_survey(self):
            if not self.rows:
                QMessageBox.information(self, 'Import required', 'Import or convert a survey first.');return
            path, _ = QFileDialog.getSaveFileName(self, 'Export common interchange CSV', 'converted-survey.csv', 'CSV (*.csv)')
            if path:
                try:
                    write_csv(path, self.rows)
                    Path(path + '.import.json').write_text(json.dumps(self.import_report, indent=2), encoding='utf-8')
                except OSError as exc: QMessageBox.warning(self, 'Export failed', str(exc))

        def start_run(self):
            if not self.rows:
                QMessageBox.information(self, 'Import required', 'Import and check a survey first.')
                return
            try:
                self.current_settings()
                self.selected_engines()
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
            settings = self.current_settings()
            self.pending_engines = self.selected_engines()
            self.output_path = Path(mkdtemp(prefix='ert-run-', dir=folder))
            self.batch_results = {engine: {'status': 'pending'} for engine in self.pending_engines}
            self.result_paths = {};self.result_choice.clear();self.image.clear()
            write_csv(self.output_path / 'survey.csv', self.rows)
            (self.output_path / 'settings.json').write_text(json.dumps(asdict(settings)), encoding='utf-8')
            (self.output_path / 'import-report.json').write_text(json.dumps(self.import_report, indent=2), encoding='utf-8')
            self.summary.setText('Inversion batch running…')
            self.log.clear();self.cancelled = False
            for widget in self.inputs: widget.setEnabled(False)
            self.cancel.setEnabled(True)
            self.start_next_engine()

        def start_next_engine(self):
            if not self.pending_engines or self.cancelled:
                self.finish_batch();return
            import shutil
            self.active_engine = self.pending_engines.pop(0)
            self.active_output = self.output_path / self.active_engine
            self.active_output.mkdir()
            for name in ('survey.csv', 'settings.json'):
                shutil.copy2(self.output_path / name, self.active_output / name)
            self.batch_results[self.active_engine]['status'] = 'running'
            self.log.append('\n=== ' + ENGINES[self.active_engine] + ' ===')
            self.log_offset = 0;self.log_timer.start()
            self.process = QProcess(self)
            self.process.setProcessChannelMode(QProcess.MergedChannels)
            self.process.readyReadStandardOutput.connect(self.read_log)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.process_error)
            if self.active_engine == 'pygimli':
                program = sys.executable
                args = ['--worker', str(self.active_output)]
                if not getattr(sys, 'frozen', False): args.insert(0, str(Path(__file__).resolve()))
            else:
                executable = engine_path(self.active_engine)
                if executable:
                    program, args = str(executable), ['--worker', str(self.active_output)]
                else:
                    import os
                    program = os.environ['ERT_ENGINE_TEST_PYTHON']
                    args = [str(Path(__file__).resolve()), '--engine-worker', self.active_engine, str(self.active_output)]
            self.process.start(program, args)
            self.statusBar().showMessage('Inverting with ' + ENGINES[self.active_engine] + ' • see live solver output')

        def read_log(self):
            if self.process:
                self.log.insertPlainText(bytes(self.process.readAllStandardOutput()).decode('utf-8', errors='replace'))
            if self.active_output and (self.active_output / 'solver.log').exists():
                with (self.active_output / 'solver.log').open('rb') as stream:
                    stream.seek(self.log_offset);chunk = stream.read();self.log_offset = stream.tell()
                self.log.insertPlainText(chunk.decode('utf-8', errors='replace'))
            self.log.ensureCursorVisible()

        def process_error(self, error):
            if error == QProcess.FailedToStart:
                self.log.append(self.process.errorString())
                self.finished(-1, QProcess.CrashExit)

        def cancel_run(self):
            self.cancelled = True
            for engine in self.pending_engines: self.batch_results[engine]['status'] = 'cancelled'
            self.pending_engines = []
            if self.process and self.process.state() != QProcess.NotRunning: self.process.kill()

        def finished(self, code, status):
            self.log_timer.stop();self.read_log()
            if code == 0 and status == QProcess.NormalExit and not self.cancelled:
                try:
                    result = json.loads((self.active_output / 'run.json').read_text(encoding='utf-8'))
                    common = json.loads((self.active_output / 'comparison_metrics.json').read_text(encoding='utf-8'))
                    self.batch_results[self.active_engine] = {'status': 'completed', **common}
                    self.result_paths[self.active_engine] = self.active_output
                except Exception as exc:
                    self.batch_results[self.active_engine] = {'status': 'failed', 'error': str(exc)}
            else:
                self.batch_results[self.active_engine] = {'status': 'cancelled' if self.cancelled else 'failed', 'error': 'See engine solver.log'}
            self.process.deleteLater();self.process = None
            self.start_next_engine()

        def finish_batch(self):
            import csv
            (self.output_path / 'batch.json').write_text(json.dumps(self.batch_results, indent=2), encoding='utf-8')
            with (self.output_path / 'comparison.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream);writer.writerow(['engine', 'status', 'common_log_chi_squared', 'relative_rms_percent'])
                for engine, result in self.batch_results.items():
                    writer.writerow([engine, result['status'], result.get('common_log_chi_squared', ''), result.get('relative_rms_percent', '')])
            self.comparison.setRowCount(len(self.batch_results))
            self.result_choice.clear()
            for i, (engine, result) in enumerate(self.batch_results.items()):
                values = [ENGINES[engine], result['status'], f"{result['common_log_chi_squared']:.4g}" if 'common_log_chi_squared' in result else '—',
                          f"{result['relative_rms_percent']:.3f}" if 'relative_rms_percent' in result else '—']
                for j, value in enumerate(values): self.comparison.setItem(i, j, QTableWidgetItem(value))
                if engine in self.result_paths: self.result_choice.addItem(ENGINES[engine], engine)
            for widget in self.inputs: widget.setEnabled(True)
            self.refresh_bounds();self.refresh_engines();self.cancel.setEnabled(False)
            completed = len(self.result_paths)
            self.summary.setText(f'{completed}/{len(self.batch_results)} engines completed. Results: {self.output_path}\n'
                                 'Common log χ² uses identical apparent-resistivity data/errors; native solver objectives differ. Check individual logs for failures.')
            self.show_selected_result();self.select_step(4)
            self.statusBar().showMessage('Cancelled' if self.cancelled else 'Batch complete' if completed == len(self.batch_results) else 'Batch completed with engine failures')
            if getattr(self, 'test_target', None):
                self.grab().save(str(self.test_target / 'results-preview.png'))
                ok = completed == len(self.batch_results) and not self.image.pixmap().isNull()
                QTimer.singleShot(0, lambda: QApplication.instance().exit(0 if ok else 1))

        def show_selected_result(self):
            if not hasattr(self, 'result_choice'): return
            engine = self.result_choice.currentData()
            if engine in self.result_paths:
                self.image.setPixmap(QPixmap(str(self.result_paths[engine] / 'model.png')).scaledToWidth(800, Qt.SmoothTransformation))

        def open_ai_settings(self):
            from ai_settings import AISettingsDialog
            dialog = AISettingsDialog(self.ai_key,self.ai_preferences,self)
            if dialog.exec() == QDialog.Accepted:
                self.ai_key,self.ai_preferences = dialog.result_key,dialog.result_preferences
                self.clear_ai_chat()
                self.ai_usage.setText('AI ready • GPT-5.6 Luna' if self.ai_preferences['enabled'] and self.ai_key else 'Offline commands ready • AI disabled')
            elif dialog.result_key is None:
                self.ai_key = None
                self.ai_usage.setText('Offline commands ready • no API key')
                self.clear_ai_chat()

        def clear_ai_chat(self):
            self.ai_history = [];self.ai_pending = None;self.ai_apply.setEnabled(False)
            self.chat.setPlainText('Conversation cleared. Your request counter is retained for this session.')

        def ai_state(self):
            from dataclasses import asdict
            import math
            stats = {'measurements':len(self.rows or []),'electrodes':len({r[k] for r in self.rows or [] for k in ('ax','bx','mx','nx')})}
            if self.rows:
                values = [r['rhoa'] for r in self.rows]
                stats.update(apparent_resistivity_min=min(values),apparent_resistivity_max=max(values))
            results = {}
            for engine,result in self.batch_results.items():
                results[engine] = {'status':result['status']}
                for key in ('common_log_chi_squared','relative_rms_percent'):
                    value=result.get(key)
                    if isinstance(value,(int,float)) and math.isfinite(value): results[engine][key]=value
            return dict(step=self.pages.currentIndex(),settings=asdict(self.current_settings(False)),survey=stats,
                        running=bool(self.process and self.process.state()!=QProcess.NotRunning),
                        engines={key:{'available':key=='pygimli' or engine_path(key) is not None,'selected':c.isChecked()} for key,c in self.engine_checks.items()},
                        results=results)

        def navigate(self):
            from ai_client import contains_key
            prompt=self.prompt.text().strip()
            if contains_key(prompt):
                self.prompt.clear()
                QMessageBox.information(self,'Use AI Settings','Enter API keys only in the masked AI Settings dialog.');return
            if not self.ai_preferences['enabled'] or not self.ai_key:
                self.offline_navigate();return
            if not prompt:return
            if self.ai_worker is not None:return
            if len(prompt)>2000:
                self.chat.append('Assistant: Please keep messages to 2,000 characters or less.');return
            if self.ai_requests>=self.ai_preferences['request_limit']:
                self.chat.append('Assistant: Session request limit reached. Review your usage and AI Settings.');return
            self.ai_pending=None;self.ai_apply.setEnabled(False)
            self.chat.setPlainText(self.chat.toPlainText()+'\nYou: '+prompt)
            self.prompt.clear()
            self.ai_snapshot=self.ai_state()
            self.ai_sent_prompt=prompt
            self.ai_requests+=1
            self.ai_send.setEnabled(False);self.prompt.setEnabled(False);self.ai_clear.setEnabled(False);self.ai_settings_button.setEnabled(False)
            self.ai_usage.setText('Thinking… • request '+str(self.ai_requests))
            self.ai_worker=ChatWorker(self.ai_key,prompt,self.ai_snapshot,list(self.ai_history),self)
            self.ai_worker.done.connect(self.ai_received)
            self.ai_worker.failed.connect(self.ai_failed)
            self.ai_worker.finished.connect(self.ai_finished)
            self.ai_worker.start()

        def ai_received(self, reply):
            from ai_client import STEPS
            self.ai_history.extend([{'role':'user','content':self.ai_sent_prompt},{'role':'assistant','content':reply['reply']}])
            self.ai_history=self.ai_history[-8:]
            self.ai_tokens+=reply['usage']['total_tokens']
            self.chat.setPlainText(self.chat.toPlainText()+'\nAssistant: '+reply['reply'])
            pending=[]
            for action in reply['actions']:
                if action['kind']=='navigate': self.select_step(STEPS.index(action['step']))
                else: pending.append(action)
            if pending:
                # Snapshot after safe navigation, before proposing scientific state changes.
                self.ai_pending=(pending,self.ai_state())
                self.ai_apply.setEnabled(True)
                self.chat.setPlainText(self.chat.toPlainText()+'\nProposed changes (not yet applied):\n'+self.ai_action_text(pending))

        def ai_failed(self, message):
            self.chat.setPlainText(self.chat.toPlainText()+'\nAssistant: '+message)

        def ai_finished(self):
            self.ai_worker.deleteLater();self.ai_worker=None
            for widget in (self.ai_send,self.prompt,self.ai_clear,self.ai_settings_button):widget.setEnabled(True)
            self.ai_usage.setText(f'Session: {self.ai_requests} requests • {self.ai_tokens} tokens reported by API')
            if getattr(self,'ai_test_callback',None):self.ai_test_callback()

        def ai_action_text(self, actions):
            lines=[]
            for action in actions:
                kind=action['kind']
                if kind=='set_parameters': lines.extend(change['name']+' = '+str(change['value']) for change in action['parameters'])
                elif kind=='select_engines':lines.append('Select engines: '+', '.join(action['engines']))
                elif kind=='load_sample':lines.append('Replace current survey with sample: '+action['sample'])
                elif kind=='start_run':lines.append('Start selected inversions (you will choose the output folder).')
            return '\n'.join(lines)

        def apply_ai_actions(self, confirmed=False):
            if not self.ai_pending:return
            actions,snapshot=self.ai_pending
            if self.ai_state()!=snapshot:
                self.ai_failed('The project changed after this proposal. Send your request again.');self.ai_pending=None;self.ai_apply.setEnabled(False);return
            if self.process is not None or getattr(self,'pack_installer',None) and self.pack_installer.isRunning():
                self.ai_failed('Wait until inversion or engine installation finishes before applying changes.');return
            from ai_client import validate_proposal,AssistantError
            try:
                proposal=validate_proposal({'reply':'','actions':actions},self.current_settings(False))
                for name,control in self.parameter_controls.items():
                    value=getattr(proposal['settings'],name)
                    if value is None:continue
                    display=value*100 if name=='error_floor' else value
                    if not control.minimum()<=display<=control.maximum() or abs(round(display,control.decimals())-display)>1e-9:
                        raise AssistantError(name+' is outside the supported UI range or precision. Ask for a supported value.')
                for action in actions:
                    if action['kind']=='select_engines' and any(not self.engine_checks[e].isEnabled() for e in action['engines']):
                        raise AssistantError('Install the requested optional engine pack first.')
            except AssistantError as exc:self.ai_failed(str(exc));return
            if not confirmed and QMessageBox.question(self,'Apply assistant proposal?',self.ai_action_text(actions))!=QMessageBox.Yes:return
            candidate=proposal['settings']
            for action in actions:
                if action['kind']=='load_sample':self.load_survey(str(resource_path('examples/'+action['sample']+'.csv')))
            if proposal['patch']:
                for key,control in self.parameter_controls.items():
                    value=getattr(candidate,key)
                    if key=='error_floor':value*=100
                    if value is None:value={'lower_resistivity':1,'upper_resistivity':100000}.get(key,0)
                    control.setValue(value)
                self.preset.setCurrentText(candidate.preset);self.iterations.setValue(candidate.max_iterations)
                self.robust_data.setChecked(candidate.robust_data);self.stop_at_chi_one.setChecked(candidate.stop_at_chi_one)
                self.hydro_solver.setCurrentText(candidate.hydro_solver);self.use_bounds.setChecked(candidate.lower_resistivity is not None)
                self.refresh_bounds()
            for action in actions:
                if action['kind']=='select_engines':
                    for engine,check in self.engine_checks.items():check.setChecked(engine in action['engines'])
            self.ai_pending=None;self.ai_apply.setEnabled(False)
            self.chat.setPlainText(self.chat.toPlainText()+'\nApplied the reviewed proposal.')
            if any(action['kind']=='start_run' for action in actions):self.select_step(3);self.start_run()

        def offline_navigate(self):
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
            if self.ai_worker is not None:
                QMessageBox.information(self,'AI request active','Wait for the current AI request to finish before closing.');event.ignore();return
            if getattr(self, 'pack_installer', None) and self.pack_installer.isRunning():
                QMessageBox.information(self, 'Installing engine', 'Wait for engine installation to finish.');event.ignore();return
            if self.process and self.process.state() != QProcess.NotRunning:
                QMessageBox.information(self, 'Run active', 'Cancel the inversion before closing.')
                event.ignore()
            else:
                event.accept()

    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = Window()
    window.show()
    if any(flag in sys.argv for flag in ('--smoke-test','--workflow-test','--multi-test','--conversion-test','--assistant-test')):
        window.ai_preferences['enabled']=False
        window.ai_key=None
    if '--workflow-test' in sys.argv or '--multi-test' in sys.argv:
        flag = '--multi-test' if '--multi-test' in sys.argv else '--workflow-test'
        target = Path(sys.argv[sys.argv.index(flag) + 1]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        def exercise_workflow():
            window.test_target = target
            for step, tile in enumerate(window.tiles):
                tile.click()
                assert window.pages.currentIndex() == step
                assert [button.isChecked() for button in window.tiles] == [i == step for i in range(5)]
            window.prompt.setText('configure inversion');window.navigate()
            assert window.pages.currentIndex() == 2
            window.parameter_controls['error_floor'].setValue(5)
            assert window.current_settings().error_floor == 0.05
            window.reset_parameters()
            assert window.current_settings() == Settings()
            window.load_survey(str(resource_path('examples/homogeneous.csv')))
            window.start.setValue(80);window.iterations.setValue(5)
            if flag == '--multi-test':
                for check in window.engine_checks.values(): check.setChecked(True)
                window.parameter_controls['mesh_depth'].setValue(4)
                window.parameter_controls['max_cell_area'].setValue(.5)
            else:
                window.robust_data.setChecked(True);window.stop_at_chi_one.setChecked(False);window.use_bounds.setChecked(True)
                for key, value in dict(error_floor=5, lower_resistivity=50, upper_resistivity=200,
                                       mesh_depth=4, max_cell_area=.5, vertical_weight=.7, lambda_factor=.9, min_phi_change=.5).items():
                    window.parameter_controls[key].setValue(value)
            window.select_step(3);window.prepare_run(str(target))
        QTimer.singleShot(0, exercise_workflow)
        QTimer.singleShot(180000, lambda: app.exit(1))
    if '--assistant-test' in sys.argv:
        target=Path(sys.argv[sys.argv.index('--assistant-test')+1]).resolve();target.mkdir(parents=True,exist_ok=True)
        def test_ai():
            import ai_client
            from unittest.mock import patch
            def action(kind,**kwargs):return {'kind':kind,'step':None,'sample':None,'engines':[],'parameters':[],**kwargs}
            calls=[]
            def fake(key,prompt,state,history):
                assert 'rows' not in state and 'input_path' not in state
                calls.append(prompt)
                proposal={'reply':'I propose λ = 30 and a 5% error floor.', 'actions':[
                    action('navigate',step='configure'),action('set_parameters',parameters=[{'name':'regularization','value':30},{'name':'error_floor','value':.05}])]}
                validated=ai_client.validate_proposal(proposal,Settings(**state['settings']))
                validated['usage']={'input_tokens':100,'output_tokens':100,'total_tokens':200}
                return validated
            window.ai_key='sk-test-not-a-real-key';window.ai_preferences={'enabled':True,'request_limit':1}
            window.ai_mock=patch('ai_client.request_reply',fake);window.ai_mock.start()
            def checked():
                assert window.pages.currentIndex()==2 and window.current_settings().regularization==20
                assert window.ai_pending and window.ai_apply.isEnabled()
                window.apply_ai_actions(confirmed=True)
                assert window.current_settings().regularization==30 and window.current_settings().error_floor==.05
                assert not window.ai_pending and window.ai_tokens==200
                stale=window.ai_state()
                window.ai_pending=([action('set_parameters',parameters=[{'name':'regularization','value':40}])],stale)
                window.lam.setValue(31)
                window.apply_ai_actions(confirmed=True)
                assert window.lam.value()==31 and window.ai_pending is None
                window.ai_pending=([action('start_run')],window.ai_state())
                starts=[];window.start_run=lambda:starts.append(True)
                with patch.object(QMessageBox,'question',return_value=QMessageBox.No):window.apply_ai_actions()
                assert not starts
                window.apply_ai_actions(confirmed=True)
                assert len(starts)==1
                window.prompt.setText('another request');window.navigate()
                assert len(calls)==1
                window.ai_mock.stop();window.ai_key=None
                (target/'report.json').write_text(json.dumps({'status':'passed','network_calls':0,'requests':len(calls)}))
                app.quit()
            window.ai_test_callback=checked
            window.prompt.setText('Set lambda to 30 and error floor to 5 percent');window.navigate()
        QTimer.singleShot(0,test_ai)
        QTimer.singleShot(15000,lambda:app.exit(1))
    if '--conversion-test' in sys.argv:
        target = Path(sys.argv[sys.argv.index('--conversion-test') + 1]).resolve()
        target.mkdir(parents=True, exist_ok=True)
        def test_conversions():
            from import_dialog import ImportDialog
            from core import COLUMNS
            reference = load_csv(resource_path('examples/conductive_block.csv'))
            for name in ('resistance_percent.tsv','voltage_current.csv','electrode_ids.csv'):
                dialog = ImportDialog(str(resource_path('examples/' + name)), window)
                if name == 'voltage_current.csv':
                    dialog.voltage.setCurrentIndex(1);dialog.current.setCurrentIndex(1)
                if name == 'electrode_ids.csv':
                    assert dialog.coordinates.currentIndex() == 0
                    dialog.coordinates.setCurrentIndex(2)
                    dialog.electrodes.setText(str(resource_path('examples/electrodes.csv')))
                dialog.preview()
                assert dialog.rows and len(dialog.rows) == len(reference)
                assert all(abs(a[key] - b[key]) < 1e-9 for a,b in zip(dialog.rows, reference) for key in COLUMNS)
                write_csv(target / (name + '.converted.csv'), dialog.rows)
            for name in ('homogeneous','conductive_block','resistive_block','layered'):
                assert load_csv(resource_path('examples/' + name + '.csv'))
            for reader, name in ((read_bert,'conductive_block.ohm'),(read_res2dinv_wenner,'wenner_res2dinv.dat')):
                rows, report = reader(resource_path('examples/' + name))
                assert all(abs(a[key]-b[key]) < 1e-9 for a,b in zip(rows, reference) for key in COLUMNS)
            (target / 'report.json').write_text(json.dumps({'converted_formats':5,'sample_surveys':4,'status':'passed'}))
            app.quit()
        QTimer.singleShot(0, test_conversions)
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
    elif len(sys.argv) == 4 and sys.argv[1] == '--engine-worker':
        folder = Path(sys.argv[3]).resolve()
        stream = redirect_worker_log(folder)
        try: run_inversion(folder / 'survey.csv', folder, Settings(**json.loads((folder / 'settings.json').read_text())), backend=sys.argv[2])
        except Exception:
            traceback.print_exc();sys.exit(1)
        finally: stream.flush()
    elif len(sys.argv) == 3 and sys.argv[1] == '--install-pack':
        from engine_packs import install_pack
        try: install_pack(sys.argv[2])
        except Exception:
            (runtime_folder / 'pack-install-error.log').write_text(traceback.format_exc(), encoding='utf-8')
            sys.exit(1)
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
