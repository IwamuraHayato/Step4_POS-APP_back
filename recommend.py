import pandas as pd
import mysql.connector
from sqlalchemy import create_engine
from sklearn.metrics.pairwise import cosine_similarity

# データベースの接続情報
DB_USER = "ryoueno"
DB_PASSWORD = "tech0-himdb"
DB_HOST = "tech0-gen-8-step4-him-database.mysql.database.azure.com"
DB_PORT = 3306
DB_NAME = "hsp-db"

# MySQLに接続
engine = create_engine(f"mysql+mysqlconnector://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

# Usersテーブルの情報取得
query_users = "SELECT user_id, gender, relationship_id, area_id, birth_date FROM Users;"
df_users = pd.read_sql(query_users, engine)
df_users["gender"] = df_users["gender"].map({"M": 0, "F": 1, "U": 2})

# 年齢の計算
df_users["age"] = pd.to_datetime("today").year - pd.to_datetime(df_users["birth_date"]).dt.year
df_users.drop(columns=["birth_date"], inplace=True)

# 年齢の画像表示 Min-Maxスケーリング
from sklearn.preprocessing import MinMaxScaler
scaler = MinMaxScaler()
df_users["age"] = scaler.fit_transform(df_users[["age"]])

df_users = pd.get_dummies(df_users, columns=["area_id"])
area_columns = [col for col in df_users.columns if col.startswith("area_id_")]
df_users[area_columns] = df_users[area_columns].astype(int)


#UserTags情報の取得
query_tags = """SELECT u.user_id, t.tag_id FROM UserTags u JOIN Tags t ON u.tag_id = t.tag_id;"""
df_tags = pd.read_sql(query_tags, engine)
# ワンホットエンコーディング
df_tags_onehot = df_tags.pivot_table(index="user_id", columns="tag_id", aggfunc="size", fill_value=0)
df_tags_onehot = df_tags_onehot.add_prefix("tag_")

#PointTransaction情報の取得
query_transactions = "SELECT user_id, store_id FROM pointtransaction WHERE user_id IS NOT NULL;"
df_pointtransaction = pd.read_sql(query_transactions, engine)
# ワンホットエンコーディング
df_transactions_onehot = df_pointtransaction.pivot_table(index="user_id", columns="store_id", aggfunc="size", fill_value=0)
df_transactions_onehot = df_transactions_onehot.add_prefix("store_")


#データの統合
df_final = df_users.set_index("user_id")\
    .join(df_tags_onehot, how="left")\
    .join(df_transactions_onehot, how="left")\
    .fillna(0)

print(df_final.head())