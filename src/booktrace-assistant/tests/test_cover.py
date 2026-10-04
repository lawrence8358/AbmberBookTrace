import unittest

from booktrace_assistant.cover import sanmin_cover_url


class SanminCoverUrlTests(unittest.TestCase):
    def test_derives_cdn_path_from_isbn13(self):
        self.assertEqual(
            sanmin_cover_url("9786267174142"),
            "https://cdnec.sanmin.com.tw/product_images/626/626717414.jpg",
        )
        self.assertEqual(
            sanmin_cover_url("978-986-17-5526-7"),
            "https://cdnec.sanmin.com.tw/product_images/986/986175526.jpg",
        )

    def test_rejects_isbns_the_cdn_scheme_cannot_cover(self):
        for isbn in ("", "123", "9791234567890", "978626717414X", "9786267174"):
            with self.subTest(isbn=isbn):
                self.assertEqual(sanmin_cover_url(isbn), "")


if __name__ == "__main__":
    unittest.main()
