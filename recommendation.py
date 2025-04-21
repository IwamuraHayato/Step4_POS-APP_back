from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
import pandas as pd
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
from typing import List, Optional, Dict, Any
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

# データ取得関数
def get_user_data(session) -> pd.DataFrame:
    """ユーザーデータを取得し前処理する"""
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
    return df_users

def get_user_tags(session) -> pd.DataFrame:
    """ユーザータグデータを取得しワンホットエンコーディングする"""
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
        return df_tags_onehot.add_prefix("tag_")
    else:
        # タグがない場合は空のDataFrameを作成
        return pd.DataFrame()

def get_transaction_data(session) -> pd.DataFrame:
    """ポイント取引データを取得しワンホットエンコーディングする"""
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
        return df_transactions_onehot.add_prefix("store_")
    else:
        # 取引がない場合は空のDataFrameを作成
        return pd.DataFrame()
    
def get_favorite_events_onehot(session) -> pd.DataFrame:
    """お気に入りイベントをワンホットエンコーディングする"""
    query_fav = text("""
    SELECT user_id, event_id
    FROM FavoriteEvents
    """)
    result_fav = session.execute(query_fav).fetchall()

    if result_fav:
        df_fav = pd.DataFrame(result_fav)
        df_fav_onehot = df_fav.pivot_table(
            index="user_id", columns="event_id", aggfunc="size", fill_value=0
        )
        return df_fav_onehot.add_prefix("fav_event_")
    else:
        return pd.DataFrame() 

def get_event_tags(session, event_id: int) -> List[str]:
    """イベントのタグを取得する"""
    query_event_tags = text("""
    SELECT t.tag_name
    FROM EventTags et
    JOIN Tags t ON et.tag_id = t.tag_id
    WHERE et.event_id = :event_id
    """)
    result_tags = session.execute(query_event_tags, {"event_id": event_id}).fetchall()
    return [tag.tag_name for tag in result_tags]

def get_events_by_store_ids(session, store_ids: List[int], limit: int = 6) -> List[Dict]:
    """指定された店舗IDに関連するイベントを取得する"""
    if not store_ids:
        return []
        
    store_ids_str = ", ".join(str(id) for id in store_ids)
    query_events = text(f"""
        SELECT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
        e.flyer_url, e.event_image_url, e.store_id
        FROM Events e
        LEFT JOIN Stores s ON e.store_id = s.store_id
        WHERE e.store_id IN ({store_ids_str})
        ORDER BY e.start_date ASC
        LIMIT {limit}
        """)
    
    return session.execute(query_events).fetchall()

def get_popular_events(session, limit: int = 6) -> List[Dict]:
    """人気のイベントを取得する"""
    query = text(f"""
    SELECT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
           e.flyer_url, e.event_image_url, e.store_id,
           s.store_name
    FROM Events e
    LEFT JOIN Stores s ON e.store_id = s.store_id
    WHERE e.start_date >= CURDATE()
    ORDER BY e.start_date ASC
    LIMIT {limit}
    """)
    
    return session.execute(query).fetchall()

def format_event_to_recommendation(session, event, prefix_tag: str = "おすすめ") -> EventRecommendation:
    """イベント情報をレコメンデーションモデルに変換する"""
    tags = get_event_tags(session, event.event_id)
    event_date = event.start_date.strftime("%Y/%m/%d") if event.start_date else None
    
    return EventRecommendation(
        id=str(event.event_id),
        imageUrl=event.event_image_url or event.flyer_url,
        area=getattr(event, "area", "福岡市内"),  # areaフィールドがない場合はデフォルト値
        title=event.event_name,
        date=event_date,
        tags=[prefix_tag] + tags,
        description=event.description,
        points=None  # ポイント情報がない場合はNone
    )

def find_similar_users(df_final: pd.DataFrame, user_id: int, top_n: int = 5) -> List[int]:
    """類似ユーザーをコサイン類似度で計算する"""
    # 対象ユーザーがデータセットに存在するか確認
    if user_id not in df_final.index:
        print(f"ユーザーID {user_id} はデータセットに存在しません")
        return []
    
    # コサイン類似度の計算
    cosine_sim = cosine_similarity(df_final)
    # 結果をデータフレームに変換
    cosine_sim_df = pd.DataFrame(cosine_sim, index=df_final.index, columns=df_final.index)
    
    # 類似ユーザーの抽出 (自分自身を除く)
    return cosine_sim_df[user_id].sort_values(ascending=False).iloc[1:top_n+1].index.tolist()

