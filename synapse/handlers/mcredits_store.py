class McreditsStore:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def get_active_packages(self) -> list[dict]:
        """Return only active packages, ordered by sort_order."""
        rows = await self.db_pool.execute(
            """
            SELECT id, name, description, credits_amount, price_usd_cents, sort_order
            FROM mcredit_packages
            WHERE is_active = true
            ORDER BY sort_order ASC
            """
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "credits_amount": row[3],
                "price_usd_cents": row[4],
                "sort_order": row[5],
            }
            for row in rows
        ]

    async def get_all_packages(self) -> list[dict]:
        """Return ALL packages (including inactive) for admin UI"""
        rows = await self.db_pool.execute(
            """
            SELECT id, name, description, credits_amount, price_usd_cents,
                   sort_order, is_active
            FROM mcredit_packages
            ORDER BY sort_order ASC, id ASC
            """
        )
        return [
            {
                "id": row[0],
                "name": row[1],
                "description": row[2],
                "credits_amount": row[3],
                "price_usd_cents": row[4],
                "sort_order": row[5],
                "is_active": row[6],
            }
            for row in rows
        ]

    async def create_or_update_package(self, data: dict) -> int:
        """Create or update a package. Returns the package id."""
        name = data["name"]
        description = data.get("description")
        credits_amount = data["credits_amount"]
        price_usd_cents = data["price_usd_cents"]
        sort_order = data.get("sort_order", 0)
        is_active = data.get("is_active", True)
        package_id = data.get("id")

        if package_id:
            # Update existing
            await self.db_pool.execute(
                """
                UPDATE mcredit_packages
                SET name = %s, description = %s, credits_amount = %s,
                    price_usd_cents = %s, sort_order = %s, is_active = %s,
                    updated_ts = EXTRACT(EPOCH FROM NOW())::bigint
                WHERE id = %s
                """,
                (name, description, credits_amount, price_usd_cents, sort_order, is_active, package_id)
            )
            return package_id
        else:
            # Insert new
            row = await self.db_pool.execute(
                """
                INSERT INTO mcredit_packages (name, description, credits_amount,
                    price_usd_cents, sort_order, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (name, description, credits_amount, price_usd_cents, sort_order, is_active)
            )
            return row[0][0]
