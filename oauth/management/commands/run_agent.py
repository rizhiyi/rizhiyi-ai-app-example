from django.core.management.base import BaseCommand
from crewai_agent.agent import run_crew
import os

class Command(BaseCommand):
    help = 'Runs the crewAI agent'

    def add_arguments(self, parser):
        parser.add_argument('query', type=str, help='The query for the agent', nargs='?', default='Explain error 500 and check recent logs.')
        parser.add_argument('--username', type=str, help='Rizhiyi username for API Key formatting')
        parser.add_argument('--api-key', type=str, help='Rizhiyi API Key')
        parser.add_argument('--base-url', type=str, help='Rizhiyi Base URL')

    def handle(self, *args, **options):
        query = options['query']
        username = options.get('username') or os.getenv("LOGEASE_USERNAME")
        api_key = options.get('api_key') or os.getenv("LOGEASE_API_KEY")
        base_url = options.get('base_url') or os.getenv("LOGEASE_BASE_URL")
        
        self.stdout.write(self.style.SUCCESS(f'Starting crewAI agent with query: {query}'))
        
        # Check for Moonshot API Key
        if not os.getenv("OPENAI_API_KEY"):
            self.stdout.write(self.style.WARNING("Warning: OPENAI_API_KEY not found in environment variables."))
            self.stdout.write("Please set it in your .env file.")
        
        try:
            result = run_crew(query, base_url=base_url, api_key=api_key, username=username)
            self.stdout.write(self.style.SUCCESS('Agent finished execution.'))
            self.stdout.write(f'Result: {result}')
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error running agent: {str(e)}'))
