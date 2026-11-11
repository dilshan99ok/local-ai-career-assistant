from App.app_utils.database import DB_PATH, initialize_database


def update_database():
    initialize_database()
    print(f"Applications schema is ready at: {DB_PATH}")


if __name__ == "__main__":
    update_database()
