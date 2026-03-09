"""
Custom User model with extended fields.
"""
import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Extended User model for PYQ Analyzer."""
    
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True
    )
    institution = models.CharField(max_length=255, blank=True)
    
    # Preferences stored as JSON
    preferences = models.JSONField(default=dict, blank=True)
    # Example: {"theme": "dark", "notifications": true}
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']
    
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'
    
    def __str__(self):
        return self.email
    
    def get_display_name(self):
        """Return the best available display name."""
        return self.full_name or self.username or self.email.split('@')[0]
    
    def get_preference(self, key, default=None):
        """Get a user preference by key."""
        return self.preferences.get(key, default)
    
    def set_preference(self, key, value):
        """Set a user preference."""
        self.preferences[key] = value
        self.save(update_fields=['preferences'])
