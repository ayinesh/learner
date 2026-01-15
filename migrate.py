"""Database migration script - runs SQL migrations against Railway PostgreSQL."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))


async def run_migration():
    """Run the database migration."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError:
        print("ERROR: SQLAlchemy not installed. Run: pip install sqlalchemy asyncpg")
        return False

    # Try to load from .env
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    import os
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        print("ERROR: DATABASE_URL not set in environment or .env file")
        print("\nSet it with your Railway PUBLIC URL:")
        print("  DATABASE_URL=postgresql+asyncpg://postgres:xxx@xxx.proxy.rlwy.net:PORT/railway")
        return False

    # Ensure asyncpg driver
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    print(f"Connecting to: {database_url[:50]}...")
    
    # Create engine
    try:
        engine = create_async_engine(database_url, echo=False)
    except Exception as e:
        print(f"ERROR: Failed to create database engine: {e}")
        return False

    # Get all migration files in order
    migrations_dir = Path(__file__).parent / "migrations"
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print(f"ERROR: No migration files found in {migrations_dir}")
        return False

    print(f"Found {len(migration_files)} migration files:")
    for f in migration_files:
        print(f"  - {f.name}")
    print()

    # Combine all migration files
    sql_content = ""
    for migration_file in migration_files:
        print(f"Reading migration: {migration_file.name}")
        sql_content += migration_file.read_text(encoding="utf-8") + "\n\n"
    
    # Split into individual statements
    # Handle PostgreSQL-specific syntax
    statements = []
    current_statement = []
    in_function = False
    
    for line in sql_content.split('\n'):
        stripped = line.strip()
        
        # Skip empty lines and comments at statement level
        if not stripped or stripped.startswith('--'):
            if current_statement:
                current_statement.append(line)
            continue
        
        current_statement.append(line)
        
        # Track function/trigger blocks
        if 'CREATE OR REPLACE FUNCTION' in stripped.upper() or 'CREATE FUNCTION' in stripped.upper():
            in_function = True
        
        if in_function:
            if stripped.endswith('$$ LANGUAGE plpgsql;') or stripped.endswith('$$ LANGUAGE plpgsql SECURITY DEFINER;'):
                in_function = False
                statements.append('\n'.join(current_statement))
                current_statement = []
        elif stripped.endswith(';'):
            statements.append('\n'.join(current_statement))
            current_statement = []
    
    # Don't forget any remaining statement
    if current_statement:
        remaining = '\n'.join(current_statement).strip()
        if remaining:
            statements.append(remaining)

    print(f"Found {len(statements)} SQL statements to execute\n")
    
    # Execute statements - each in its own transaction to handle errors gracefully
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, statement in enumerate(statements, 1):
        statement = statement.strip()
        if not statement:
            continue

        # Get first line for display
        first_line = statement.split('\n')[0][:60]

        try:
            async with engine.begin() as conn:
                await conn.execute(text(statement))
            print(f"  [{i}/{len(statements)}] OK {first_line}...")
            success_count += 1
        except Exception as e:
            error_msg = str(e)
            # Some errors are OK (like "already exists", "duplicate key", etc.)
            if 'already exists' in error_msg.lower() or 'duplicate' in error_msg.lower():
                print(f"  [{i}/{len(statements)}] SKIP {first_line}... (already exists)")
                skip_count += 1
            else:
                print(f"  [{i}/{len(statements)}] FAIL {first_line}...")
                print(f"      Error: {error_msg.split(chr(10))[0][:100]}")
                error_count += 1

    await engine.dispose()
    
    print(f"\n{'='*50}")
    print(f"Migration complete!")
    print(f"  Successful: {success_count}")
    print(f"  Skipped (already exists): {skip_count}")
    print(f"  Errors: {error_count}")

    if error_count == 0:
        print("\n[OK] All statements executed successfully!")
        return True
    else:
        print(f"\n[WARN] {error_count} errors occurred. Check the output above.")
        return False


async def verify_tables():
    """Verify tables were created."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
        from dotenv import load_dotenv
    except ImportError:
        return
    
    load_dotenv()
    import os
    database_url = os.getenv("DATABASE_URL")
    
    if not database_url:
        return
    
    if "+asyncpg" not in database_url:
        database_url = database_url.replace("postgresql://", "postgresql+asyncpg://")
    
    engine = create_async_engine(database_url, echo=False)
    
    print("\nVerifying tables...")
    async with engine.begin() as conn:
        result = await conn.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        ))
        tables = [row[0] for row in result.fetchall()]
    
    await engine.dispose()
    
    if tables:
        print(f"Found {len(tables)} tables:")
        for table in tables:
            print(f"  • {table}")
    else:
        print("No tables found!")


if __name__ == "__main__":
    print("=" * 50)
    print("AI Learning System - Database Migration")
    print("=" * 50 + "\n")
    
    success = asyncio.run(run_migration())
    
    if success:
        asyncio.run(verify_tables())
