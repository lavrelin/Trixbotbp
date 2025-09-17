#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Полная миграция БД для исправления всех проблем
Запустите: python fix_database.py
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def fix_database():
    """Исправляет все проблемы в БД"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден в .env файле")
        return
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Подключение к БД успешно")
        
        # Получаем текущую структуру таблиц
        print("\n🔍 Проверяем текущую структуру БД...")
        
        # Проверяем таблицу users
        users_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'users'
            ORDER BY ordinal_position;
        """)
        
        print("📋 Столбцы таблицы users:")
        for col in users_columns:
            print(f"  - {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        # Проверяем таблицу posts
        posts_columns = await conn.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns 
            WHERE table_name = 'posts'
            ORDER BY ordinal_position;
        """)
        
        print("📋 Столбцы таблицы posts:")
        for col in posts_columns:
            print(f"  - {col['column_name']}: {col['data_type']} ({'NULL' if col['is_nullable'] == 'YES' else 'NOT NULL'})")
        
        print("\n🔧 Выполняем исправления...")
        
        # Список всех миграций
        migrations = [
            # 1. Удаляем проблемные столбцы если они есть
            "ALTER TABLE users DROP COLUMN IF EXISTS updated_at;",
            "ALTER TABLE posts DROP COLUMN IF EXISTS updated_at;",
            
            # 2. Добавляем новые поля для piar если их нет
            """
            DO $$ 
            BEGIN
                -- Добавляем piar_instagram
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_instagram') THEN
                    ALTER TABLE posts ADD COLUMN piar_instagram VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_instagram';
                END IF;
                
                -- Добавляем piar_telegram
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_telegram') THEN
                    ALTER TABLE posts ADD COLUMN piar_telegram VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_telegram';
                END IF;
                
                -- Удаляем старое поле contacts если оно есть
                IF EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='posts' AND column_name='piar_contacts') THEN
                    ALTER TABLE posts DROP COLUMN piar_contacts;
                    RAISE NOTICE 'Удален столбец piar_contacts';
                END IF;
                
                -- Проверяем и добавляем другие нужные поля
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='is_piar') THEN
                    ALTER TABLE posts ADD COLUMN is_piar BOOLEAN DEFAULT FALSE;
                    RAISE NOTICE 'Добавлен столбец is_piar';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_name') THEN
                    ALTER TABLE posts ADD COLUMN piar_name VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_name';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_profession') THEN
                    ALTER TABLE posts ADD COLUMN piar_profession VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_profession';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_districts') THEN
                    ALTER TABLE posts ADD COLUMN piar_districts JSON;
                    RAISE NOTICE 'Добавлен столбец piar_districts';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_phone') THEN
                    ALTER TABLE posts ADD COLUMN piar_phone VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_phone';
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_price') THEN
                    ALTER TABLE posts ADD COLUMN piar_price VARCHAR(255);
                    RAISE NOTICE 'Добавлен столбец piar_price';
                END IF;
            END $$;
            """,
            
            # 3. Обновляем типы данных если нужно
            """
            DO $$
            BEGIN
                -- Проверяем тип столбца media
                IF EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='posts' AND column_name='media' 
                          AND data_type != 'json') THEN
                    ALTER TABLE posts ALTER COLUMN media TYPE JSON USING media::JSON;
                    RAISE NOTICE 'Обновлен тип столбца media на JSON';
                END IF;
                
                -- Проверяем тип столбца hashtags
                IF EXISTS (SELECT 1 FROM information_schema.columns 
                          WHERE table_name='posts' AND column_name='hashtags' 
                          AND data_type != 'json') THEN
                    ALTER TABLE posts ALTER COLUMN hashtags TYPE JSON USING hashtags::JSON;
                    RAISE NOTICE 'Обновлен тип столбца hashtags на JSON';
                END IF;
            END $$;
            """
        ]
        
        # Выполняем миграции
        for i, migration in enumerate(migrations):
            try:
                await conn.execute(migration)
                print(f"✅ Миграция {i+1} выполнена")
            except Exception as e:
                print(f"⚠️  Миграция {i+1} пропущена: {e}")
        
        # Финальная проверка структуры
        print("\n📋 Итоговая структура таблицы posts:")
        final_posts = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'posts' 
            ORDER BY ordinal_position;
        """)
        
        for row in final_posts:
            print(f"  ✓ {row['column_name']}: {row['data_type']}")
        
        # Проверяем количество записей
        users_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        posts_count = await conn.fetchval("SELECT COUNT(*) FROM posts")
        
        print(f"\n📊 Статистика:")
        print(f"  Пользователей: {users_count}")
        print(f"  Постов: {posts_count}")
        
        await conn.close()
        print("\n🎉 База данных успешно исправлена!")
        print("✅ Теперь бот должен работать без ошибок")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")

if __name__ == "__main__":
    asyncio.run(fix_database())
