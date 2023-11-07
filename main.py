from PyQt5.QtCore import QThread, pyqtSignal, QSize, Qt
from PyQt5.QtWidgets import (
    QBoxLayout,
    QLayout,
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
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QAbstractItemView,
)
from PyQt5.QtGui import QPixmap, QWindow
from minecraft_launcher_lib.types import MinecraftOptions

from minecraft_launcher_lib import fabric
from minecraft_launcher_lib.utils import (
    get_installed_versions,
    get_minecraft_directory,
    get_version_list,
)
from minecraft_launcher_lib.install import install_minecraft_version
from minecraft_launcher_lib.command import get_minecraft_command

from uuid import uuid1

from subprocess import call

import sqlite3

launcher_dir = get_minecraft_directory().replace("minecraft", "rowdylauncher")


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

    def launch_setup(self, version_name: str, version_dict, login: str):
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
            fabric.install_fabric(
                minecraft_version=self.version_dict["version"],
                minecraft_directory=launcher_dir,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )

            installed_versions = get_installed_versions(launcher_dir)
            for x in installed_versions:
                if x["id"].split("-")[-1] == self.version_dict["version"]:
                    v = x["id"]

        else:
            v = self.version_dict["id"]
            install_minecraft_version(
                versionid=self.version_dict["id"],
                minecraft_directory=launcher_dir,
                callback={
                    "setStatus": self.update_progress_label,
                    "setProgress": self.update_progress,
                    "setMax": self.update_progress_max,
                },
            )

        options: MinecraftOptions = {
            "username": self.login,
            "uuid": str(uuid1()),
            "token": "",
        }

        call(
            get_minecraft_command(
                version=v,  # type: ignore
                minecraft_directory=launcher_dir,
                options=options,
            )
        )
        self.state_update_signal.emit(False)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.resize(512, 512)
        self.setWindowTitle("RowdyLauncher")

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        self.logo = QLabel(self.centralwidget)
        self.logo.setPixmap(QPixmap("assets/logo.png"))

        self.logospacer = QSpacerItem(
            20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )

        self.stats_button = QPushButton("Статистика", self.centralwidget)
        self.stats_button.clicked.connect(self.show_stats)  # type: ignore

        self.login = QLineEdit(self.centralwidget)
        self.login.setPlaceholderText("Логин")
        self.password = QLineEdit(self.centralwidget)
        self.password.setPlaceholderText("Пароль")
        self.password.setEchoMode(QLineEdit.Password)

        self.status_bar = QStatusBar()

        self.version_select = QComboBox(self.centralwidget)
        versions = [
            (f"Vanilla {v['id']}", v)
            for v in get_version_list()
            if v["type"] == "release"
        ]
        fabric_versions = [
            (f"Fabric {f['version']}", f)
            for f in fabric.get_all_minecraft_versions()
            if f["stable"]
        ]
        all_versions = versions + fabric_versions
        for text, data in all_versions:
            self.version_select.addItem(text, data)

        self.progress_spacer = QSpacerItem(
            20, 20, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum
        )

        self.start_progress_label = QLabel(self.centralwidget)
        self.start_progress_label.setText("")
        self.start_progress_label.setVisible(False)

        self.start_progress = QProgressBar(self.centralwidget)
        self.start_progress.setVisible(False)

        self.start_button = QPushButton("Играть", self.centralwidget)
        self.start_button.clicked.connect(self.launch_game)  # type: ignore

        self.vertical_layout = QVBoxLayout(self.centralwidget)
        self.vertical_layout.setContentsMargins(15, 15, 15, 15)

        self.vertical_layout.addItem(self.logospacer)
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

    def show_stats(self):
        self.stats_window = StatsWindow()
        self.stats_window.show()

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

        # Авторизация
        conn_auth = sqlite3.connect("users.db")
        c_auth = conn_auth.cursor()

        c_auth.execute("SELECT * FROM users WHERE login=?", (self.login.text(),))
        user = c_auth.fetchone()
        if user is None:
            c_auth.execute(
                "INSERT INTO users VALUES (?, ?)",
                (self.login.text(), self.password.text()),
            )
            conn_auth.commit()
            self.status_bar.showMessage("Регистрация прошла успешно!")
        elif user[1] != self.password.text():
            self.status_bar.showMessage(
                "Неверный пароль. Пожалуйста, попробуйте еще раз."
            )
            return
        else:
            self.status_bar.showMessage("Авторизация прошла успешно!")

        # Статистика
        conn_stats = sqlite3.connect("stats.db")
        c_stats = conn_stats.cursor()

        c_stats.execute(
            "CREATE TABLE IF NOT EXISTS stats (version TEXT, launches INTEGER)"
        )

        c_stats.execute(
            "SELECT * FROM stats WHERE version=?", (self.version_select.currentText(),)
        )
        version_stats = c_stats.fetchone()
        if version_stats is None:
            c_stats.execute(
                "INSERT INTO stats VALUES (?, ?)",
                (self.version_select.currentText(), 1),
            )
        else:
            c_stats.execute(
                "UPDATE stats SET launches = launches + 1 WHERE version=?",
                (self.version_select.currentText(),),
            )
        conn_stats.commit()

        # Проверка значений из stats.db
        c_stats.execute("SELECT * FROM stats")
        all_stats = c_stats.fetchall()
        for stat in all_stats:
            print(f"Версия: {stat[0]}, Запуски: {stat[1]}")

        conn_auth.close()
        conn_stats.close()

        # Запуск
        self.login.setReadOnly(True)
        self.password.setReadOnly(True)
        self.launch_thread.launch_setup_signal.emit(
            self.version_select.currentText(),
            self.version_select.currentData(),
            self.login.text(),
        )
        self.launch_thread.start()


class StatsWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("RowdyLauncher | Статистика")
        self.resize(384, 256)

        self.centralwidget = QWidget(self)
        self.setCentralWidget(self.centralwidget)

        self.stats_layout = QVBoxLayout(self.centralwidget)

        self.stats_table = QTableWidget(self.centralwidget)
        self.stats_table.setColumnCount(2)
        self.stats_table.setHorizontalHeaderLabels(["Версия", "Запуски"])
        self.stats_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.refresh_button = QPushButton("Обновить", self.centralwidget)
        self.refresh_button.clicked.connect(self.refresh)  # type: ignore
        self.refresh()

        self.stats_layout.addWidget(self.stats_table)
        self.stats_layout.addWidget(self.refresh_button)

    # to do: доделать статистику пользователя из файлов (колво миров, модов и тд, что угодно)

    def refresh(self):
        conn_stats = sqlite3.connect("stats.db")
        c_stats = conn_stats.cursor()
        c_stats.execute("SELECT * FROM stats")
        all_stats = c_stats.fetchall()

        conn_stats.close()

        self.stats_table.setRowCount(len(all_stats))
        for i, stat in enumerate(all_stats):
            self.stats_table.setItem(i, 0, QTableWidgetItem(stat[0]))
            self.stats_table.setItem(i, 1, QTableWidgetItem(str(stat[1])))


if __name__ == "__main__":
    from sys import argv, exit

    QApplication.setAttribute(Qt.ApplicationAttribute.AA_EnableHighDpiScaling, True)

    app = QApplication(argv)
    window = MainWindow()
    window.show()

    exit(app.exec_())
