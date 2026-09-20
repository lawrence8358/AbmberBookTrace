using System.Data;
using System.Data.Common;
using Microsoft.EntityFrameworkCore;

namespace BookTrace.Api.Data;

public static class SqliteSchemaUpgrade
{
    public static void EnsureBorrowingRecordSchema(BookDbContext database)
    {
        var connection = database.Database.GetDbConnection();
        var shouldClose = connection.State != ConnectionState.Open;
        if (shouldClose)
        {
            connection.Open();
        }

        try
        {
            Execute(connection, "PRAGMA foreign_keys = ON;");
            Execute(connection, """
                CREATE TABLE IF NOT EXISTS "BorrowingRecords" (
                    "Id" INTEGER NOT NULL CONSTRAINT "PK_BorrowingRecords" PRIMARY KEY AUTOINCREMENT,
                    "BookId" INTEGER NOT NULL,
                    "BorrowerName" TEXT NOT NULL,
                    "BorrowDateUtc" TEXT NOT NULL,
                    "DueDateUtc" TEXT NULL,
                    "ReturnedAtUtc" TEXT NULL,
                    "Note" TEXT NULL,
                    CONSTRAINT "FK_BorrowingRecords_Books_BookId"
                        FOREIGN KEY ("BookId") REFERENCES "Books" ("Id") ON DELETE CASCADE
                );
                """);

            var existingColumns = ReadColumns(connection, "BorrowingRecords");
            var missingColumns = new (string Name, string Definition)[]
            {
                ("BookId", "INTEGER NOT NULL DEFAULT 0"),
                ("BorrowerName", "TEXT NOT NULL DEFAULT ''"),
                ("BorrowDateUtc", "TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'"),
                ("DueDateUtc", "TEXT NULL"),
                ("ReturnedAtUtc", "TEXT NULL"),
                ("Note", "TEXT NULL"),
            };

            foreach (var (name, definition) in missingColumns)
            {
                if (existingColumns.Contains(name))
                {
                    continue;
                }

                Execute(connection, $"ALTER TABLE \"BorrowingRecords\" ADD COLUMN \"{name}\" {definition};");
            }

            Execute(connection, "CREATE INDEX IF NOT EXISTS \"IX_BorrowingRecords_BookId\" ON \"BorrowingRecords\" (\"BookId\");");
        }
        finally
        {
            if (shouldClose)
            {
                connection.Close();
            }
        }
    }

    private static HashSet<string> ReadColumns(DbConnection connection, string tableName)
    {
        using var command = connection.CreateCommand();
        command.CommandText = $"PRAGMA table_info(\"{tableName}\");";
        var columns = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
        using var reader = command.ExecuteReader();
        while (reader.Read())
        {
            columns.Add(reader.GetString(1));
        }

        return columns;
    }

    private static void Execute(DbConnection connection, string sql)
    {
        using var command = connection.CreateCommand();
        command.CommandText = sql;
        command.ExecuteNonQuery();
    }
}
