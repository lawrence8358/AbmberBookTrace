using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace BookTrace.Api.Data.Migrations
{
    /// <inheritdoc />
    public partial class UpdateBookStorageAndDates : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "CoverImageData",
                table: "Books");

            migrationBuilder.AddColumn<string>(
                name: "CoverStorageName",
                table: "Books",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateOnly>(
                name: "PublicationDate",
                table: "Books",
                type: "TEXT",
                nullable: true);

            migrationBuilder.AddColumn<DateOnly>(
                name: "PurchaseDate",
                table: "Books",
                type: "TEXT",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "CoverStorageName",
                table: "Books");

            migrationBuilder.AddColumn<byte[]>(
                name: "CoverImageData",
                table: "Books",
                type: "BLOB",
                nullable: true);

            migrationBuilder.DropColumn(
                name: "PublicationDate",
                table: "Books");

            migrationBuilder.DropColumn(
                name: "PurchaseDate",
                table: "Books");
        }
    }
}
