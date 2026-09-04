from setuptools import setup

with open("README.md", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="instagram-graphql-scraper",
    version="0.1.0",
    description="Collects posts from a public Instagram profile via captured GraphQL requests.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="faustren",
    license="MIT",
    package_dir={"instagram_graphql_scraper": "."},
    packages=[
        "instagram_graphql_scraper",
        "instagram_graphql_scraper.base",
        "instagram_graphql_scraper.pages",
        "instagram_graphql_scraper.utils",
    ],
    install_requires=[
        "selenium>=4.20",
        "selenium-wire>=5.1",
        "requests>=2.31",
        "brotli>=1.1",
    ],
    python_requires=">=3.10",
)
