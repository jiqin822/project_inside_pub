"""Script to check if a user exists by email."""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infra.db.base import AsyncSessionLocal
from app.infra.db.models.user import UserModel


async def check_user_by_email(email: str):
    """Check if a user exists by email."""
    async with AsyncSessionLocal() as session:
        try:
            # Find the user
            result = await session.execute(
                select(UserModel).where(UserModel.email == email)
            )
            user = result.scalar_one_or_none()
            
            if not user:
                print(f"❌ User with email '{email}' NOT FOUND in the system.")
                print(f"\n   This means:")
                print(f"   - When adding this email as a relationship, an invite will be created")
                print(f"   - The relationship will show as 'pending' until the user signs up")
                print(f"   - The invite page will pop up to share the invitation link")
                return False
            
            print(f"✅ User with email '{email}' EXISTS in the system:")
            print(f"   ID: {user.id}")
            print(f"   Email: {user.email}")
            print(f"   Display Name: {user.display_name}")
            print(f"   Is Active: {user.is_active}")
            print(f"   Created At: {user.created_at}")
            print(f"\n   This means:")
            print(f"   - When adding this email as a relationship, a direct relationship will be created")
            print(f"   - The relationship will be active immediately (not pending)")
            return True
            
        except Exception as e:
            print(f"❌ Error checking user: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    email = sys.argv[1] if len(sys.argv) > 1 else "a@g.com"
    print(f"🔍 Checking if user '{email}' exists...\n")
    asyncio.run(check_user_by_email(email))
