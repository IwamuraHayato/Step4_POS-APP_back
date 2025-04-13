from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
from typing import List, Optional
from datetime import datetime
import traceback
from sqlalchemy import text

# 既存のモジュールをインポート
from db_control import crud
from db_control.connect_MySQL import engine
from db_control.mymodels_MySQL import User, UserTag, Tag, PointTransaction, Event, EventTag, Store
from db_control.crud import session_scope

# APIRouter の初期化
router = APIRouter()

# レスポンスモデルの定義
class EventRecommendation(BaseModel):
    id: str
    imageUrl: Optional[str] = None
    area: Optional[str] = None
    title: str
    date: Optional[str] = None
    tags: List[str] = []
    description: Optional[str] = None
    points: Optional[int] = None

class RecommendationResponse(BaseModel):
    events: List[EventRecommendation]
    similarUsers: List[int] = []

# 協調フィルタリングのロジックを実装
def calculate_recommendations(user_id: int, top_n: int = 5):
    try:
        # session_scopeを使用してデータベースセッションを管理
        with session_scope() as session:
            # ユーザーテーブルからデータを取得
            query_users = text("""
            SELECT user_id, gender, relationship_id, postal_code, birth_date 
            FROM Users
            """)
            result_users = session.execute(query_users).fetchall()
            if not result_users:
                raise HTTPException(status_code=404, detail="ユーザーデータが見つかりません")
            
            # 結果をDataFrameに変換
            df_users = pd.DataFrame(result_users)
            
            # 性別を数値に変換
            df_users["gender"] = df_users["gender"].map({"M": 0, "F": 1, "U": 2})
            
            # 年齢の計算
            df_users["age"] = pd.to_datetime("today").year - pd.to_datetime(df_users["birth_date"]).dt.year
            df_users.drop(columns=["birth_date"], inplace=True)
            
            # 年齢のMin-Maxスケーリング
            scaler = MinMaxScaler()
            df_users["age"] = scaler.fit_transform(df_users[["age"]])
            
            # 郵便番号をワンホットエンコーディング
            df_users = pd.get_dummies(df_users, columns=["postal_code"])
            area_columns = [col for col in df_users.columns if col.startswith("postal_code")]
            df_users[area_columns] = df_users[area_columns].astype(int)
            
            # ユーザータグの取得
            query_tags = text("""
            SELECT u.user_id, t.tag_name  
            FROM UserTags u 
            JOIN Tags t ON u.tag_id = t.tag_id
            """)
            result_tags = session.execute(query_tags).fetchall()
            
            # タグのワンホットエンコーディング
            if result_tags:
                df_tags = pd.DataFrame(result_tags)
                df_tags_onehot = df_tags.pivot_table(
                    index="user_id", columns="tag_name", aggfunc="size", fill_value=0
                )
                df_tags_onehot = df_tags_onehot.add_prefix("tag_")
            else:
                # タグがない場合は空のDataFrameを作成
                df_tags_onehot = pd.DataFrame(index=df_users["user_id"].unique())
            
            # ポイント取引の取得
            query_transactions = text("""
            SELECT user_id, store_id 
            FROM PointTransaction 
            WHERE user_id IS NOT NULL
            """)
            result_transactions = session.execute(query_transactions).fetchall()
            
            # 取引のワンホットエンコーディング
            if result_transactions:
                df_transactions = pd.DataFrame(result_transactions)
                df_transactions_onehot = df_transactions.pivot_table(
                    index="user_id", columns="store_id", aggfunc="size", fill_value=0
                )
                df_transactions_onehot = df_transactions_onehot.add_prefix("store_")
            else:
                # 取引がない場合は空のDataFrameを作成
                df_transactions_onehot = pd.DataFrame(index=df_users["user_id"].unique())
            
            # データの統合
            df_final = df_users.set_index("user_id")\
                .join(df_tags_onehot, how="left")\
                .join(df_transactions_onehot, how="left")\
                .fillna(0)
            
            # 対象ユーザーがデータセットに存在するか確認
            if user_id not in df_final.index:
                print(f"ユーザーID {user_id} はデータセットに存在しません")
                return {"events": [], "similarUsers": []}
            
            # コサイン類似度の計算
            cosine_sim = cosine_similarity(df_final)
            # 結果をデータフレームに変換
            cosine_sim_df = pd.DataFrame(cosine_sim, index=df_final.index, columns=df_final.index)
            
            # 類似ユーザーの抽出
            similar_users = cosine_sim_df[user_id].sort_values(ascending=False).iloc[1:top_n+1].index.tolist()
            
            # 類似ユーザーが訪れた店舗の抽出
            existing_users = [user for user in similar_users if user in df_transactions_onehot.index]
            if existing_users:
                recommended_stores = df_transactions_onehot.loc[existing_users].sum().sort_values(ascending=False)
                top_stores = recommended_stores.head(5).index.tolist()
                
                # 店舗IDからイベントを取得
                store_ids = [int(store.replace("store_", "")) for store in top_stores]
                
                # 店舗に関連するイベントを取得
                if store_ids:
                    store_ids_str = ", ".join(str(id) for id in store_ids)
                    # 現在の日付（CURDATE()）以降に開催予定のイベントを抽出→AND e.start_date >= CURDATE()
                    # query_events = text(f"""
                    #     SELECT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
                    #     e.flyer_url, e.event_image_url, e.store_id
                    #     FROM Events e
                    #     LEFT JOIN Stores s ON e.store_id = s.store_id
                    #     WHERE e.store_id IN ({store_ids_str})
                    #     AND e.start_date >= CURDATE()
                    #     ORDER BY e.start_date ASC
                    #     LIMIT 6
                    #     """)
                    #　↓日時に関係なく抽出
                    query_events = text(f"""
                        SELECT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
                        e.flyer_url, e.event_image_url, e.store_id
                        FROM Events e
                        LEFT JOIN Stores s ON e.store_id = s.store_id
                        WHERE e.store_id IN ({store_ids_str})
                        ORDER BY e.start_date ASC
                        LIMIT 6
                        """)
                    
                    result_events = session.execute(query_events).fetchall()
                    
                    # イベント情報をフォーマット
                    recommended_events = []
                    for event in result_events:
                        # イベントタグの取得
                        query_event_tags = text("""
                        SELECT t.tag_name
                        FROM EventTags et
                        JOIN Tags t ON et.tag_id = t.tag_id
                        WHERE et.event_id = :event_id
                        """)
                        result_tags = session.execute(query_event_tags, {"event_id": event.event_id}).fetchall()
                        tags = [tag.tag_name for tag in result_tags]
                        
                        event_date = event.start_date.strftime("%Y/%m/%d") if event.start_date else None
                        
                        recommended_events.append(EventRecommendation(
                            id=str(event.event_id),
                            imageUrl=event.event_image_url or event.flyer_url,
                            area="福岡市内",  # 固定値を使用
                            title=event.event_name,
                            date=event_date,
                            tags=["おすすめ"] + tags,
                            description=event.description,
                            points=None  # ポイント情報がない場合はNone
                        ))
                    
                    return {
                        "events": recommended_events,
                        "similarUsers": similar_users
                    }
            
            # イベントがない場合や類似ユーザーがいない場合は空のリストを返す
            return {
                "events": [],
                "similarUsers": similar_users
            }
            
    except Exception as e:
        print(f"推薦計算エラー: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"推薦計算中にエラーが発生しました: {str(e)}")

# フォールバックイベントを取得する関数
def get_popular_events(session, limit=6):
    try:
        # 人気のイベントを取得するクエリ
        # ここでは開始日が近いイベントを「人気」とみなしています
        query = text(f"""
        SELECT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
               e.flyer_url, e.event_image_url, e.store_id,
               s.address as area
        FROM Events e
        LEFT JOIN Stores s ON e.store_id = s.store_id
        WHERE e.start_date >= CURDATE()
        ORDER BY e.start_date ASC
        LIMIT {limit}
        """)
        
        result = session.execute(query).fetchall()
        return result
    except Exception as e:
        print(f"人気イベント取得エラー: {str(e)}")
        return []

@router.get("/api/recommendations/{user_id}", response_model=RecommendationResponse)
def get_recommendations(user_id: int, top_n: int = Query(5, ge=1, le=20)):
    """ユーザーIDに基づいて協調フィルタリングによるおすすめイベントを取得"""
    try:
        # ユーザーの存在確認
        user = crud.getuserById(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="指定されたユーザーが見つかりません")
        
        # 協調フィルタリングによるレコメンド計算
        recommendations = calculate_recommendations(user_id, top_n)
        
        # レコメンドがない場合は代替のレコメンドを提供
        if not recommendations["events"]:
            with session_scope() as session:
                # 人気のイベントをフォールバックとして表示
                popular_events = get_popular_events(session, limit=6)
                events = []
                
                for event in popular_events:
                    # イベントタグの取得
                    query_event_tags = text("""
                    SELECT t.tag_name
                    FROM EventTags et
                    JOIN Tags t ON et.tag_id = t.tag_id
                    WHERE et.event_id = :event_id
                    """)
                    result_tags = session.execute(query_event_tags, {"event_id": event.event_id}).fetchall()
                    tags = [tag.tag_name for tag in result_tags]
                    
                    event_date = event.start_date.strftime("%Y/%m/%d") if event.start_date else None
                    
                    events.append(EventRecommendation(
                        id=str(event.event_id),
                        imageUrl=event.event_image_url or event.flyer_url,
                        area=event.area or "福岡市内",
                        title=f"注目イベント: {event.event_name}",
                        date=event_date,
                        tags=["人気"] + tags,
                        description=event.description,
                        points=None
                    ))
                
                recommendations["events"] = events
        
        return recommendations
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print(f"レコメンデーションAPIエラー: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"レコメンデーション取得中にエラーが発生しました: {str(e)}")