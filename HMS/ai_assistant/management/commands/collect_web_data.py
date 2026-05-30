from django.core.management.base import BaseCommand
from ai_assistant.web_collector import WebCollector

class Command(BaseCommand):
    help = 'Crawl and collect medical information from trusted health portals'

    def add_arguments(self, parser):
        parser.add_argument('--url', type=str, help='Scrape a specific medical URL')

    def handle(self, *args, **options):
        wc = WebCollector()
        url = options.get('url')
        
        if url:
            self.stdout.write(f"Scraping specific URL: {url}...")
            obj = wc.collect_from_url(url)
            if obj:
                self.stdout.write(self.style.SUCCESS(
                    f"Successfully collected item:\n"
                    f"  - Title: {obj.title}\n"
                    f"  - Category: {obj.category}\n"
                    f"  - Saved to WebCollectedData (ID: {obj.id})"
                ))
            else:
                self.stdout.write(self.style.ERROR("Failed to collect web data from the specified URL."))
        else:
            self.stdout.write("Running default collection on trusted medical portals...")
            entries = wc.run_default_collection()
            self.stdout.write(self.style.SUCCESS(
                f"[+] Completed default collection. Scraped and stored {len(entries)} articles.\n"
                f"    Articles are saved as unverified in the database and are ready for admin review."
            ))
