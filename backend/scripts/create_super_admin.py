"""python -m scripts.create_super_admin EMAIL PASSWORD"""

import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.models import User, UserRole
from app.db.session import SessionLocal


def main() -> None:
    email, password = sys.argv[1].lower(), sys.argv[2]
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == email))
        if not user:
            user = User(email=email, password_hash=hash_password(password))
            db.add(user)
            db.flush()
        if "super_admin" not in user.role_names:
            user.roles.append(UserRole(role="super_admin"))
        db.commit()
    print("super admin ready:", email)


if __name__ == "__main__":
    main()
