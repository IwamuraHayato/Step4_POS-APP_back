from schemas import RegisterStep1Request

# uname() error回避
import platform
print("platform", platform.uname())


from sqlalchemy import create_engine, insert, delete, update, select, func
import sqlalchemy
from sqlalchemy.orm import Session,sessionmaker
import json
import pandas as pd
from contextlib import contextmanager
from db_control import mymodels_MySQL as models
from db_control.connect_MySQL import engine
from . import mymodels_MySQL
from .mymodels_MySQL import Family, FamilyRelationship, User, UserTag, Tag, Store, Event, EventTag, TransactionType, PointTransaction, FavoriteEvent
from typing import List
from datetime import date


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

def selectEvent(store_id):
    query = select(mymodels_MySQL.Event).where(mymodels_MySQL.Event.store_id == store_id)
    try:
        with session_scope() as session:
            result = session.execute(query).scalars().all()
            print(f"Query result: {result}")
            # 結果をオブジェクトから辞書に変換し、リストに追加
            result_dict_eventlist = [
                {
                    "event_id": event_info.event_id,
                    "event_name": event_info.event_name,
                    "start_date": event_info.start_date.strftime("%Y-%m-%d"),
                    "end_date": event_info.end_date.strftime("%Y-%m-%d"),
                    "start_at": str(event_info.start_at), 
                    "end_at": str(event_info.end_at),
                    "description": event_info.description,
                    "store_id": event_info.store_id,
                    "flyer_url": event_info.flyer_url,
                    "event_image_url": event_info.event_image_url
                }
                for event_info in result
            ]
            return result_dict_eventlist
    except Exception as e:
            print(f"エラー: {e}")
            return None
    
def insertEvent(event_data):
    """
    イベントをデータベースに挿入する
    
    Args:
        event_data (list): イベントデータのリスト
        
    Returns:
        int: 挿入されたイベントのID
    """
    print(f"Inserting event with data: {event_data}")  # デバッグ用
    
    # event_dataがリストの場合は最初の要素を取得
    if isinstance(event_data, list) and len(event_data) > 0:
        event_data = event_data[0]
    
    # flyer_urlとevent_image_urlが存在しない場合はNoneを設定
    if 'flyer_url' not in event_data:
        event_data['flyer_url'] = None
    if 'event_image_url' not in event_data:
        event_data['event_image_url'] = None
    
    query = insert(Event).values(event_data)
    try:
        with session_scope() as session:
            result = session.execute(query)
            session.flush() 
            event_id = result.inserted_primary_key[0]
            print(f"Successfully inserted event with ID: {event_id}")  # デバッグ用
            return event_id
    except sqlalchemy.exc.IntegrityError as e:
        print(f"Transaction：一意制約違反により、挿入に失敗しました: {e}")
        raise

def getTagIdByName(tag_name):
    """タグ名からタグIDを取得する"""
    try:
        with session_scope() as session:
            query = select(Tag.tag_id).where(Tag.tag_name == tag_name)
            result = session.execute(query).scalar()
            if not result:
                # タグが存在しない場合は新規作成
                new_tag = Tag(tag_name=tag_name)
                session.add(new_tag)
                session.flush()
                result = new_tag.tag_id
            return result
    except Exception as e:
        print(f"タグID取得エラー: {e}")
        raise

def insertEventTag(event_id, tag_ids):
    try:
        with session_scope() as session:
            for tag_id in tag_ids:
                existing_tag = session.query(Tag).filter_by(tag_id=tag_id).first()
                if not existing_tag:
                    raise Exception(f"存在しないtag_idです: {tag_id}")
                event_tag = EventTag(event_id=event_id, tag_id=tag_id)
                session.add(event_tag)
    except Exception as e:
        print(f"EventTag の挿入に失敗しました: {e}")
        raise

