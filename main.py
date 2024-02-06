from subprocess import call
from sys import version
from typing import Union
from uuid import uuid1

from icecream import ic
from minecraft_launcher_lib import fabric
from minecraft_launcher_lib.command import get_minecraft_command
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.types import (FabricMinecraftVersion,
                                          MinecraftOptions,
                                          MinecraftVersionInfo)
from minecraft_launcher_lib.utils import (get_installed_versions,
                                          get_minecraft_directory,
                                          get_version_list)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QAbstractItemView, QApplication, QComboBox,
                             QHeaderView, QLabel, QLineEdit, QMainWindow,
                             QProgressBar, QPushButton, QSizePolicy,
                             QSpacerItem, QStatusBar, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from db_loader import DB_CURSOR
from utils import auth, update_stats

# pyright: reportOptionalMemberAccess=false
LAUNCHER_DIR = get_minecraft_directory().replace("minecraft", "rowdylauncher")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        try:
            with open(f"{LAUNCHER_DIR}/.temp.dat", "rb") as f:
                lines = f.readlines()
                self.login.setText(lines[0].decode().strip())
                self.password.setText(lines[1].decode().strip())
        except FileNotFoundError:
            pass

    def initUI(self):
        self.resize(512, 512)
        self.setWindowTitle("RowdyLauncher")

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        self.logo = QLabel(self.centralwidget)
        self.logo.setPixmap(QPixmap("assets/logo.png"))

        self.logo_spacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.stats_button = QPushButton("Статистика", self.centralwidget)
        self.stats_button.clicked.connect(self.show_stats)

        self.login = QLineEdit(self.centralwidget)
        self.login.setPlaceholderText("Логин")
        self.password = QLineEdit(self.centralwidget)
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)

        self.status_bar = QStatusBar()

        self.version_select = QComboBox(self.centralwidget)
        vanilla_versions = [
            (f"Vanilla {vanilla_version['id']}", vanilla_version)
            for vanilla_version in get_version_list()
            if vanilla_version["type"] == "release"
        ]
        fabric_versions = [
            (f"Fabric {fabric_version['version']}", fabric_version)
            for fabric_version in fabric.get_all_minecraft_versions()
            if fabric_version["stable"]
        ]
        all_versions = zip(vanilla_versions, fabric_versions)
        for v, f in all_versions:
            self.version_select.addItem(v[0], v[1])
            self.version_select.addItem(f[0], f[1])

        self.progress_spacer = QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )

        self.start_progress_label = QLabel(self.centralwidget)
        self.start_progress_label.setText("")
        self.start_progress_label.setVisible(False)

        self.start_progress = QProgressBar(self.centralwidget)
        self.start_progress.setVisible(False)

        self.start_button = QPushButton("Играть", self.centralwidget)
        self.start_button.clicked.connect(self.launch_game)

        self.vertical_layout = QVBoxLayout(self.centralwidget)
        self.vertical_layout.setContentsMargins(15, 15, 15, 15)

        self.vertical_layout.addItem(self.logo_spacer)
        self.vertical_layout.addItem(self.progress_spacer)

        self.vertical_layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)
        self.vertical_layout.addWidget(self.login)
        self.vertical_layout.addWidget(self.password)
        self.vertical_layout.addWidget(self.status_bar)
        self.vertical_layout.addWidget(self.version_select)
        self.vertical_layout.addWidget(self.start_progress_label)
        self.vertical_layout.addWidget(self.start_progress)
        self.vertical_layout.addWidget(self.start_button)

        self.launch_thread = LaunchThread()
        self.launch_thread.STATE_UPDATE_SIGNAL.connect(self.state_update)
        self.launch_thread.PROGRESS_UPDATE_SIGNAL.connect(self.update_progress)

    def state_update(self, value):
        self.start_button.setDisabled(value)
        self.start_progress_label.setVisible(value)
        self.start_progress.setVisible(value)

    def update_progress(self, progress, max_progress, label):
        self.start_progress.setValue(progress)
        self.start_progress.setMaximum(max_progress)
        self.start_progress_label.setText(label)

    def launch_game(self):
        if not self.login.text() and not self.password.text():
            self.status_bar.showMessage("Введите логин и пароль!")
            return
        elif not self.login.text():
            self.status_bar.showMessage("Введите логин!")
            return
        elif not self.password.text():
            self.status_bar.showMessage("Введите пароль!")
            return

        log, authed = auth(self.login.text(), self.password.text())
        self.status_bar.showMessage(log)
        if authed:
            with open(f"{LAUNCHER_DIR}/.temp.dat", "wb") as f:
                f.write(str.encode(f"{self.login.text()}\n{self.password.text()}"))
        else:
            return

        update_stats(self.version_select)

        # Запуск LaunchThread
        self.login.setReadOnly(True)
        self.password.setReadOnly(True)

        self.launch_thread.LAUNCH_SETUP_SIGNAL.emit(
            self.version_select.currentText(),
            self.version_select.currentData(),
            self.login.text(),
        )
        self.launch_thread.start()

    def show_stats(self):
        self.stats_window = StatsWindow()
        self.stats_window.show()


