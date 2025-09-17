import threading
import time
from collections import defaultdict

from src.database import get_db
from src.models import Article

# 全局计数器和锁
view_counts = defaultdict(int)
counter_lock = threading.Lock()

stop_event = threading.Event()
PERSIST_INTERVAL = 60  # 每60秒持久化一次


def persist_views():
    """定时将内存中的浏览量持久化到数据库"""
    while not stop_event.is_set():
        time.sleep(PERSIST_INTERVAL)

        try:
            # 创建计数器快照并清空
            with counter_lock:
                if not view_counts:
                    continue

                counts_snapshot = view_counts.copy()
                view_counts.clear()

            # 批量更新数据库
            update_success = False
            with get_db() as session:
                try:
                    for blog_id, count in counts_snapshot.items():
                        article = session.query(Article).filter_by(article_id=blog_id).first()
                        if article:
                            article.views += count
                        else:
                            session.add(Article(article_id=blog_id, views=count))
                    update_success = True
                except Exception as db_error:
                    # current_app.logger.error(f"Database update failed: {str(db_error)}",exc_info=True)
                    session.rollback()

            if not update_success:
                with counter_lock:
                    for blog_id, count in counts_snapshot.items():
                        view_counts[blog_id] += count

        except Exception as e:
            # current_app.logger.error(f"View persistence error: {str(e)}",exc_info=True)
            pass
    final_persist()


def final_persist():
    """应用关闭时执行最终持久化"""
    with counter_lock:
        if not view_counts:
            return

        counts_snapshot = view_counts.copy()
        view_counts.clear()

    with get_db() as session:
        try:
            for blog_id, count in counts_snapshot.items():
                article = session.query(Article).filter_by(article_id=blog_id).first()
                if article:
                    article.views += count
                else:
                    session.add(Article(article_id=blog_id, views=count))

        except Exception as e:
            # current_app.logger.error(f"Final persist failed: {str(e)}",exc_info=True)
            session.rollback()
