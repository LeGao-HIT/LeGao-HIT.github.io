import tempfile
import unittest
from pathlib import Path

from scripts import cache_repository_cards


class CacheRepositoryCardsTest(unittest.TestCase):
    def test_caches_light_and_dark_svg_cards_for_each_repository(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            data_file = root / "repositories.yml"
            output_dir = root / "assets" / "img" / "repositories"
            data_file.write_text(
                "github_users:\n"
                "  - LeGao-HIT\n"
                "\n"
                "repo_description_lines_max: 2\n"
                "\n"
                "github_repos:\n"
                "  - LeGao-HIT/example-one\n"
                "  - LeGao-HIT/example-two\n",
                encoding="utf-8",
            )

            requested_urls = []

            def fake_fetch(url):
                requested_urls.append(url)
                return f"<svg>{url}</svg>".encode("utf-8")

            cache_repository_cards.cache_repository_cards(
                data_file=data_file,
                output_dir=output_dir,
                fetch=fake_fetch,
            )

            self.assertEqual(
                sorted(path.name for path in output_dir.iterdir()),
                [
                    "LeGao-HIT__example-one--dark.svg",
                    "LeGao-HIT__example-one--light.svg",
                    "LeGao-HIT__example-two--dark.svg",
                    "LeGao-HIT__example-two--light.svg",
                ],
            )
            self.assertIn("repo=example-one", requested_urls[0])
            self.assertIn("theme=default", requested_urls[0])
            self.assertIn("theme=dark", "\n".join(requested_urls))

    def test_fallback_svg_contains_repository_metadata(self):
        svg = cache_repository_cards.fallback_svg(
            "LeGao-HIT/example-one",
            "light",
            {
                "name": "example-one",
                "description": "Example cached card",
                "stargazers_count": 12,
                "forks_count": 3,
                "language": "Python",
            },
        ).decode("utf-8")

        self.assertIn("example-one", svg)
        self.assertIn("Example cached card", svg)
        self.assertIn("12", svg)
        self.assertIn("3", svg)
        self.assertIn("Python", svg)


if __name__ == "__main__":
    unittest.main()
