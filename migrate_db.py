#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для миграции БД - добавление новых полей
Запустите: python migrate_db.py
"""

import asyncio
import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

async def migrate_database():
    """Добавляет отсутствующие поля в БД"""
    
    if not DATABASE_URL:
        print("❌ DATABASE_URL не найден в .env файле")
        return
    
    try:
        # Подключаемся к БД
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Подключение к БД успешно")
        
        # Список миграций
        migrations = [
            # Добавляем новые поля для piar
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS piar_instagram VARCHAR(255);",
            "ALTER TABLE posts ADD COLUMN IF NOT EXISTS piar_telegram VARCHAR(255);",
            
            # Удаляем старое поле piar_contacts если оно есть
            "ALTER TABLE posts DROP COLUMN IF EXISTS piar_contacts;",
            
            # Проверяем и добавляем поля если их нет
            """
            DO $$ 
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_instagram') THEN
                    ALTER TABLE posts ADD COLUMN piar_instagram VARCHAR(255);
                END IF;
                
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                              WHERE table_name='posts' AND column_name='piar_telegram') THEN
                    ALTER TABLE posts ADD COLUMN piar_telegram VARCHAR(255);
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
        
        # Проверяем структуру таблицы
        result = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'posts' 
            ORDER BY ordinal_position;
        """)
        
        print("\n📋 Текущая структура таблицы posts:")
        for row in result:
            print(f"  - {row['column_name']}: {row['data_type']}")
        
        await conn.close()
        print("\n🎉 Миграция завершена успешно!")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")

if __name__ == "__main__":
    asyncio.run(migrate_database())
