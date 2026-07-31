from PySide6 import QtCore, QtWidgets

from videotrans.configure.config import params
from videotrans.util.help_misc import open_url


class Ui_jiucaiform(object):
    def setupUi(self, form):
        form.setWindowTitle("韭菜盒子 API")
        form.setMinimumWidth(560)
        layout = QtWidgets.QFormLayout(form)

        self.jiucai_api = QtWidgets.QLineEdit()
        self.jiucai_key = QtWidgets.QLineEdit()
        self.jiucai_key.setEchoMode(QtWidgets.QLineEdit.Password)
        self.show_key = QtWidgets.QCheckBox("显示 Key")
        layout.addRow("API URL", self.jiucai_api)
        layout.addRow("API Key", self.jiucai_key)
        layout.addRow("", self.show_key)

        buttons = QtWidgets.QHBoxLayout()
        self.get_key = QtWidgets.QPushButton("前往获取 Key")
        self.test_api = QtWidgets.QPushButton("测试连接")
        self.save_api = QtWidgets.QPushButton("保存")
        buttons.addWidget(self.get_key)
        buttons.addStretch()
        buttons.addWidget(self.test_api)
        buttons.addWidget(self.save_api)
        layout.addRow(buttons)

        self.jiucai_api.setText(params.get("jiucai_api", "https://api.jiucaihezi.studio/v1"))
        self.jiucai_key.setText(params.get("jiucai_key", ""))
        self.show_key.toggled.connect(lambda checked: self.jiucai_key.setEchoMode(
            QtWidgets.QLineEdit.Normal if checked else QtWidgets.QLineEdit.Password))
        self.get_key.clicked.connect(lambda: open_url("https://api.jiucaihezi.studio/keys"))
        QtCore.QMetaObject.connectSlotsByName(form)