def find_recommended_stores(df_transactions: pd.DataFrame, similar_users: List[int], top_n: int = 5) -> List[int]:
    """類似ユーザーが訪れた店舗を特定する"""
    # 類似ユーザーが取引データに存在するか確認
    existing_users = [user for user in similar_users if user in df_transactions.index]
    if not existing_users:
        return []
    
    # 類似ユーザーの店舗訪問を集計
    recommended_stores = df_transactions.loc[existing_users].sum().sort_values(ascending=False)
    top_stores = recommended_stores.head(top_n).index.tolist()
    
    # 店舗IDを整数に変換
    return [int(store.replace("store_", "")) for store in top_stores]

# メイン推薦ロジック
def calculate_recommendations(user_id: int, top_n: int = 5) -> Dict[str, Any]:
    """協調フィルタリングによるイベント推薦を計算する"""
    try:
        with session_scope() as session:
            # 1. 各種データの取得
            df_users = get_user_data(session)
            df_tags_onehot = get_user_tags(session)
            df_transactions_onehot = get_transaction_data(session)
            df_fav_events_onehot = get_favorite_events_onehot(session)
                        
            # 2. データの統合
            area_columns = [col for col in df_users.columns if col.startswith("postal_code")]
            df_users[area_columns] = df_users[area_columns].astype(int)
            
            # データフレームを結合
            df_final = df_users.set_index("user_id")
            
            # タグデータがあれば結合
            if not df_tags_onehot.empty:
                df_final = df_final.join(df_tags_onehot, how="left")
            
            # 取引データがあれば結合
            if not df_transactions_onehot.empty:
                df_final = df_final.join(df_transactions_onehot, how="left")

            if not df_fav_events_onehot.empty:
                df_final = df_final.join(df_fav_events_onehot, how="left")
            
            # 欠損値を0で埋める
            df_final = df_final.fillna(0)
            
            # 3. 類似ユーザーの特定
            similar_users = find_similar_users(df_final, user_id, top_n)
            if not similar_users:
                return {"events": [], "similarUsers": []}
            
            # # 4. 類似ユーザーが訪れた店舗の特定
            # store_ids = find_recommended_stores(df_transactions_onehot, similar_users)
            # if not store_ids:
            #     return {"events": [], "similarUsers": similar_users}
            
            # # 5. 店舗に関連するイベントの取得
            # events_data = get_events_by_store_ids(session, store_ids)
           
            # # 6. イベント情報をフォーマット
            # recommended_events = [
            #     format_event_to_recommendation(session, event) 
            #     for event in events_data
            # ]

            # 4. 類似ユーザーがお気に入り登録しているイベントを取得
            query = text("""
            SELECT DISTINCT e.event_id, e.event_name, e.description, e.start_date, e.end_date,
                            e.flyer_url, e.event_image_url, e.store_id, e.area
            FROM FavoriteEvents f
            JOIN Events e ON f.event_id = e.event_id
            WHERE f.user_id IN :similar_users
            ORDER BY e.start_date ASC
            LIMIT 6
            """)

            # SQLAlchemyにリストを渡す場合はタプル形式にする必要あり
            result_events = session.execute(query, {"similar_users": tuple(similar_users)}).fetchall()

            # 5. イベント情報をフォーマット
            recommended_events = [
                format_event_to_recommendation(session, event)
                for event in result_events
            ]
            
            return {
                "events": recommended_events,
                "similarUsers": similar_users
            }
            
    except Exception as e:
        print(f"推薦計算エラー: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"推薦計算中にエラーが発生しました: {str(e)}")

# APIエンドポイント
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
                popular_events = get_popular_events(session)
                events = [
                    format_event_to_recommendation(session, event, prefix_tag="人気") 
                    for event in popular_events
                ]
                recommendations["events"] = events
        
        return recommendations
    except HTTPException as http_ex:
        raise http_ex
    except Exception as e:
        print(f"レコメンデーションAPIエラー: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"レコメンデーション取得中にエラーが発生しました: {str(e)}")