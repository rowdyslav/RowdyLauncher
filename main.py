from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt5.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QSpacerItem,
    QSizePolicy,
    QProgressBar,
    QPushButton,
    QApplication,
    QMainWindow,
)
from PyQt5.QtGui import QPixmap
from minecraft_launcher_lib.types import FabricMinecraftVersion, MinecraftOptions, MinecraftVersionInfo

from minecraft_launcher_lib import fabric
from minecraft_launcher_lib.utils import get_installed_versions, get_minecraft_directory, get_version_list
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command

from uuid import uuid1

from subprocess import call

minecraft_directory = get_minecraft_directory().replace("minecraft", "rowdylauncher")


class LaunchThread(QThread):
    launch_setup_signal = pyqtSignal(str, dict, str)
    progress_update_signal = pyqtSignal(int, int, str)
    state_update_signal = pyqtSignal(bool)

    version_id = ""
    login = ""

    progress = 0
    progress_max = 0
    progress_label = ""

    def __init__(self):
        super().__init__()
        self.launch_setup_signal.connect(self.launch_setup)

    def launch_setup(self, version_name: str, version_dict: MinecraftVersionInfo | FabricMinecraftVersion, login: str):
        self.version_name = version_name
        self.version_dict = version_dict
        self.login = login

    def update_progress_label(self, value):
        self.progress_label = value
        self.progress_update_signal.emit(
            self.progress, self.progress_max, self.progress_label
        )

    def update_progress(self, value):
        self.progress = value
        self.progress_update_signal.emit(
            self.progress, self.progress_max, self.progress_label
        )

    def update_progress_max(self, value):
        self.progress_max = value
        self.progress_update_signal.emit(
            self.progress, self.progress_max, self.progress_label
        )

    def run(self):
        self.state_update_signal.emit(True)

        if "Fabric" in self.version_name:
            installed_versions = get_installed_versions(minecraft_directory)
            for x in installed_versions:
                if x["id"].split('-')[-1] == self.version_dict["version"]:
                    v = x["id"]

            fabric.install_fabric(
                minecraft_version=self.version_dict["version"],
                minecraft_directory=minecraft_directory,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )
        else:
            v = self.version_dict["id"]
            install_minecraft_version(
                versionid=self.version_dict["id"],
                minecraft_directory=minecraft_directory,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )

        options: MinecraftOptions = {
            "login": self.login,
            "uuid": str(uuid1()),
            "token": "",
        }

        call(
            get_minecraft_command(
                version=v,
                minecraft_directory=minecraft_directory,
                options=options,
            )
        )
        self.state_update_signal.emit(False)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(512, 512)

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        self.logo = QLabel(self.centralwidget)
        self.logo.setMaximumSize(QSize(256, 256))
        self.logo.setPixmap(QPixmap("assets/logo.png"))
        self.logo.setScaledContents(True)

        self.logospacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.login = QLineEdit(self.centralwidget)
        self.login.setPlaceholderText("Логин")
        self.password = QLineEdit(self.centralwidget)
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)

        self.version_select = QComboBox(self.centralwidget)

        for v, f in zip(get_version_list(), fabric.get_all_minecraft_versions()):
            if v["type"] == "release":
                self.version_select.addItem(f"Vanilla {v.get("id")}", v)
            if f["stable"] == True:
                self.version_select.addItem(f"Fabric {f.get("version")}", f)

        self.progress_spacer = QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )

        self.start_progress_label = QLabel(self.centralwidget)
        self.start_progress_label.setText("")
        self.start_progress_label.setVisible(False)

        self.start_progress = QProgressBar(self.centralwidget)
        self.start_progress.setProperty("value", 0)
        self.start_progress.setVisible(False)

        self.start_button = QPushButton(self.centralwidget)
        self.start_button.setText("Играть")
        self.start_button.clicked.connect(self.launch_game) #type: ignore

        self.vertical_layout = QVBoxLayout(self.centralwidget)
        self.vertical_layout.setContentsMargins(15, 15, 15, 15)
        self.vertical_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vertical_layout.addItem(self.logospacer)
        self.vertical_layout.addWidget(self.login)
        self.vertical_layout.addWidget(self.password)
        self.vertical_layout.addWidget(self.version_select)
        self.vertical_layout.addItem(self.progress_spacer)
        self.vertical_layout.addWidget(self.start_progress_label)
        self.vertical_layout.addWidget(self.start_progress)
        self.vertical_layout.addWidget(self.start_button)

        self.launch_thread = LaunchThread()
        self.launch_thread.state_update_signal.connect(self.state_update)
        self.launch_thread.progress_update_signal.connect(self.update_progress)

    def state_update(self, value):
        self.start_button.setDisabled(value)
        self.start_progress_label.setVisible(value)
        self.start_progress.setVisible(value)

    def update_progress(self, progress, max_progress, label):
        self.start_progress.setValue(progress)
        self.start_progress.setMaximum(max_progress)
        self.start_progress_label.setText(label)

    def launch_game(self):
        self.launch_thread.launch_setup_signal.emit(
            self.version_select.currentText(), self.version_select.currentData(), self.login.text()
        )
        self.launch_thread.start()


if __name__ == "__main__":
    from sys import argv, exit

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    app = QApplication(argv)
    window = MainWindow()
    window.show()

    exit(app.exec_())
