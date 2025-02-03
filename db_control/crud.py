# uname() error回避
import platform
print("platform", platform.uname())


from sqlalchemy import create_engine, insert, delete, update, select, func
import sqlalchemy
from sqlalchemy.orm import sessionmaker
import json
import pandas as pd
from contextlib import contextmanager

from db_control.connect_MySQL import engine
from . import mymodels_MySQL
from .mymodels_MySQL import Product, Transaction, TransactionDetail

Session = sessionmaker(bind=engine)


@contextmanager
def session_scope():
    """
    セッションを安全に管理するためのスコープを提供。
    トランザクションの開始、ロールバック、クローズを自動で処理。
    """
    session = Session()
    try:
        yield session  # 呼び出し元にセッションを渡す
        session.commit()  # 正常終了時はコミット
    except Exception as e:
        session.rollback()  # エラー時はロールバック
        print(f"セッションのエラー: {e}")  # デバッグ用にエラーを表示
        raise  # エラーを再スロー
    finally:
        session.close()  # 最後にセッションをクローズ

    """指定したモデルの最後に挿入された ID を取得"""
def get_last_inserted_id(session, model):
    return session.execute(
        select(model.TRD_ID).order_by(model.TRD_ID.desc()).limit(1)
    ).scalar()

def insertTransaction(transaction_data):
    query = insert(Transaction).values(transaction_data)
    try:
        with session_scope() as session:
            session.execute(query)
            TRD_ID = get_last_inserted_id(session, Transaction)
            return TRD_ID
    except sqlalchemy.exc.IntegrityError as e:
        print(f"Transaction：一意制約違反により、挿入に失敗しました: {e}")
        raise

def insertDetails(detail_data):
    query = insert(TransactionDetail).values(detail_data)
    try:
        with session_scope() as session:
            session.execute(query)
            get_total_amt_query = select(func.sum(TransactionDetail.PRD_PRICE)).where(TransactionDetail.TRD_ID == detail_data["TRD_ID"])
            TOTAL_AMT = session.execute(get_total_amt_query).scalar()
            return TOTAL_AMT
    except sqlalchemy.exc.IntegrityError as e:
        print(f"TransactionDetail：一意制約違反により、挿入に失敗しました: {e}")
        # 一意制約とはデータが重複を許可していないということ
        raise

def insetTotalamt(TOTAL_AMT, TRD_ID):
    query = update(Transaction).where(Transaction.TRD_ID == TRD_ID).values(TOTAL_AMT = TOTAL_AMT)
    try:
        with session_scope() as session:
            session.execute(query)
            return 
    except sqlalchemy.exc.IntegrityError as e:
        print(f"TOTAL_AMTの挿入に失敗しました: {e}")
        raise


def myselect(mymodels_MySQL, CODE):
    query = select(mymodels_MySQL).where(mymodels_MySQL.CODE == CODE)
    try:
        with session_scope() as session:
            # クエリを実行して結果を取得
            result = session.execute(query).scalars().all()
            print(f"Query result: {result}")

            # 結果をオブジェクトから辞書に変換し、リストに追加
            result_dict_list = [
                {
                    "PRD_ID": prd_info.PRD_ID,
                    "CODE": prd_info.CODE,
                    "NAME": prd_info.NAME,
                    "PRICE": prd_info.PRICE
                }
                for prd_info in result
            ]

        # リストを JSON に変換して返す
        result_json = json.dumps(result_dict_list, ensure_ascii=False)
        return result_json
    except sqlalchemy.exc.IntegrityError as e:
        print(f"一意制約違反: {e}")
        return None
    except Exception as e:
        print(f"エラー: {e}")
        return None


# def myselect(mymodel, customer_id):
#     # session構築
#     Session = sessionmaker(bind=engine)
#     session = Session()
#     query = session.query(mymodel_My).filter(mymodel.customer_id == customer_id)
#     try:
#         # トランザクションを開始
#         with session.begin():
#             result = query.all()
#         # 結果をオブジェクトから辞書に変換し、リストに追加
#         result_dict_list = []
#         for customer_info in result:
#             result_dict_list.append({
#                 "customer_id": customer_info.customer_id,
#                 "customer_name": customer_info.customer_name,
#                 "age": customer_info.age,
#                 "gender": customer_info.gender
#             })
#         # リストをJSONに変換
#         result_json = json.dumps(result_dict_list, ensure_ascii=False)
#     except sqlalchemy.exc.IntegrityError:
#         print("一意制約違反により、挿入に失敗しました")

#     # セッションを閉じる
#     session.close()
#     return result_json


def myselectAll(mymodel):
    # session構築
    Session = sessionmaker(bind=engine)
    session = Session()
    query = select(mymodel)
    try:
        # トランザクションを開始
        with session.begin():
            df = pd.read_sql_query(query, con=engine)
            result_json = df.to_json(orient='records', force_ascii=False)

    except sqlalchemy.exc.IntegrityError:
        print("一意制約違反により、挿入に失敗しました")
        result_json = None

    # セッションを閉じる
    session.close()
    return result_json


def myupdate(mymodel, values):
    # session構築
    Session = sessionmaker(bind=engine)
    session = Session()

    customer_id = values.pop("customer_id")

    query = "お見事！E0002の原因はこのクエリの実装ミスです。正しく実装しましょう"
    try:
        # トランザクションを開始
        with session.begin():
            result = session.execute(query)
    except sqlalchemy.exc.IntegrityError:
        print("一意制約違反により、挿入に失敗しました")
        session.rollback()
    # セッションを閉じる
    session.close()
    return "put"


def mydelete(mymodel, customer_id):
    # session構築
    Session = sessionmaker(bind=engine)
    session = Session()
    query = delete(mymodel).where(mymodel.customer_id == customer_id)
    try:
        # トランザクションを開始
        with session.begin():
            result = session.execute(query)
    except sqlalchemy.exc.IntegrityError:
        print("一意制約違反により、挿入に失敗しました")
        session.rollback()

    # セッションを閉じる
    session.close()
    return customer_id + " is deleted"