def getuserById(user_id):
    query = select(mymodels_MySQL.User).where(mymodels_MySQL.User.user_id == user_id)
    try:
        with session_scope() as session:
            user_info = session.execute(query).scalars().first()
            if user_info:
                points = getTotalPointsByUserId(user_info.user_id)
                return {
                    "user_id": user_info.user_id,
                    "name": user_info.name,
                    "birth_date": str(user_info.birth_date),
                    "gender": user_info.gender,
                    # "area_id": user_info.area_id,
                    "points": points 
                }
            return None
    except sqlalchemy.exc.IntegrityError as e:
        print(f"Transaction：一意制約違反により、挿入に失敗しました: {e}")
        raise

def getTotalPointsByUserId(user_id: int):
    try:
        with session_scope() as session:
            total_points = session.query(func.coalesce(func.sum(PointTransaction.point), 0)) \
                .filter(PointTransaction.user_id == user_id) \
                .scalar()
            return total_points
    except Exception as e:
        print(f"ポイント合計取得エラー: {e}")
        raise

def insertUserAndStoreTransaction(data):
    with session_scope() as session:
        # typeに応じて対応する2つのタイプを決定
        if data.type == "earn":
            user_type = "earn"
            store_type = "grant"
            user_point = data.point
            store_point = -data.point
        elif data.type == "use":
            user_type = "use"
            store_type = "collect"
            user_point = -data.point
            store_point = data.point
        else:
            raise Exception("不正なトランザクションタイプです")

        # トランザクション種別ID取得
        def get_type_id(t_type):
            result = session.execute(
                select(TransactionType.transaction_type_id).where(TransactionType.transaction_type == t_type)
            ).scalar()
            if not result:
                raise Exception(f"{t_type} のtransaction_typeが見つかりません")
            return result

        user_transaction = PointTransaction(
            user_id=data.user_id,
            store_id=data.store_id,
            point=user_point,
            transaction_type_id=get_type_id(user_type)
        )

        store_transaction = PointTransaction(
            user_id=None,
            store_id=data.store_id,
            point=store_point,
            transaction_type_id=get_type_id(store_type)
        )

        session.add_all([user_transaction, store_transaction])

def get_all_tags():
    try:
        with session_scope() as session:
            result = session.query(mymodels_MySQL.Tag).all()
            return [{"tag_id": tag.tag_id, "tag_name": tag.tag_name} for tag in result]
    except Exception as e:
        print(f"タグ一覧取得エラー: {e}")
        raise

def insert_favorite_event(user_id, event_id):
    """
    お気に入りイベントを登録
    event: FavoriteEvent (Pydanticモデル)
    """
    try:
        with session_scope() as session:
            # 重複チェック（同じuser_id + event_idの組み合わせがあるか）
            existing = session.query(FavoriteEvent).filter_by(
                user_id=user_id,
                event_id=event_id
            ).first()
            if existing:
                print("すでにお気に入り登録されています")
                return  # or raise Exception / HTTPException

            new_favorite = FavoriteEvent(
                user_id=user_id,
                event_id=event_id
            )
            session.add(new_favorite)
            print("お気に入りを登録しました")
    except Exception as e:
        print(f"お気に入り登録エラー: {e}")
        raise


def delete_favorite_event(user_id: int, event_id: int):
    """
    お気に入りイベントを削除
    """
    try:
        with session_scope() as session:
            favorite = session.query(FavoriteEvent).filter_by(
                user_id=user_id,
                event_id=event_id
            ).first()

            if favorite:
                session.delete(favorite)
                print("お気に入りを削除しました")
            else:
                print("対象のお気に入りは存在しません")
    except Exception as e:
        print(f"お気に入り削除エラー: {e}")
        raise

def insert_user_step1(db, data):
    new_user = models.User(
        name=data.name,
        name_kana=data.name_kana,
        gender=data.gender,
        birth_date=data.birth_date,
        postal_code=data.postal_code,
        address1=data.address1,
        address2=data.address2,
        email=None, #仮登録なので空、Step3で登録
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)  # user_id を取得するため
    return new_user.user_id

