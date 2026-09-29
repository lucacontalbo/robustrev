import sqlite3


class ArxivDB:
    # A safe limit well below the default SQLite variable limit of 999
    SQLITE_SAFE_VARIABLE_LIMIT = 900

    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = sqlite3.connect(db_file)
        self.conn.row_factory = sqlite3.Row

    def reindex_papers(self):
        """
        Rebuilds all indexes on the 'papers' table, including the
        primary key index on 'arxiv_id'. This can optimize performance.
        """
        c = self.conn.cursor()
        print("Reindexing the 'papers' table...")
        c.execute("REINDEX papers")
        self.conn.commit()
        print("Reindexing complete.")

    def insert_papers(self, papers):
        """
        Insert a list of paper dicts into the database.
        Each dict should have keys: arxiv_id, title, abstract.
        """
        if not papers:
            return 0

        c = self.conn.cursor()
        count = 0
        for paper in papers:
            c.execute(
                "INSERT OR IGNORE INTO papers (arxiv_id, title, abstract) VALUES (?, ?, ?)",
                (paper["arxiv_id"], paper["title"], paper["abstract"]),
            )
            count += c.rowcount
        self.conn.commit()
        return count

    def load_batch(self, ids):
        """
        Loads a single batch of IDs using an IN clause. Efficient for small batches.
        """
        if not ids:
            return []

        placeholders = ",".join("?" * len(ids))
        query = f"""
            SELECT arxiv_id, title, abstract
            FROM papers
            WHERE arxiv_id IN ({placeholders})
        """
        c = self.conn.cursor()
        c.execute(query, ids)
        results = c.fetchall()

        return [
            {"arxiv_id": r["arxiv_id"], "title": r["title"], "abstract": r["abstract"]}
            for r in results
        ]

    def get_papers(self, ids: list[str]) -> list[dict]:
        """
        Robustly and efficiently fetches papers for a list of IDs.
        Uses a simple IN clause for small lists and a much faster
        temporary table JOIN for large lists.
        """
        if not ids:
            return []

        # For small queries, the IN clause is efficient and has less overhead.
        if len(ids) <= self.SQLITE_SAFE_VARIABLE_LIMIT:
            return self.load_batch(ids)

        # For large queries, a temporary table and JOIN is much faster.
        c = self.conn.cursor()

        try:
            # 1. Create a temporary table to hold the IDs
            c.execute("CREATE TEMPORARY TABLE temp_ids (id TEXT PRIMARY KEY NOT NULL)")

            # 2. Insert all IDs into the temporary table
            ids_to_insert = [
                (id_val,) for id_val in set(ids)
            ]  # Use set to ensure uniqueness
            c.executemany("INSERT INTO temp_ids (id) VALUES (?)", ids_to_insert)

            # 3. Perform a single, efficient JOIN query
            query = """
                SELECT p.arxiv_id, p.title, p.abstract
                FROM papers AS p
                JOIN temp_ids AS t ON p.arxiv_id = t.id
            """
            c.execute(query)
            results = c.fetchall()

            return [
                {
                    "arxiv_id": r["arxiv_id"],
                    "title": r["title"],
                    "abstract": r["abstract"],
                }
                for r in results
            ]
        finally:
            # 4. Ensure the temporary table is dropped
            c.execute("DROP TABLE IF EXISTS temp_ids")

    def get_fulltexts(self, ids):
        """
        Fetch full text paths (md_path) for a list of arxiv_ids.
        This method is also updated to handle large lists of IDs.
        """
        if not ids:
            return []

        # Reusing the optimized logic from get_papers for consistency
        if len(ids) <= self.SQLITE_SAFE_VARIABLE_LIMIT:
            all_results = []
            for i in range(0, len(ids), self.SQLITE_SAFE_VARIABLE_LIMIT):
                batch_ids = ids[i : i + self.SQLITE_SAFE_VARIABLE_LIMIT]
                if not batch_ids:
                    continue
                placeholders = ",".join("?" * len(batch_ids))
                query = f"SELECT arxiv_id, md_path FROM papers_metadata WHERE arxiv_id IN ({placeholders})"
                c = self.conn.cursor()
                c.execute(query, batch_ids)
                all_results.extend(c.fetchall())
            return [
                {"arxiv_id": r["arxiv_id"], "md_path": r["md_path"]}
                for r in all_results
            ]

        # Use temporary table for larger queries
        c = self.conn.cursor()
        try:
            c.execute("CREATE TEMPORARY TABLE temp_ids (id TEXT PRIMARY KEY NOT NULL)")
            ids_to_insert = [(id_val,) for id_val in set(ids)]
            c.executemany("INSERT INTO temp_ids (id) VALUES (?)", ids_to_insert)
            query = """
                SELECT m.arxiv_id, m.md_path
                FROM papers_metadata AS m
                JOIN temp_ids AS t ON m.arxiv_id = t.id
            """
            c.execute(query)
            results = c.fetchall()
            return [
                {"arxiv_id": r["arxiv_id"], "md_path": r["md_path"]} for r in results
            ]
        finally:
            c.execute("DROP TABLE IF EXISTS temp_ids")

    def count(self):
        c = self.conn.cursor()
        c.execute("SELECT COUNT(*) FROM papers")
        return c.fetchone()[0]

    def stream_arxiv_ids(self):
        """
        Memory-efficiently yields every arxiv_id from the papers table.
        """
        c = self.conn.cursor()
        c.execute("SELECT arxiv_id FROM papers")
        for row in c:
            yield row["arxiv_id"]

    def sample_random(self, n=5):
        """
        Returns n random papers from the database.
        """
        c = self.conn.cursor()
        c.execute(
            f"SELECT arxiv_id, title, abstract FROM papers ORDER BY RANDOM() LIMIT ?",
            (n,),
        )
        results = c.fetchall()
        return [
            {"arxiv_id": r["arxiv_id"], "title": r["title"], "abstract": r["abstract"]}
            for r in results
        ]

    def sample_batch(self, batch_size=50):
        """
        Efficiently yields batches of papers of size batch_size.
        """
        c = self.conn.cursor()
        c.execute("SELECT arxiv_id, title, abstract FROM papers")
        while True:
            rows = c.fetchmany(batch_size)
            if not rows:
                break
            yield [
                {
                    "arxiv_id": r["arxiv_id"],
                    "title": r["title"],
                    "abstract": r["abstract"],
                }
                for r in rows
            ]

    def close(self):
        self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
