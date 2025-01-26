from db_control.mymodels_MySQL import Base
from db_control.connect_MySQL import engine
from sqlalchemy import inspect


def init_db():
    # インスペクターを作成
    inspector = inspect(engine)
     # 確認したいテーブルのリスト
    required_tables = ['m_product_iwamu', 'transactions_iwamu', 'transaction_details_iwamu']

    # 既存のテーブルを取得
    existing_tables = inspector.get_table_names()

    print("Checking tables...")

    # 必要なテーブルが存在するか確認
    missing_tables = [table for table in required_tables if table not in existing_tables]

    # テーブルが存在しない場合は作成
    if missing_tables:
        print(f"Creating tables >>> Missing tables: {missing_tables}")
        try:
            # テーブルを作成
            Base.metadata.create_all(bind=engine)
            print("Tables created successfully!")
        except Exception as e:
            print(f"Error creating tables: {e}")
            raise
    else:
        print("All required tables already exist.")

if __name__ == "__main__":
    init_db()