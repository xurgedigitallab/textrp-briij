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
