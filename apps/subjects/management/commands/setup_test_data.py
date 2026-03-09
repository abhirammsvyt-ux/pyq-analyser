"""
Management command to create test data for the PYQ Analyzer.
Usage: python manage.py setup_test_data
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.users.models import User
from apps.subjects.models import Subject, Module, ExamPattern


class Command(BaseCommand):
    help = 'Creates test data for PYQ Analyzer'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating test data...'))
        
        # Get or create admin user
        try:
            user = User.objects.get(email='admin@test.com')
            self.stdout.write(f'Using existing user: {user.email}')
        except User.DoesNotExist:
            user = User.objects.create_superuser(
                username='admin',
                email='admin@test.com',
                password='admin123'
            )
            self.stdout.write(self.style.SUCCESS(f'Created admin user: {user.email}'))
        
        # Create a test subject
        subject, created = Subject.objects.get_or_create(
            user=user,
            name='Disaster Management',
            code='MCN301',
            defaults={
                'description': 'Comprehensive study of disaster management principles',
                'university': 'KTU',
                'exam_board': 'APJ Abdul Kalam Technological University',
                'year': '2019 Scheme',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created subject: {subject}'))
        else:
            self.stdout.write(f'Subject already exists: {subject}')
        
        # Create modules
        modules_data = [
            {
                'number': 1,
                'name': 'Introduction to Disasters',
                'description': 'Concepts, types, and classification of disasters',
                'topics': [
                    'Disaster definition and concepts',
                    'Types of disasters (natural and man-made)',
                    'Hazard, vulnerability, and risk',
                    'Classification of disasters',
                    'Disaster impact assessment'
                ],
                'keywords': [
                    'disaster', 'hazard', 'vulnerability', 'risk', 
                    'natural disaster', 'man-made', 'classification'
                ],
                'weightage': 20.0
            },
            {
                'number': 2,
                'name': 'Disaster Mitigation and Preparedness',
                'description': 'Strategies for disaster risk reduction',
                'topics': [
                    'Disaster management cycle',
                    'Mitigation strategies',
                    'Preparedness planning',
                    'Early warning systems',
                    'Capacity building',
                    'Risk reduction measures'
                ],
                'keywords': [
                    'mitigation', 'preparedness', 'prevention', 
                    'DRR', 'early warning', 'capacity building'
                ],
                'weightage': 20.0
            },
            {
                'number': 3,
                'name': 'Institutional Framework',
                'description': 'Disaster management organizations and policies',
                'topics': [
                    'NDMA (National Disaster Management Authority)',
                    'SDMA (State Disaster Management Authority)',
                    'DDMA (District Disaster Management Authority)',
                    'Disaster Management Act 2005',
                    'National Policy on Disaster Management',
                    'Institutional structure'
                ],
                'keywords': [
                    'NDMA', 'SDMA', 'DDMA', 'disaster management act', 
                    'policy', 'institutional', 'framework', 'authority'
                ],
                'weightage': 20.0
            },
            {
                'number': 4,
                'name': 'Response and Recovery',
                'description': 'Emergency response and post-disaster recovery',
                'topics': [
                    'Emergency response planning',
                    'Relief operations',
                    'Rescue operations',
                    'Rehabilitation measures',
                    'Recovery strategies',
                    'Reconstruction planning'
                ],
                'keywords': [
                    'response', 'relief', 'rehabilitation', 'recovery', 
                    'emergency', 'rescue', 'evacuation', 'reconstruction'
                ],
                'weightage': 20.0
            },
            {
                'number': 5,
                'name': 'Community-Based Disaster Management',
                'description': 'Role of communities in disaster management',
                'topics': [
                    'Community participation',
                    'CBDM (Community-Based Disaster Management)',
                    'Local disaster management',
                    'Awareness programs',
                    'Training and education',
                    'NGO and volunteer roles'
                ],
                'keywords': [
                    'community', 'participation', 'CBDM', 'local', 
                    'awareness', 'training', 'volunteer', 'NGO'
                ],
                'weightage': 20.0
            }
        ]
        
        for mod_data in modules_data:
            module, created = Module.objects.get_or_create(
                subject=subject,
                number=mod_data['number'],
                defaults={
                    'name': mod_data['name'],
                    'description': mod_data['description'],
                    'topics': mod_data['topics'],
                    'keywords': mod_data['keywords'],
                    'weightage': mod_data['weightage']
                }
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  Created: {module}'))
            else:
                # Update existing module
                module.name = mod_data['name']
                module.description = mod_data['description']
                module.topics = mod_data['topics']
                module.keywords = mod_data['keywords']
                module.weightage = mod_data['weightage']
                module.save()
                self.stdout.write(f'  Updated: {module}')
        
        # Create exam pattern
        exam_pattern, created = ExamPattern.objects.get_or_create(
            subject=subject,
            defaults={
                'name': 'KTU Standard Pattern',
                'description': 'Standard KTU exam pattern with Part A (Q1-10) and Part B (Q11-20)',
                'pattern_config': ExamPattern.get_default_ktu_pattern(),
                'part_a_marks': 3,
                'part_b_marks': 14,
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created exam pattern: {exam_pattern}'))
        else:
            self.stdout.write(f'Exam pattern already exists: {exam_pattern}')
        
        self.stdout.write(self.style.SUCCESS('\n✓ Test data setup complete!'))
        self.stdout.write(self.style.SUCCESS(f'\nSubject: {subject.name} ({subject.code})'))
        self.stdout.write(self.style.SUCCESS(f'Modules: {Module.objects.filter(subject=subject).count()}'))
        self.stdout.write(self.style.SUCCESS(f'\nYou can now:'))
        self.stdout.write(f'  1. Upload PYQ PDFs at: /papers/subject/{subject.pk}/upload/')
        self.stdout.write(f'  2. View analytics at: /analytics/subject/{subject.pk}/')
        self.stdout.write(f'  3. Download reports at: /reports/subject/{subject.pk}/')