def insertUserTag(user_id: int, tag_id: int):
    try:
        with session_scope() as session:
            new_user_tag = UserTag(user_id=user_id, tag_id=tag_id)
            session.add(new_user_tag)
            print(f"UserTag 登録成功: user_id={user_id}, tag_id={tag_id}")
    except Exception as e:
        print(f"UserTag 登録失敗: {e}")
        raise

def get_favorite_event_ids(user_id):
    with session_scope() as session:
        result = session.query(FavoriteEvent.event_id).filter_by(user_id=user_id).distinct().all()
        return [r.event_id for r in result]

def get_favorite_events(user_id):
    with session_scope() as session:
        result = session.query(
            FavoriteEvent.event_id,
            Event.event_name,
            Event.event_image_url,
            Event.start_date,
            Event.area,
            Store.store_name
        ).join(Event, FavoriteEvent.event_id == Event.event_id) \
         .join(Store, Event.store_id == Store.store_id) \
         .filter(FavoriteEvent.user_id == user_id) \
         .distinct().all()

        return [
            {
                "event_id": r.event_id,
                "event_name": r.event_name,
                "area": r.area,
                "date": r.start_date.strftime("%Y/%m/%d"),
                "image_url": r.event_image_url
            }
            for r in result
        ]

def search_events(keyword: str, date: str, tags: str):
    with session_scope() as session:
        query = session.query(Event, Store.store_name).join(Store, Event.store_id == Store.store_id)

        if keyword:
            query = query.filter(Event.event_name.contains(keyword) | Event.description.contains(keyword))

        if date:
            query = query.filter(Event.start_date == date)

        if tags:
            tag_list = tags.split(',')
            query = query.join(EventTag, Event.event_id == EventTag.event_id)\
                         .join(Tag, EventTag.tag_id == Tag.tag_id)\
                         .filter(Tag.tag_name.in_(tag_list))

        results = query.all()

        return [{
            "id": e.Event.event_id,
            "title": e.Event.event_name,
            "date": e.Event.start_date.strftime("%Y-%m-%d"),
            "area": e.Event.area,
            "description": e.Event.description,
            "imageUrl": e.Event.event_image_url or None,
            "tags": [t.tag_name for t in session.query(Tag).join(EventTag).filter(EventTag.event_id == e.Event.event_id)]
        } for e in results]
    

def get_upcoming_events():
    today = date.today()
    with session_scope() as session:
        events = session.query(Event, Store.store_name)\
            .join(Store, Event.store_id == Store.store_id)\
            .filter(Event.start_date >= today)\
            .order_by(Event.start_date.asc())\
            .all()

        event_list = []
        for e in events:
            tags = session.query(Tag.tag_name)\
                .join(EventTag)\
                .filter(EventTag.event_id == e.Event.event_id)\
                .all()
            tag_names = [t.tag_name for t in tags]

            event_list.append({
                "id": e.Event.event_id,
                "title": e.Event.event_name,
                "date": e.Event.start_date.strftime("%Y-%m-%d"),
                "area": e.Event.area,
                "imageUrl": e.Event.event_image_url,
                "description": e.Event.description,
                "tags": tag_names,
            })

        return event_list

def get_event_detail_by_id(event_id: int):
    try:
        with session_scope() as session:
            event = session.query(Event).filter(Event.event_id == event_id).first()
            if not event:
                return None

            store_name = event.store.store_name if event.store else None

            tag_names = [
                t.tag_name for t in session.query(Tag.tag_name)
                .join(EventTag)
                .filter(EventTag.event_id == event.event_id)
                .all()
            ]

            return {
                "event_id": event.event_id,
                "title": event.event_name,
                "description": event.description,
                "date": f"{event.start_date.strftime('%Y年%m月%d日')} 〜 {event.end_date.strftime('%Y年%m月%d日')}",
                "time": f"{event.start_at.strftime('%H:%M')} 〜 {event.end_at.strftime('%H:%M')}",
                "area": event.area,
                "store_name": store_name,
                "image_url": event.event_image_url,
                "flyer_url": event.flyer_url,
                "tags": tag_names,
                "point_info": event.information
            }

    except Exception as e:
        print(f"イベント詳細取得エラー: {e}")
        raise
