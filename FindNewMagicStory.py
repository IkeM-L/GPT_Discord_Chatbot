import requests
from bs4 import BeautifulSoup

class MagicStoryChecker:
    def __init__(self, url, storage_file='seen_articles.txt'):
        self.url = url
        self.storage_file = storage_file
        self.seen_articles = self.load_seen_articles()

    def load_seen_articles(self):
        """Load the set of seen articles from a file."""
        try:
            with open(self.storage_file, 'r') as file:
                return set(file.read().splitlines())
        except FileNotFoundError:
            return set()

    def save_seen_articles(self):
        """Save the set of seen articles to a file."""
        with open(self.storage_file, 'w') as file:
            file.write('\n'.join(self.seen_articles))

    def fetch_articles(self):
        """Fetch the HTML content of the article page."""
        response = requests.get(self.url)
        if response.status_code != 200:
            raise Exception(f"Error fetching {self.url}: Status code {response.status_code}")
        return response.text

    def extract_article_links(self, html):
        """Extract the links to the articles from the HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        # Find all <a> tags with a 'href' attribute containing '/en/news/magic-story/'
        article_tags = soup.find_all('a', href=True)
        return [tag['href'] for tag in article_tags if '/en/news/magic-story/' in tag['href']]

    def get_new_articles(self):
        """Get the links to the new articles that have not been seen before."""
        html = self.fetch_articles()
        all_articles = self.extract_article_links(html)
        new_articles = [article for article in all_articles if article not in self.seen_articles]

        self.seen_articles.update(new_articles)
        self.save_seen_articles()

        return new_articles


# Usage
def check_for_new_magic_stories():
    """Check for new Magic: The Gathering stories and print the links to the new articles."""
    checker = MagicStoryChecker('https://magic.wizards.com/en/news/magic-story')
    new_articles = checker.get_new_articles()
    if new_articles:
        print("New articles found:")
        for article in new_articles:
            print(article)
    else:
        print("No new articles.")

# This function can be imported and run periodically in another bot.
# check_for_new_magic_stories()