from sqlalchemy import Column, Integer, String, ForeignKey, Date, Enum, TIMESTAMP, Text, Time
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum
from sqlalchemy import Enum as SQLAlchemyEnum

Base = declarative_base()

# Families テーブル
class Family(Base):
    __tablename__ = 'Families'

    family_id = Column(Integer, primary_key=True, autoincrement=True)
    family_name = Column(String(255), nullable=False)
    users = relationship("User", back_populates="family")

    def __repr__(self):
        return f"<Family(family_id={self.family_id}, family_name={self.family_name})>"

# FamilyRelationship テーブル
class RelationshipType(enum.Enum):
    FATHER = "父"
    MOTHER = "母"
    SON = "息子"
    DAUGHTER = "娘"
    GRANDFATHER = "祖父"
    GRANDMOTHER= "曾祖"
    OTHER = "その他"

class FamilyRelationship(Base):
    __tablename__ = 'FamilyRelationship'

    relationship_id = Column(Integer, primary_key=True, autoincrement=True)
    relationship_type = Column(String(50), nullable=False)
    users = relationship("User", back_populates="relation")

    def __repr__(self):
        return f"<FamilyRelationship(relationship_id={self.relationship_id}, relationship_type={self.relationship_type})>"

# # Area テーブル
# class Area(Base):
#     __tablename__ = 'Area'

#     area_id = Column(Integer, primary_key=True, autoincrement=True)
#     area_name = Column(String(255), unique=True, nullable=False)
#     users = relationship("User", back_populates="area")

#     def __repr__(self):
#         return f"<Area(area_id={self.area_id}, area_name={self.area_name})>"

# Users テーブル
class User(Base):
    __tablename__ = 'Users'

    user_id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    name_kana = Column(String(255), nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    family_id = Column(Integer, ForeignKey('Families.family_id', ondelete="SET NULL"), nullable=True)
    relationship_id = Column(Integer, ForeignKey('FamilyRelationship.relationship_id', ondelete="SET NULL"), nullable=True)
    birth_date = Column(Date, nullable=False)
    gender = Column(Enum('M', 'F', 'U'), nullable=False)
    postal_code = Column(String(8), nullable=True)
    address1 = Column(String(255), nullable=True)
    address2 = Column(String(255), nullable=True)
    nimoca_id = Column(String(255), nullable=True)  # 追加
    saibugas_id = Column(String(255), nullable=True)  # 追加
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=True)

    family = relationship("Family", back_populates="users")
    relation = relationship("FamilyRelationship", back_populates="users")
    tags = relationship("UserTag", back_populates="user")

    def __repr__(self):
        return f"<User(user_id={self.user_id}, name={self.name}, email={self.email})>"

# UserTags (ユーザーとタグの中間テーブル)
class UserTag(Base):
    __tablename__ = 'UserTags'

    user_tag_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('Users.user_id', ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey('Tags.tag_id', ondelete="CASCADE"), nullable=False)

    user = relationship("User", back_populates="tags")
    tag = relationship("Tag", back_populates="users")

    def __repr__(self):
        return f"<UserTag(user_tag_id={self.user_tag_id}, user_id={self.user_id}, tag_id={self.tag_id})>"

# Tags (タグ管理)
class Tag(Base):
    __tablename__ = 'Tags'

    tag_id = Column(Integer, primary_key=True, autoincrement=True)
    tag_name = Column(String(255), unique=True, nullable=False)

    users = relationship("UserTag", back_populates="tag")
    events = relationship("EventTag", back_populates="tag")

    def __repr__(self):
        return f"<Tag(tag_id={self.tag_id}, tag_name={self.tag_name})>"

# Stores (店舗管理)
class Store(Base):
    __tablename__ = 'Stores'

    store_id = Column(Integer, primary_key=True, autoincrement=True)
    store_name = Column(String(255), unique=True, nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    events = relationship("Event", back_populates="store")
    transactions = relationship("PointTransaction", back_populates="store")

    def __repr__(self):
        return f"<Store(store_id={self.store_id}, store_name={self.store_name})>"

# Events (イベント管理)
class Event(Base):
    __tablename__ = 'Events'

    event_id = Column(Integer, primary_key=True, autoincrement=True)
    event_name = Column(String(255), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_at = Column(Time, nullable=False)
    end_at = Column(Time, nullable=False)
    description = Column(Text, nullable=False)
    information = Column(Text, nullable=True)
    flyer_url = Column(String(500), nullable=True)  # フライヤーのURL追加
    event_image_url = Column(String(500), nullable=True)  # イベントイメージのURL追加
    store_id = Column(Integer, ForeignKey('Stores.store_id', ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow, nullable=True)
    updated_at = Column(TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=True)

    store = relationship("Store", back_populates="events")
    tags = relationship("EventTag", back_populates="event")

    def __repr__(self):
        return f"<Event(event_id={self.event_id}, event_name={self.event_name})>"

# EventTags (イベントとタグの中間テーブル)
class EventTag(Base):
    __tablename__ = 'EventTags'

    event_tag_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(Integer, ForeignKey('Events.event_id', ondelete="CASCADE"), nullable=False)
    tag_id = Column(Integer, ForeignKey('Tags.tag_id', ondelete="CASCADE"), nullable=False)

    event = relationship("Event", back_populates="tags")
    tag = relationship("Tag", back_populates="events")

    def __repr__(self):
        return f"<EventTag(event_tag_id={self.event_tag_id}, event_id={self.event_id}, tag_id={self.tag_id})>"

# TransactionType (トランザクション種別)
class TransactionType(Base):
    __tablename__ = 'Transaction_type'

    transaction_type_id = Column(Integer, primary_key=True, autoincrement=True)
    transaction_type = Column(String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<TransactionType(transaction_type_id={self.transaction_type_id}, transaction_type={self.transaction_type})>"

# PointTransaction (ポイント取引)
class PointTransaction(Base):
    __tablename__ = 'PointTransaction'

    transaction_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('Users.user_id', ondelete="SET NULL"))
    store_id = Column(Integer, ForeignKey('Stores.store_id', ondelete="CASCADE"))
    transaction_type_id = Column(Integer, ForeignKey('Transaction_type.transaction_type_id', ondelete="CASCADE"))
    point = Column(Integer, nullable=False)
    transaction_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User")
    store = relationship("Store", back_populates="transactions")
    transaction_type = relationship("TransactionType")

    def __repr__(self):
        return f"<PointTransaction(transaction_id={self.transaction_id}, point={self.point})>"

# FavoriteEvents (ユーザーのお気に入りイベント)
class FavoriteEvent(Base):
    __tablename__ = 'FavoriteEvents'

    favorite_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('Users.user_id', ondelete="CASCADE"), nullable=False)
    event_id = Column(Integer, ForeignKey('Events.event_id', ondelete="CASCADE"), nullable=False)
    created_at = Column(TIMESTAMP, default=datetime.utcnow)

    user = relationship("User", backref="favorite_events")
    event = relationship("Event", backref="favorited_by")

    def __repr__(self):
        return f"<FavoriteEvent(favorite_id={self.favorite_id}, user_id={self.user_id}, event_id={self.event_id})>"
