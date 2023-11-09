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