class LaunchThread(QThread):
    """Класс поток, запускающий игру, отображающий прогресс"""

    LAUNCH_SETUP_SIGNAL = pyqtSignal(str, dict, str)
    PROGRESS_UPDATE_SIGNAL = pyqtSignal(int, int, str)
    STATE_UPDATE_SIGNAL = pyqtSignal(bool)

    VERSION_ID = ""
    LOGIN = ""

    PROGRESS = 0
    PROGRESS_MAX = 0
    PROGRESS_LABEL = ""

    def __init__(self):
        super().__init__()
        self.LAUNCH_SETUP_SIGNAL.connect(self.launch_setup)

    def launch_setup(
        self,
        version_name: str,
        version_dict: Union[MinecraftVersionInfo, FabricMinecraftVersion],
        login: str,
    ):
        self.version_name = version_name
        self.version_dict = version_dict
        self.login = login

    def update_progress_label(self, value):
        self.PROGRESS_LABEL = value
        self.PROGRESS_UPDATE_SIGNAL.emit(
            self.PROGRESS, self.PROGRESS_MAX, self.PROGRESS_LABEL
        )

    def update_progress(self, value):
        self.PROGRESS = value
        self.PROGRESS_UPDATE_SIGNAL.emit(
            self.PROGRESS, self.PROGRESS_MAX, self.PROGRESS_LABEL
        )

    def update_progress_max(self, value):
        self.PROGRESS_MAX = value
        self.PROGRESS_UPDATE_SIGNAL.emit(
            self.PROGRESS, self.PROGRESS_MAX, self.PROGRESS_LABEL
        )

    def run(self):
        """Установка и запуск версии майнкрафта"""

        self.STATE_UPDATE_SIGNAL.emit(True)

        if "Fabric" in self.version_name:
            fabric.install_fabric(
                minecraft_version=self.version_dict["version"],  # type: ignore
                minecraft_directory=LAUNCHER_DIR,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )
            for x in get_installed_versions(LAUNCHER_DIR):
                if x["id"].split("-")[-1] == self.version_dict["version"]:  # type: ignore
                    version = x["id"]
        else:
            install_minecraft_version(
                versionid=self.version_dict["id"],  # type: ignore
                minecraft_directory=LAUNCHER_DIR,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )
            version = self.version_dict["id"]  # type: ignore

        options: MinecraftOptions = {
            "username": self.login,
            "uuid": str(uuid1()),
            "token": "",
        }

        ic(options)

        call(
            get_minecraft_command(
                version=version,  # type: ignore
                minecraft_directory=LAUNCHER_DIR,
                options=options,
            )
        )
        self.STATE_UPDATE_SIGNAL.emit(False)


class StatsWindow(QMainWindow):
    """Окно просмотра статистики"""

    def __init__(self):
        super().__init__()
        self.initUI()
        self.refresh()

    def initUI(self):
        self.setWindowTitle("RowdyLauncher | Статистика")
        self.resize(384, 256)

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        self.stats_layout = QVBoxLayout(self.centralwidget)

        self.stats_table = QTableWidget(self.centralwidget)
        self.stats_table.setColumnCount(3)
        self.stats_table.setHorizontalHeaderLabels(["Версия", "Запуски", "Релиз"])
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.stats_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.Stretch
        )  # Версия
        self.stats_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.Stretch
        )  # Запуски
        self.stats_table.horizontalHeader().setSectionResizeMode(
            2, QHeaderView.Stretch
        )  # Релиз
        self.stats_table.horizontalHeader().setStretchLastSection(True)

        self.refresh_button = QPushButton("Обновить", self.centralwidget)
        self.refresh_button.clicked.connect(self.refresh)

        self.search_input = QLineEdit(self.centralwidget)
        self.search_input.setPlaceholderText("Поиск по версии")
        self.search_input.textChanged.connect(self.filterVersions)

        self.stats_layout.addWidget(self.search_input)
        self.stats_layout.addWidget(self.refresh_button)
        self.stats_layout.addWidget(self.stats_table)

    def refresh(self):
        """Обновление таблицы из дб"""

        DB_CURSOR.execute("SELECT * FROM stats")
        all_stats = DB_CURSOR.fetchall()

        self.stats_table.setRowCount(len(all_stats))
        for i, stat in enumerate(all_stats):
            self.stats_table.setItem(i, 0, QTableWidgetItem(stat[0]))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(stat[1])))
            self.stats_table.setItem(i, 2, QTableWidgetItem(str(stat[2])))

    def filterVersions(self):
        """Функция для поиска из дб"""

        search_text = self.search_input.text().strip().lower()
        DB_CURSOR.execute(
            "SELECT * FROM stats WHERE version LIKE ?", ("%" + search_text + "%",)
        )
        filtered_stats = DB_CURSOR.fetchall()

        self.stats_table.setRowCount(len(filtered_stats))
        for i, stat in enumerate(filtered_stats):
            self.stats_table.setItem(i, 0, QTableWidgetItem(stat[0]))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(stat[1])))
            self.stats_table.setItem(i, 2, QTableWidgetItem(str(stat[2])))


if __name__ == "__main__":
    from sys import argv, exit

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    app = QApplication(argv)
    window = MainWindow()
    window.show()

    exit(app.exec_())
