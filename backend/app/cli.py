import argparse
import getpass
import re

from app.config import Settings
from app.db.session import build_engine, build_session_factory
from app.services import admin as admin_service

_USERNAME_PATTERN = re.compile(r"^[0-9]{8,18}$")


def _read_admin_input() -> tuple[str, str, str, str]:
    username = input("管理员用户名（8-18 位数字）：").strip()
    if not _USERNAME_PATTERN.fullmatch(username):
        raise ValueError("用户名必须为 8-18 位数字")

    password = getpass.getpass("密码（8-18 位，输入不会显示）：")
    if not 8 <= len(password) <= 18:
        raise ValueError("密码长度必须为 8-18 位")

    recovery_question = input("找回问题：").strip()
    recovery_answer = getpass.getpass("找回答案（输入不会显示）：")
    if not recovery_question or not recovery_answer.strip():
        raise ValueError("找回问题和答案不能为空")
    return username, password, recovery_question, recovery_answer


def create_admin_command() -> int:
    settings = Settings()
    username, password, question, answer = _read_admin_input()
    engine = build_engine(settings.database_url)
    factory = build_session_factory(engine)
    try:
        with factory() as session:
            user = admin_service.create_admin(
                session,
                username,
                password,
                question,
                answer,
            )
        print(f"管理员 {user.username} 创建成功")
        return 0
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="轻办公工具箱管理命令")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("create-admin", help="创建初始管理员账号")
    args = parser.parse_args()

    if args.command == "create-admin":
        raise SystemExit(create_admin_command())


if __name__ == "__main__":
    main()
