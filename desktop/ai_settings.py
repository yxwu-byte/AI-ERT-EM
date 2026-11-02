"""Local API configuration; only preferences are saved as JSON."""
import json
import os
from pathlib import Path
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QFormLayout,QLabel,QLineEdit,QCheckBox,
    QSpinBox,QPushButton,QDialogButtonBox,QFileDialog,QMessageBox)
from ai_client import MODEL
from ai_credentials import save_key,delete_key
from runtime import configure_runtime


def read_preferences():
    try:
        data=json.loads((configure_runtime()/'ai-settings.json').read_text(encoding='utf-8'))
        return {'enabled':data.get('enabled') is True,'request_limit':max(1,min(1000,int(data.get('request_limit',50))))}
    except (OSError,ValueError,TypeError,AttributeError): return {'enabled':False,'request_limit':50}


def import_key_file(path):
    import re
    text=Path(path).read_text(encoding='utf-8-sig')
    for line in text.splitlines():
        match=re.match(r'^\s*(?:export\s+)?OPENAI_API_KEY\s*=\s*(.*?)\s*$',line)
        if match:
            value=match.group(1).strip().strip('\"\'')
            if value.startswith('sk-') and len(value)>24 and not any(c.isspace() for c in value): return value
    raise ValueError('This file does not contain a usable OPENAI_API_KEY entry.')


class AISettingsDialog(QDialog):
    def __init__(self,current_key,preferences,parent=None):
        super().__init__(parent)
        self.setWindowTitle('AI assistant settings');self.resize(540,410)
        self.result_key=current_key;self.result_preferences=dict(preferences)
        box=QVBoxLayout(self)
        info=QLabel('Use your existing OpenAI Platform API key. Messages and a summary of settings, survey counts and '
            'fit metrics are sent to OpenAI when you press Send. Anything you type is sent; survey files, raw rows, '
            'file paths and solver logs are not uploaded automatically. Usage is billed to your API project.')
        info.setWordWrap(True);box.addWidget(info)
        form=QFormLayout();box.addLayout(form)
        form.addRow('Model',QLabel(MODEL+' • low reasoning • bounded replies'))
        self.enabled=QCheckBox('Enable API assistant');self.enabled.setChecked(preferences['enabled']);form.addRow(self.enabled)
        self.key=QLineEdit();self.key.setEchoMode(QLineEdit.Password)
        self.key.setPlaceholderText('Key available; leave blank to keep it' if current_key else 'Enter existing key locally; never paste into chat')
        form.addRow('OpenAI API key',self.key)
        self.remember=QCheckBox('Remember using Windows Credential Manager');self.remember.setEnabled(os.name=='nt')
        form.addRow(self.remember)
        self.limit=QSpinBox();self.limit.setRange(1,1000);self.limit.setValue(preferences['request_limit'])
        form.addRow('Request limit per app session',self.limit)
        help_label=QLabel('The request limit is a local guard, not a dollar budget. Set project budgets and alerts in OpenAI Platform. '
                         'Without Remember, a newly entered key stays only in memory until the app closes. Keys never enter the installer or GitHub.')
        help_label.setWordWrap(True);box.addWidget(help_label)
        imported=QPushButton('Import existing key from a local .env file…');imported.clicked.connect(self.import_file);box.addWidget(imported)
        forget=QPushButton('Forget locally saved key');forget.clicked.connect(self.forget);box.addWidget(forget)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);box.addWidget(buttons)

    def import_file(self):
        path,_=QFileDialog.getOpenFileName(self,'Choose a local key file','','Environment files (*.env .env*);;All files (*)')
        if not path:return
        try:self.key.setText(import_key_file(path))
        except (OSError,ValueError):QMessageBox.warning(self,'Key import failed','Could not read a usable OPENAI_API_KEY. No file contents were logged.')

    def forget(self):
        try:delete_key()
        except OSError as exc:QMessageBox.warning(self,'Could not forget key',str(exc));return
        self.result_key=None;self.key.clear();self.enabled.setChecked(False)
        self.key.setPlaceholderText('Enter existing key locally')

    def save(self):
        value=self.key.text().strip() or self.result_key
        if self.enabled.isChecked() and (not value or not value.startswith('sk-') or len(value)<25 or any(c.isspace() for c in value)):
            QMessageBox.warning(self,'Key required','Enter or import your existing OpenAI API key in this dialog.');return
        try:
            if self.remember.isChecked() and value:save_key(value)
            preferences={'enabled':self.enabled.isChecked(),'request_limit':self.limit.value()}
            path=configure_runtime()/'ai-settings.json'
            path.write_text(json.dumps(preferences,indent=2),encoding='utf-8')
        except OSError:
            QMessageBox.warning(self,'Settings could not be saved','Credential storage or local preferences could not be written.');return
        self.result_key=value;self.result_preferences=preferences;self.key.clear();self.accept()
