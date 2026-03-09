"""Management command to process papers in background."""
from django.core.management.base import BaseCommand
from apps.papers.models import Paper
from apps.papers.background_processor import process_subject_papers


class Command(BaseCommand):
    help = 'Process all queued papers'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subject-id',
            type=str,
            help='Process papers for specific subject ID',
        )

    def handle(self, *args, **options):
        subject_id = options.get('subject_id')
        
        if subject_id:
            self.stdout.write(f'Processing papers for subject {subject_id}...')
            process_subject_papers(subject_id)
        else:
            # Process all subjects with pending papers
            from apps.subjects.models import Subject
            subjects_with_pending = Subject.objects.filter(
                papers__status=Paper.ProcessingStatus.PROCESSING
            ).distinct()
            
            for subject in subjects_with_pending:
                self.stdout.write(f'Processing subject: {subject.name}')
                process_subject_papers(str(subject.id))
        
        self.stdout.write(self.style.SUCCESS('Processing complete'))
