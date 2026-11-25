"""Column mapping, unit conversion and preview before accepting a survey."""
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QComboBox,QDoubleSpinBox,
    QLineEdit,QPushButton,QDialogButtonBox,QLabel,QTableWidget,QTableWidgetItem,QFileDialog,QMessageBox)
from survey_io import table,suggest_mapping,ImportOptions,convert_table
from core import COLUMNS


class ImportDialog(QDialog):
    def __init__(self,path,parent=None):
        super().__init__(parent)
        self.setWindowTitle('Convert survey to the ERT interchange format')
        self.resize(900,740)
        self.path=path;self.rows=None;self.report=None
        headers,_=table(path)
        suggested=suggest_mapping(headers)
        box=QVBoxLayout(self)
        help_label=QLabel('Map your columns, specify their physical meaning and units, then preview the conversion. '
            'The result uses electrode positions in metres, apparent resistivity in ohm m and fractional relative errors. '
            'Flat 2D surveys only; no rows are silently discarded.')
        help_label.setWordWrap(True);box.addWidget(help_label)
        form=QFormLayout();box.addLayout(form)
        self.mapping={}
        labels={'ax':'A current electrode','bx':'B current electrode','mx':'M potential electrode','nx':'N potential electrode',
                'value':'Measurement','current':'Current (for voltage/current)','error':'Relative error (optional)'}
        for key,label in labels.items():
            combo=QComboBox();combo.addItems(['Not supplied',*headers]);combo.setCurrentText(suggested[key] or 'Not supplied')
            form.addRow(label,combo);self.mapping[key]=combo
            combo.currentIndexChanged.connect(self.invalidate)
        def choice(label,items):
            combo=QComboBox();combo.addItems(items);form.addRow(label,combo);combo.currentIndexChanged.connect(self.invalidate);return combo
        self.coordinates=choice('Electrode columns represent',['Choose interpretation…','Horizontal positions','Electrode IDs'])
        if all(suggested[key].lower() in (key,key[0]+'_x','x'+key[0]) for key in COLUMNS[:4]): self.coordinates.setCurrentIndex(1)
        self.position_unit=choice('Position units',['metres','centimetres','feet'])
        self.value_mode=choice('Measurement meaning',['Apparent resistivity (ohm m)','Resistance (ohm)','Voltage / current'])
        if suggested['value'].lower() in ('r','resistance'): self.value_mode.setCurrentIndex(1)
        if suggested['value'].lower() in ('u','voltage','v'): self.value_mode.setCurrentIndex(2)
        self.voltage=choice('Voltage units',['V','mV']);self.current=choice('Current units',['A','mA'])
        self.error_mode=choice('Error units',['Fraction (0.03 = 3%)','Percent (3 = 3%)'])
        if 'pct' in suggested['error'].lower() or 'percent' in suggested['error'].lower(): self.error_mode.setCurrentIndex(1)
        self.default_error=QDoubleSpinBox();self.default_error.setRange(.01,99);self.default_error.setValue(3);self.default_error.setSuffix(' %')
        form.addRow('Error estimate if no error column',self.default_error);self.default_error.valueChanged.connect(self.invalidate)
        self.electrodes=QLineEdit();self.electrodes.setPlaceholderText('Required for IDs: CSV with id,x headers; y,z must be zero if provided')
        form.addRow('Electrode position file',self.electrodes);self.electrodes.textChanged.connect(self.invalidate)
        select=QPushButton('Choose electrode position table…');select.clicked.connect(self.choose_electrodes);box.addWidget(select)
        preview=QPushButton('Validate and preview conversion');preview.clicked.connect(self.preview);box.addWidget(preview)
        self.status=QLabel('No conversion applied yet.');self.status.setWordWrap(True);box.addWidget(self.status)
        self.preview_table=QTableWidget(0,len(COLUMNS));self.preview_table.setHorizontalHeaderLabels(COLUMNS);box.addWidget(self.preview_table,1)
        self.buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText('Use converted survey')
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept);self.buttons.rejected.connect(self.reject);box.addWidget(self.buttons)

    def invalidate(self,*_):
        self.rows=None
        if hasattr(self,'buttons'):
            self.buttons.button(QDialogButtonBox.Ok).setEnabled(False)
            self.status.setText('Settings changed. Validate and preview again before importing.')

    def choose_electrodes(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose electrode table','','Tables (*.csv *.tsv *.txt)')
        if path:self.electrodes.setText(path)

    def preview(self):
        try:
            if self.coordinates.currentIndex()==0:raise ValueError('Choose whether the electrode columns contain positions or electrode IDs.')
            mapping={key:combo.currentText() if combo.currentIndex()>0 else '' for key,combo in self.mapping.items()}
            options=ImportOptions(coordinate_mode='positions' if self.coordinates.currentIndex()==1 else 'indices',
                position_scale=[1,.01,.3048][self.position_unit.currentIndex()],value_mode=['rhoa','resistance','voltage_current'][self.value_mode.currentIndex()],
                voltage_scale=[1,.001][self.voltage.currentIndex()],current_scale=[1,.001][self.current.currentIndex()],
                error_percent=bool(self.error_mode.currentIndex()),default_error=self.default_error.value()/100,
                electrode_file=self.electrodes.text() or None)
            self.rows,self.report=convert_table(self.path,mapping,options)
        except Exception as exc:
            QMessageBox.warning(self,'Conversion needs attention',str(exc));return
        shown=self.rows[:100];self.preview_table.setRowCount(len(shown))
        for i,row in enumerate(shown):
            for j,key in enumerate(COLUMNS):self.preview_table.setItem(i,j,QTableWidgetItem(f'{row[key]:.7g}'))
        self.status.setText(f'{len(self.rows)} measurements validated; showing the first {len(shown)}. '+
                            ('Errors were estimated from your selected default.' if self.report['estimated_errors'] else 'Supplied errors were converted to relative fractions.'))
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(True)
