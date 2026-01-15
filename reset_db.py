"""Reset database - drops all tables and types."""

import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def reset_database():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine
    
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return
        
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    print(f"Connecting to: {database_url[:50]}...")
    engine = create_async_engine(database_url)
    
    print("Dropping all tables...")
    async with engine.begin() as conn:
        await conn.execute(text("""
            DO $$ 
            DECLARE r RECORD;
            BEGIN
                FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP
                    EXECUTE 'DROP TABLE IF EXISTS ' || quote_ident(r.tablename) || ' CASCADE';
                END LOOP;
            END $$;
        """))
        print("✓ Tables dropped")
        
        await conn.execute(text("""
            DO $$ 
            DECLARE r RECORD;
            BEGIN
                FOR r IN (SELECT typname FROM pg_type t JOIN pg_namespace n ON t.typnamespace = n.oid WHERE n.nspname = 'public' AND t.typtype = 'e') LOOP
                    EXECUTE 'DROP TYPE IF EXISTS ' || quote_ident(r.typname) || ' CASCADE';
                END LOOP;
            END $$;
        """))
        print("✓ Types dropped")
    
    await engine.dispose()
    print("\n✓ Database reset complete!")

if __name__ == "__main__":
    asyncio.run(reset_database())
