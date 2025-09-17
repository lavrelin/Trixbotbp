#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция для изменения INTEGER на BIGINT для Telegram ID
Запустите: python migrate_to_bigint.py
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate_to_bigint():
    """Изменяет типы ID столбцов на BIGINT"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден в .env файле")
        return
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Подключение к БД успешно")
        
        print("\n🔍 Проверяем текущие типы столбцов...")
        
        # Проверяем типы ID столбцов
        id_columns = await conn.fetch("""
            SELECT 
                table_name, 
                column_name, 
                data_type,
                is_nullable
            FROM information_schema.columns 
            WHERE table_name IN ('users', 'posts') 
            AND column_name IN ('id', 'user_id')
            ORDER BY table_name, column_name;
        """)
        
        print("📋 Текущие типы ID столбцов:")
        for col in id_columns:
            print(f"  - {col['table_name']}.{col['column_name']}: {col['data_type']}")
        
        print("\n🔧 Выполняем миграцию к BIGINT...")
        
        # Создаем резервную копию данных (опционально)
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        posts_count = await conn.fetchval("SELECT COUNT(*) FROM posts")
        print(f"📊 Будем мигрировать {users_count} пользователей и {posts_count} постов")
        
        # Миграция в транзакции
        async with conn.transaction():
            try:
                # 1. Изменяем тип столбца users.id
                print("🔄 Изменяем users.id на BIGINT...")
                await conn.execute("ALTER TABLE users ALTER COLUMN id TYPE BIGINT;")
                print("✅ users.id изменен на BIGINT")
                
                # 2. Изменяем тип столбца posts.user_id
                print("🔄 Изменяем posts.user_id на BIGINT...")
                await conn.execute("ALTER TABLE posts ALTER COLUMN user_id TYPE BIGINT;")
                print("✅ posts.user_id изменен на BIGINT")
                
                print("🎉 Миграция завершена успешно!")
                
            except Exception as migration_error:
                print(f"❌ Ошибка миграции: {migration_error}")
                raise
        
        # Проверяем результат
        print("\n📋 Итоговые типы ID столбцов:")
        final_columns = await conn.fetch("""
            SELECT 
                table_name, 
                column_name, 
                data_type
            FROM information_schema.columns 
            WHERE table_name IN ('users', 'posts') 
            AND column_name IN ('id', 'user_id')
            ORDER BY table_name, column_name;
        """)
        
        for col in final_columns:
            status = "✅" if col['data_type'] == 'bigint' else "❌"
            print(f"  {status} {col['table_name']}.{col['column_name']}: {col['data_type']}")
        
        # Проверяем, что данные сохранились
        final_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        final_posts = await conn.fetchval("SELECT COUNT(*) FROM posts")
        
        print(f"\n📊 После миграции:")
        print(f"  Пользователей: {final_users} (было: {users_count})")
        print(f"  Постов: {final_posts} (было: {posts_count})")
        
        if final_users == users_count and final_posts == posts_count:
            print("✅ Все данные сохранены!")
        else:
            print("⚠️ Количество записей изменилось!")
        
        await conn.close()
        print("\n🎉 Миграция BIGINT завершена успешно!")
        print("✅ Теперь бот должен работать с большими Telegram ID")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        print("\nВозможные причины:")
        print("- Есть внешние ключи, ссылающиеся на эти столбцы")
        print("- Недостаточно прав для изменения структуры БД")
        print("- Активные подключения к БД")

if __name__ == "__main__":
    asyncio.run(migrate_to_bigint())
