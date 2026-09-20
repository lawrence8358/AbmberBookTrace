using BookTrace.Api.Models;
using Microsoft.EntityFrameworkCore;

namespace BookTrace.Api.Data;

public sealed class BookDbContext(DbContextOptions<BookDbContext> options) : DbContext(options)
{
    public DbSet<Book> Books => Set<Book>();

    protected override void OnModelCreating(ModelBuilder modelBuilder)
    {
        modelBuilder.Entity<Book>(entity =>
        {
            entity.Property(book => book.Title).IsRequired().HasMaxLength(200);
            entity.Property(book => book.Author).HasMaxLength(200);
            entity.Property(book => book.Isbn).HasMaxLength(50);
            entity.Property(book => book.Publisher).HasMaxLength(200);
            entity.Property(book => book.Category).HasMaxLength(100);
            entity.Property(book => book.Location).HasMaxLength(200);
            entity.Property(book => book.DetailedLocation).HasMaxLength(200);
            entity.Property(book => book.Notes).HasMaxLength(2000);
            entity.Property(book => book.Status).HasConversion<string>().HasMaxLength(20);
        });
    }
}
