import asyncio, json, sys
from sqlalchemy import text
import app.db.session as dbs
async def main():
    dbs.init_engine()
    async with dbs.AsyncSessionLocal() as s:
        q = "SELECT status, error_detail, result_summary::text FROM experiments WHERE id='b7635d49-3431-4348-955e-fd4a6a771f3e'"
        r = await s.execute(text(q))
        row = r.first()
        print(row[0], "|", row[1])
        sys.stdout.buffer.write((row[2][:6000] if row[2] else "").encode("utf-8"))
asyncio.run(main())
