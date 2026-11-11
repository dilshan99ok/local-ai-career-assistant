from App.app_utils.database import DB_PATH, initialize_database


def create_database():
    initialize_database()
    print(f"Database ready at: {DB_PATH}")


if __name__ == "__main__":
    create_database()
