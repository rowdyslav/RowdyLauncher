from db_loader import DB_CONN, DB_CURSOR
import hashlib


def auth(login: str, password: str) -> tuple[str, bool]:
    DB_CURSOR.execute("SELECT * FROM users WHERE login=?", (login,))
    user = DB_CURSOR.fetchone()

    if user is None:
        password_hash = hashlib.sha256(password.encode()).hexdigest()
        DB_CURSOR.execute(
            "INSERT INTO users VALUES (?, ?)",
            (login, password_hash),
        )
        return "Регистрация прошла успешно!", True
    elif user[1] != hashlib.sha256(password.encode()).hexdigest():
        return "Неверный пароль. Пожалуйста, попробуйте еще раз.", False
    else:
        return "Авторизация прошла успешно!", True


def update_stats(version_select):
    DB_CURSOR.execute(
        "SELECT * FROM stats WHERE version=?", (version_select.currentText(),)
    )
    version_stats = DB_CURSOR.fetchone()
    if version_stats is None:
        release = version_select.currentData().get("releaseTime")
        if not release:
            release = f"as Vanilla {version_select.currentText().split()[-1]}"
        else:
            release = release.strftime("%d.%m.%Y")

        DB_CURSOR.execute(
            "INSERT INTO stats VALUES (?, ?, ?)",
            (
                version_select.currentText(),
                1,
                release,
            ),
        )
    else:
        DB_CURSOR.execute(
            "UPDATE stats SET launches = launches + 1 WHERE version=?",
            (version_select.currentText(),),
        )

    DB_CONN.commit()
